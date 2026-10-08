import os
import sys
import time
import json
import cv2
import importlib
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

db_mod = importlib.import_module('00_foundation.registry.database')
fnd_res = importlib.import_module('00_foundation.streams.resolver')
fnd_reader = importlib.import_module('00_foundation.streams.reader')
p1_det = importlib.import_module('01_vehicle_detection.detector')
p2_pipe = importlib.import_module('02_tracking.pipeline')
p3_det = importlib.import_module('03_plate_detection.detector')
p3_pipe = importlib.import_module('03_plate_detection.pipeline')
p4_pipe = importlib.import_module('04_plate_ocr.pipeline')
p4_rec = importlib.import_module('04_plate_ocr.recognizers')

get_camera = db_mod.get_camera
resolve_stream = fnd_res.resolve_stream
RTSPReader = fnd_reader.RTSPReader
VehicleDetector = p1_det.VehicleDetector
VehicleTrackingPipeline = p2_pipe.VehicleTrackingPipeline
PlateDetector = p3_det.PlateDetector
PlateDetectionPipeline = p3_pipe.PlateDetectionPipeline
PlateOCRPipeline = p4_pipe.PlateOCRPipeline
get_recognizer = p4_rec.get_recognizer

REPORT_DIR = ROOT_DIR / 'reports' / 'plate_ocr' / 'live'
EVIDENCE_DIR = ROOT_DIR / 'reports' / 'plate_ocr' / 'evidence'


