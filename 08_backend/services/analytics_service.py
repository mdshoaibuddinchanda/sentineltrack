import asyncio
import importlib
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch

try:
    from ..config import get_backend_config
    from ..event_bus import get_event_bus, AlertCreatedEvent, SightingCreatedEvent
    from ..metrics import get_metrics_collector
except (ImportError, ValueError):
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    ev_m = importlib.import_module("08_backend.event_bus")
    get_event_bus, AlertCreatedEvent, SightingCreatedEvent = ev_m.get_event_bus, ev_m.AlertCreatedEvent, ev_m.SightingCreatedEvent
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector

FairStreamScheduler = importlib.import_module("11_scale_deployment.scheduler").FairStreamScheduler
get_scale_config = importlib.import_module("11_scale_deployment.config").get_scale_config



logger = logging.getLogger("sentineltrack.analytics")


class AnalyticsWorker:
    """
    Multi-camera analytics worker with genuine micro-batch inference scheduler.
    Orchestrates:
      FramePacket batch -> P1 Vehicle Detection (YOLO11m)
      -> P2 ByteTrack Multi-Camera Tracker
      -> P3 Plate Detection & Observation Pipeline (YOLO11s-plate)
      -> P4 PP-OCRv5 Consensus Voting Pipeline (min_support_count=2)
      -> P5 Target Matching & Event Timing Propagation
      -> EventBus & Telemetry.
    """

    def __init__(self, config=None, event_bus=None, metrics_collector=None, scheduler=None):
        self.config = config or get_backend_config().analytics_worker
        self.scale_config = get_scale_config()
        self.event_bus = event_bus or get_event_bus()
        self.metrics = metrics_collector or get_metrics_collector()
        self.scheduler = scheduler or FairStreamScheduler()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._dispatch_thread: Optional[threading.Thread] = None
        self._dispatch_queue: queue.Queue = queue.Queue(maxsize=2000)
        # RLock to prevent recursive deadlocks between start() and _lazy_init_models()
        self._lock = threading.RLock()
        self._camera_queues = self.scheduler._camera_queues

        # Pipeline modules
        self._detector = None
        self._tracker_registry = None
        self._plate_detector = None
        self._plate_pipeline = None
        self._ocr_pipeline = None
        self._target_pipeline = None
        self._reid_service = None
        self._reid_last_capture_pts: dict[tuple[str, int, int], float] = {}


    def _lazy_init_models(self):
        with self._lock:
            if self._detector is not None:
                return

            cuda_available = torch.cuda.is_available()
            use_half = bool(self.config.enable_cuda_fp16 and cuda_available)
            device = "cuda" if cuda_available else "cpu"
            logger.info(f"Initializing AnalyticsWorker pipeline (device={device}, half={use_half})...")

            # 1. P1 Vehicle Detector (YOLO11m)
            try:
                p1_mod = importlib.import_module("01_vehicle_detection.detector")
                self._detector = p1_mod.VehicleDetector(half=use_half, device=device)
            except Exception as e:
                logger.exception(f"Failed to initialize P1 VehicleDetector: {e}")
                self.metrics.inc_errors()
                self._detector = None

            # 2. P2 Tracker Registry (ByteTrack)
            try:
                p2_mod = importlib.import_module("02_tracking.tracker")
                self._tracker_registry = p2_mod.CameraTrackerRegistry()
            except Exception as e:
                logger.exception(f"Failed to initialize P2 CameraTrackerRegistry: {e}")
                self.metrics.inc_errors()
                self._tracker_registry = None

            # 3. P3 Plate Detector (YOLO11s-plate) & PlateDetectionPipeline
            try:
                p3_det_mod = importlib.import_module("03_plate_detection.detector")
                p3_pipe_mod = importlib.import_module("03_plate_detection.pipeline")
                self._plate_detector = p3_det_mod.PlateDetector(half=use_half, device=device)
                self._plate_pipeline = p3_pipe_mod.PlateDetectionPipeline(plate_detector=self._plate_detector)
            except Exception as e:
                logger.exception(f"Failed to initialize P3 PlateDetectionPipeline: {e}")
                self.metrics.inc_errors()
                self._plate_detector = None
                self._plate_pipeline = None

            # 4. P4 Plate OCR Pipeline (PP-OCRv5 Mobile ONNX + Consensus Voter with frozen min_support_count=2)
            try:
                p4_pipe_mod = importlib.import_module("04_plate_ocr.pipeline")
                p4_rec_mod = importlib.import_module("04_plate_ocr.recognizers")
                p4_voter_mod = importlib.import_module("04_plate_ocr.voting")

                recognizer = p4_rec_mod.get_recognizer(engine_name="ppocr_mobile", device=device)
                voter = p4_voter_mod.MultiFramePlateVoter(min_crop_quality=0.20, min_support_count=2)
                self._ocr_pipeline = p4_pipe_mod.PlateOCRPipeline(recognizer=recognizer, voter=voter)
            except Exception as e:
                logger.exception(f"Failed to initialize P4 PlateOCRPipeline: {e}")
                self.metrics.inc_errors()
                self._ocr_pipeline = None

            # 5. P5 Target Matching Pipeline
            try:
                p5_mod = importlib.import_module("05_target_matching.pipeline")
                tgt_svc_mod = importlib.import_module("08_backend.services.target_service")
                shared_wm = tgt_svc_mod.get_shared_watchlist_manager()
                self._target_pipeline = p5_mod.TargetMatchingPipeline(watchlist_manager=shared_wm)
            except Exception as e:
                logger.exception(f"Failed to initialize P5 TargetMatchingPipeline: {e}")
                self.metrics.inc_errors()
                self._target_pipeline = None

            # 6. Conditional P6 appearance fallback. The extractor is lazy so
            # a strong ANPR result never loads or runs the appearance model.
            try:
                reid_mod = importlib.import_module("06_vehicle_reid.service")
                self._reid_service = reid_mod.VehicleReIDService()
            except Exception as e:
                logger.exception(f"Failed to initialize optional P6 ReID service: {e}")
                self.metrics.inc_errors()
                self._reid_service = None

    @staticmethod
    def _reid_evidence_level(reid_service, plate_observations, track_ocr, p5_candidate):
        evidence_mod = importlib.import_module("06_vehicle_reid.models")
        AppearanceEvidence = evidence_mod.AppearanceEvidence
        if p5_candidate is not None:
            return reid_service.fusion.infer_evidence_level(p5_candidate)
        if track_ocr is not None and getattr(track_ocr, "best_text", None):
            return AppearanceEvidence.PARTIAL_PLATE
        if plate_observations:
            return AppearanceEvidence.PARTIAL_PLATE
        return AppearanceEvidence.NO_USABLE_PLATE

    def _reid_capture_due(self, track) -> bool:
        """Limit appearance extraction to one crop per track per second."""
        key = (str(track.camera_id), int(track.stream_epoch), int(track.track_id))
        current_pts = float(getattr(track, "last_pts_ms", 0.0))
        previous_pts = self._reid_last_capture_pts.get(key)
        if previous_pts is not None and current_pts >= previous_pts and current_pts - previous_pts < 1000.0:
            return False
        self._reid_last_capture_pts[key] = current_pts
        if len(self._reid_last_capture_pts) > 20000:
            self._reid_last_capture_pts = dict(list(self._reid_last_capture_pts.items())[-10000:])
        return True

    def _process_reid_for_track(self, packet, track, plate_observations, track_ocr, p5_candidate):
        """Run the bounded P6 gate and return operator-visible diagnostics."""
        if self._reid_service is None:
            return {
                "track_id": int(track.track_id),
                "ran": False,
                "identity_source": "REID_UNAVAILABLE",
                "reason": ["REID_SERVICE_UNAVAILABLE"],
            }

        evidence_level = self._reid_evidence_level(
            self._reid_service,
            plate_observations,
            track_ocr,
            p5_candidate,
        )
        evidence_name = evidence_level.value

        # This call returns before extraction for STRONG_PLATE and proves the
        # expensive appearance path is gated by ANPR evidence.
        if evidence_name == "STRONG_PLATE":
            process = self._reid_service.add_track_crop(
                track,
                None,
                evidence_level=evidence_level,
                event_time_utc=packet.event_time_utc,
            )
            fusion = self._reid_service.fuse_p5_candidate(
                p5_candidate,
                None,
                evidence_level=evidence_level,
            )
            fused = fusion.to_dict()
            fused.update({"track_id": int(track.track_id), "ran": process.ran, "stored": process.stored})
            return fused

        if not self._reid_capture_due(track):
            return {
                "track_id": int(track.track_id),
                "ran": False,
                "identity_source": "REID_REVIEW" if evidence_name == "NO_USABLE_PLATE" else "ANPR_REID_SUPPORT",
                "evidence_level": evidence_name,
                "reason": ["REID_CAPTURE_THROTTLED"],
            }

        cropper = importlib.import_module("03_plate_detection.cropper")
        crop, cx1, cy1, _, _ = cropper.crop_vehicle(
            packet.frame,
            x1=track.x1,
            y1=track.y1,
            x2=track.x2,
            y2=track.y2,
            padding=0.08,
        )
        selected_plate = max(plate_observations, key=lambda item: item.quality_score) if plate_observations else None
        plate_bbox = None
        if selected_plate is not None:
            plate_bbox = (
                selected_plate.x1 - cx1,
                selected_plate.y1 - cy1,
                selected_plate.x2 - cx1,
                selected_plate.y2 - cy1,
            )

        process = self._reid_service.add_track_crop(
            track,
            crop,
            plate_bbox=plate_bbox,
            evidence_level=evidence_level,
            event_time_utc=packet.event_time_utc,
            source_frame_metadata={
                "camera_id": packet.camera_id,
                "stream_epoch": packet.stream_epoch,
                "pts_ms": packet.pts_ms,
                "event_time_source": packet.event_time_source,
                "event_time_quality": packet.event_time_quality,
                "plate_region_masked_for_reid": True,
            },
        )
        reid_candidate = None
        if process.profile is not None:
            candidates = self._reid_service.search_track(process.track_key, top_k=1)
            reid_candidate = candidates[0] if candidates else None
        fusion = self._reid_service.fuse_p5_candidate(
            p5_candidate,
            reid_candidate,
            evidence_level=evidence_level,
        )
        fused = fusion.to_dict()
        fused.update({
            "track_id": int(track.track_id),
            "ran": process.ran,
            "stored": process.stored,
            "model_available": process.model_available,
        })
        if process.skip_reason:
            fused.setdefault("reasons", []).append(process.skip_reason)
        if process.error:
            fused.setdefault("reasons", []).append("REID_MODEL_UNAVAILABLE")
        if reid_candidate is not None:
            fused["candidate_track"] = {
                "camera_id": reid_candidate.candidate_track.camera_id,
                "stream_epoch": reid_candidate.candidate_track.stream_epoch,
                "track_id": reid_candidate.candidate_track.track_id,
            }
        return fused

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._lazy_init_models()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SentinelAnalyticsWorker")
            self._thread.start()
            self._dispatch_thread = threading.Thread(target=self._dispatch_worker_loop, daemon=True, name="SentinelEventDispatcher")
            self._dispatch_thread.start()
            logger.info("SentinelTrack AnalyticsWorker started successfully.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._dispatch_thread and self._dispatch_thread.is_alive():
            self._dispatch_thread.join(timeout=2.0)
        logger.info("SentinelTrack AnalyticsWorker stopped.")

    def is_running(self) -> bool:
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def enqueue_frame(self, frame_packet: Any) -> bool:
        """Enqueues a FramePacket into the per-camera bounded queue with latest-frame drop policy."""
        self._lazy_init_models()
        ok = self.scheduler.enqueue_frame(frame_packet)
        self.metrics.inc_frames(ingested=1, dropped=0 if ok else 1)
        return ok

    def process_batch(self, packets: List[Any]) -> List[Dict[str, Any]]:
        """
        Genuine Micro-Batch Processing across multi-camera FramePackets.
        Executes P1 batch detection -> P2 tracking -> P3 Plate Pipeline -> P4 OCR consensus -> P5 matching.
        """
        if not packets:
            return []

        self._lazy_init_models()
        if not self._detector or not self._tracker_registry:
            logger.warning("Analytics models unavailable for batch processing.")
            return [{"status": "MODELS_UNAVAILABLE", "camera_id": getattr(p, "camera_id", "unknown")} for p in packets]

        results = []
        try:
            # 1. P1 Batch Vehicle Detection
            batch_dets = self._detector.detect_batch(packets)
            total_dets = sum(len(d) for d in batch_dets)
            self.metrics.inc_analytics(vehicles=total_dets)

            # 2. P2 Tracker Update + P3 Plate Pipeline per packet
            for p_idx, packet in enumerate(packets):
                dets = batch_dets[p_idx] if p_idx < len(batch_dets) else []
                tracker = self._tracker_registry.get_tracker(packet.camera_id)
                tracks = tracker.update(packet, dets)

                plate_observations = []
                if tracks and self._plate_pipeline:
                    plate_observations = self._plate_pipeline.process(packet, tracks)
                    self.metrics.inc_analytics(plates=len(plate_observations))

                    # 3. Feed Plate Observations into P4 OCR Pipeline
                    for obs in plate_observations:
                        if self._ocr_pipeline:
                            ix1, iy1 = int(round(obs.x1)), int(round(obs.y1))
                            ix2, iy2 = int(round(obs.x2)), int(round(obs.y2))
                            fh, fw = packet.frame.shape[:2]
                            ix1, iy1 = max(0, ix1), max(0, iy1)
                            ix2, iy2 = min(fw, ix2), min(fh, iy2)

                            if ix2 > ix1 and iy2 > iy1:
                                plate_crop = packet.frame[iy1:iy2, ix1:ix2]
                                if plate_crop is not None and plate_crop.size > 0:
                                    self._ocr_pipeline.process_observation(obs, plate_crop)
                                    self.metrics.inc_analytics(ocr=1)

                # 4. Multi-Frame Track Consensus, P5 Target Matching, and
                # conditional P6 appearance fallback.
                packet_reid = []
                for trk in tracks:
                    track_ocr = None
                    cands = []
                    if self._ocr_pipeline:
                        track_ocr = self._ocr_pipeline.get_track_result(
                            packet.camera_id, packet.stream_epoch, trk.track_id
                        )
                        if track_ocr and track_ocr.best_text:
                            # Propagate UTC event-timing contract
                            track_ocr.event_time_utc = packet.event_time_utc
                            track_ocr.event_time_source = packet.event_time_source
                            track_ocr.event_time_quality = packet.event_time_quality
                            track_ocr.ingest_time_utc = packet.ingest_time_utc

                            # 5. P5 Target Matching Pipeline
                            if self._target_pipeline:
                                cands, alerts, sighting = self._target_pipeline.process_track_ocr_result(track_ocr)
                                if sighting:
                                    self.metrics.inc_analytics(sightings=1)
                                    self._dispatch_event(SightingCreatedEvent(payload={
                                        "sighting_id": sighting.sighting_id,
                                        "camera_id": sighting.camera_id,
                                        "registration": sighting.registration_candidate,
                                        "match_score": sighting.match_score,
                                        "match_class": sighting.match_class.value if hasattr(sighting.match_class, "value") else str(sighting.match_class)
                                    }))

                                for alt in alerts:
                                    self.metrics.inc_analytics(alerts=1)
                                    self._dispatch_event(AlertCreatedEvent(payload={
                                        "alert_id": alt.alert_id,
                                        "camera_id": alt.camera_id,
                                        "registration": alt.registration,
                                        "severity": alt.severity.value if hasattr(alt.severity, "value") else str(alt.severity),
                                        "match_score": alt.match_score
                                    }))

                    track_plates = [obs for obs in plate_observations if obs.track_id == trk.track_id]
                    reid_result = self._process_reid_for_track(
                        packet,
                        trk,
                        track_plates,
                        track_ocr,
                        cands[0] if cands else None,
                    )
                    packet_reid.append(reid_result)

                results.append({"status": "PROCESSED", "camera_id": packet.camera_id, "pts_ms": packet.pts_ms, "reid": packet_reid})

        except Exception as e:
            logger.exception(f"Error during analytics batch execution: {e}")
            self.metrics.inc_errors()
            for packet in packets:
                results.append({"status": "ERROR", "camera_id": getattr(packet, "camera_id", "unknown"), "error": str(e)})

        return results

    def process_single_frame(self, frame_packet: Any) -> Dict[str, Any]:
        """Wrapper for single-frame processing delegating to micro-batch processor."""
        batch_res = self.process_batch([frame_packet])
        return batch_res[0] if batch_res else {"status": "NO_RESULT"}

    def _dispatch_event(self, event: Any):
        """Enqueues an event to the dedicated background dispatch queue without spawning endless threads."""
        try:
            self._dispatch_queue.put_nowait(event)
        except queue.Full:
            logger.warning("Event dispatch queue full; dropping event.")
            self.metrics.inc_errors()

    def _dispatch_worker_loop(self):
        """Single background worker loop consuming events and publishing them safely."""
        while self._running:
            try:
                event = self._dispatch_queue.get(timeout=0.1)
                self.event_bus.publish_sync(event)

                # Split-process PostgreSQL NOTIFY publishing if enabled
                if self.scale_config.enable_postgres_event_bridge:
                    try:
                        bridge_m = importlib.import_module("11_scale_deployment.event_bridge")
                        bridge = bridge_m.get_event_bridge()
                        bridge.publish_event(event.event_type, event.payload)
                    except Exception as pe:
                        logger.warning(f"Error publishing to Postgres event bridge: {pe}")

                self._dispatch_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in event dispatch worker: {e}")


    def _worker_loop(self):
        batch_size = max(1, self.config.micro_batch_size)
        max_wait_ms = self.config.max_batch_wait_ms

        while self._running:
            active_cams = len(self.scheduler._camera_order)
            self.metrics.set_camera_workers(active_cams)

            packets_to_process = self.scheduler.fetch_batch(
                max_batch_size=batch_size,
                max_wait_ms=max_wait_ms
            )

            if packets_to_process:
                self.process_batch(packets_to_process)
            else:
                time.sleep(0.005)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            scheduler_metrics = self.scheduler.get_metrics()
            return {
                "running": self._running,
                "active_camera_count": scheduler_metrics["active_camera_count"],
                "queues": scheduler_metrics["queue_depths"],
                "scheduler": scheduler_metrics,
                "models_loaded": {
                    "detector": self._detector is not None,
                    "tracker": self._tracker_registry is not None,
                    "plate_detector": self._plate_detector is not None,
                    "plate_pipeline": self._plate_pipeline is not None,
                    "ocr_pipeline": self._ocr_pipeline is not None,
                    "target_pipeline": self._target_pipeline is not None,
                    "reid_fallback": self._reid_service is not None,
                }
            }



_GLOBAL_ANALYTICS_WORKER: Optional[AnalyticsWorker] = None
_WORKER_LOCK = threading.Lock()


def get_analytics_worker() -> AnalyticsWorker:
    global _GLOBAL_ANALYTICS_WORKER
    with _WORKER_LOCK:
        if _GLOBAL_ANALYTICS_WORKER is None:
            _GLOBAL_ANALYTICS_WORKER = AnalyticsWorker()
        return _GLOBAL_ANALYTICS_WORKER
