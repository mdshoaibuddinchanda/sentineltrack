import sys
import time
import json
import numpy as np
import torch
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
PipelineProfiler = importlib.import_module("11_scale_deployment.profiling").PipelineProfiler
ResourceMonitor = importlib.import_module("11_scale_deployment.resource_monitor").ResourceMonitor
FramePacket = importlib.import_module("00_foundation.streams.models").FramePacket
AnalyticsWorker = importlib.import_module("08_backend.services.analytics_service").AnalyticsWorker


def run_pipeline_profiler(num_iterations: int = 50, batch_size: int = 4, output_json: str = "reports/p11/runs/pipeline_profile.json"):
    print("==================================================")
    print("    SENTINELTRACK PIPELINE STAGE PROFILER         ")
    print("==================================================")
    print(f"Iterations: {num_iterations} | Batch Size: {batch_size}")

    profiler = PipelineProfiler(warmup_iterations=5)
    monitor = ResourceMonitor()
    monitor.start()

    worker = AnalyticsWorker()
    worker._lazy_init_models()

    # Generate synthetic video test frames (1080p BGR image)
    test_frames = []
    for i in range(batch_size):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # Draw some synthetic vehicle-like shapes
        frame[300:700, 400:900] = [120, 120, 120]
        frame[500:580, 550:750] = [240, 240, 240]
        pkt = FramePacket(
            camera_id=f"cam_{i % 8:02d}",
            pts_ms=float(i * 40),
            frame=frame,
            stream_epoch=1,
            ingest_time_utc=datetime.now(timezone.utc),
            event_time_utc=datetime.now(timezone.utc)
        )
        test_frames.append(pkt)

    print("Running profiling loop across P1..P5 stages...")
    for it in range(num_iterations):
        t_iter_start = time.perf_counter()

        with profiler.stage_timer("p1_detect"):
            dets = worker._detector.detect_batch(test_frames) if worker._detector else [[] for _ in test_frames]

        with profiler.stage_timer("p2_track"):
            all_tracks = []
            if worker._tracker_registry:
                for idx, pkt in enumerate(test_frames):
                    trkr = worker._tracker_registry.get_tracker(pkt.camera_id)
                    tracks = trkr.update(pkt, dets[idx] if idx < len(dets) else [])
                    all_tracks.append((pkt, tracks))

        with profiler.stage_timer("p3_plate"):
            all_obs = []
            if worker._plate_pipeline:
                for pkt, tracks in all_tracks:
                    if tracks:
                        obs = worker._plate_pipeline.process(pkt, tracks)
                        all_obs.append((pkt, tracks, obs))

        with profiler.stage_timer("p4_ocr"):
            if worker._ocr_pipeline:
                for pkt, tracks, observations in all_obs:
                    for ob in observations:
                        crop = pkt.frame[int(ob.y1):int(ob.y2), int(ob.x1):int(ob.x2)]
                        if crop.size > 0:
                            worker._ocr_pipeline.process_observation(ob, crop)

        with profiler.stage_timer("p5_match"):
            if worker._target_pipeline and worker._ocr_pipeline:
                for pkt, tracks, _ in all_obs:
                    for trk in tracks:
                        ocr_res = worker._ocr_pipeline.get_track_result(pkt.camera_id, pkt.stream_epoch, trk.track_id)
                        if ocr_res:
                            worker._target_pipeline.process_track_ocr_result(ocr_res)

        e2e_ms = (time.perf_counter() - t_iter_start) * 1000.0
        profiler.record_stage("end_to_end", e2e_ms)
        profiler.mark_iteration()

    monitor.stop()
    res_summary = monitor.get_summary()
    prof_report = profiler.get_report()

    full_report = {
        "timestamp": time.time(),
        "batch_size": batch_size,
        "iterations": num_iterations,
        "profiler": prof_report,
        "resources": res_summary
    }

    print("\n--- Pipeline Stage Profile Summary ---")
    for st_name, st_metrics in prof_report["stages"].items():
        print(f"  {st_name:<16}: Mean={st_metrics['mean_ms']:>6.2f}ms | P50={st_metrics['p50_ms']:>6.2f}ms | P95={st_metrics['p95_ms']:>6.2f}ms | Throughput={st_metrics['throughput_fps']:>6.1f} FPS")

    print("\n--- Resource Summary ---")
    print(f"  CPU Mean: {res_summary['cpu_mean_percent']}% | RSS Peak: {res_summary['rss_peak_mb']} MB | VRAM Peak: {res_summary['vram_peak_mb']} MB")

    out_p = Path(output_json)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(full_report, f, indent=2)
    print(f"\nSaved profile JSON to {output_json}")
    print("==================================================")
    return full_report


if __name__ == "__main__":
    run_pipeline_profiler()