def run_live_ocr_validation(camera_ids: list[str] = ['1', '2', '3'], frames_per_camera: int = 20):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    print(f'[LIVE OCR] Starting Multi-Camera Live OCR Validation on: {camera_ids} ({frames_per_camera} frames/cam)...')

    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    p_detector = PlateDetector(model_path='models/plate/yolo11s_plate_v2.pt', confidence=0.20, imgsz=960)
    recognizer = get_recognizer('ppocr_mobile', device='cpu')
    ocr_pipe = PlateOCRPipeline(recognizer=recognizer, default_variant='raw', min_crop_quality=0.20)

    overall_results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'recognizer': recognizer.model_name,
        'cameras_tested': [],
        'total_frames': 0,
        'total_vehicles_tracked': 0,
        'tracks_with_plate_observations': 0,
        'tracks_ocr_attempted': 0,
        'tracks_with_ge2_hypotheses': 0,
        'tracks_stable_consensus': 0,
    }

    markdown_lines = [
        '# Sentinel Live Multi-Camera OCR Validation Report',
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Recognizer:** {recognizer.model_name}",
        '',
        '| Camera ID | Name / Location | Transport | Frames | Vehicles | Tracks w/ Plates | OCR Attempted | >=2 Hypotheses | Stable Consensus | Status |',
        '| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |',
    ]

    for cid in camera_ids:
        cam = get_camera(cid)
        if not cam:
            continue
        url, transport = resolve_stream(cam)
        if not url:
            continue

        cam_name = cam.get('name') or cam.get('location') or f'Camera {cid}'
        print(f'\n--- Testing Camera {cid} ({cam_name}) via {transport} ---')

        v_pipe = VehicleTrackingPipeline(detector=v_detector, sampling_interval_ms=150.0)
        p_pipe = PlateDetectionPipeline(plate_detector=p_detector, target_crop_width=960)
        reader = RTSPReader(url=url, camera_id=str(cid))

        cam_frames = 0
        active_track_ids = set()
        tracks_with_plates = set()
        tracks_ge2 = set()
        resolved_tracks = set()

        start_time = time.time()

        for packet in reader.packets():
            cam_frames += 1
            tracks = v_pipe.process(packet)
            plates = p_pipe.process(packet, tracks)

            for t in tracks:
                active_track_ids.add((packet.camera_id, packet.stream_epoch, t.track_id))

            for p in plates:
                trk_key = (p.camera_id, p.stream_epoch, p.track_id)
                tracks_with_plates.add(trk_key)

                h_f, w_f = packet.frame.shape[:2]
                px1 = max(0, int(p.x1))
                py1 = max(0, int(p.y1))
                px2 = min(w_f, int(p.x2))
                py2 = min(h_f, int(p.y2))

                if (px2 - px1) >= 16 and (py2 - py1) >= 8:
                    plate_crop = packet.frame[py1:py2, px1:px2].copy()
                    hyp = ocr_pipe.process_observation(p, plate_crop)

                    ev_path = EVIDENCE_DIR / f'cam_{cid}_trk_{p.track_id}_pts_{int(p.pts_ms)}.jpg'
                    cv2.imwrite(str(ev_path), plate_crop)

                    track_res = ocr_pipe.get_track_result(p.camera_id, p.stream_epoch, p.track_id)
                    if track_res.total_hypotheses >= 2:
                        tracks_ge2.add(trk_key)

                    if track_res.is_resolved:
                        resolved_tracks.add(trk_key)
                        txt_len = len(track_res.best_text) if track_res.best_text else 0
                        print(f'  [CONSENSUS RESOLVED] Cam {cid} Track #{p.track_id} -> Length: {txt_len} | Conf: {track_res.confidence:.2f} | Support: {track_res.support_count}/{track_res.total_hypotheses}')



            if cam_frames >= frames_per_camera:
                break

        elapsed = max(0.001, time.time() - start_time)
        status_str = f'Recorded {len(tracks_with_plates)} plate tracks ({len(resolved_tracks)} stable consensus)' if tracks_with_plates else 'No readable positive OCR opportunity observed'

        cam_res = {
            'camera_id': cid,
            'name': cam_name,
            'transport': transport,
            'frames': cam_frames,
            'vehicles_tracked': len(active_track_ids),
            'tracks_with_plates': len(tracks_with_plates),
            'tracks_ocr_attempted': len(tracks_with_plates),
            'tracks_with_ge2_hypotheses': len(tracks_ge2),
            'tracks_stable_consensus': len(resolved_tracks),
            'status': status_str,
            'elapsed_seconds': round(elapsed, 2),
        }

        overall_results['cameras_tested'].append(cam_res)
        overall_results['total_frames'] += cam_frames
        overall_results['total_vehicles_tracked'] += len(active_track_ids)
        overall_results['tracks_with_plate_observations'] += len(tracks_with_plates)
        overall_results['tracks_ocr_attempted'] += len(tracks_with_plates)
        overall_results['tracks_with_ge2_hypotheses'] += len(tracks_ge2)
        overall_results['tracks_stable_consensus'] += len(resolved_tracks)

        markdown_lines.append(
            f'| {cid} | {cam_name} | {transport} | {cam_frames} | {len(active_track_ids)} | {len(tracks_with_plates)} | {len(tracks_with_plates)} | {len(tracks_ge2)} | {len(resolved_tracks)} | {status_str} |'
        )

    with open(REPORT_DIR / 'production_validation_report.json', 'w', encoding='utf-8') as f:
        json.dump(overall_results, f, indent=2)

    with open(REPORT_DIR / 'production_validation_report.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_lines) + '\n')

    print('\n================ LIVE MULTI-CAMERA OCR VALIDATION SUMMARY ================')
    print(f"Total Cameras Tested:           {len(overall_results['cameras_tested'])}")
    print(f"Total Frames Processed:        {overall_results['total_frames']}")
    print(f"Total Vehicles Tracked:        {overall_results['total_vehicles_tracked']}")
    print(f"Tracks with Plate Obs:         {overall_results['tracks_with_plate_observations']}")
    print(f"Tracks with >=2 Hypotheses:    {overall_results['tracks_with_ge2_hypotheses']}")
    print(f"Tracks with Stable Consensus:  {overall_results['tracks_stable_consensus']}")
    print(f"Reports saved to: {REPORT_DIR}")
    print('==========================================================================\n')

    return overall_results


if __name__ == '__main__':
    run_live_ocr_validation(['1', '2', '3'], frames_per_camera=20)
