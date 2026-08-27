import os
import sys
import time
import json
import cv2
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib

db_mod = importlib.import_module('00_foundation.registry.database')
reader_mod = importlib.import_module('00_foundation.streams.reader')
res_mod = importlib.import_module('00_foundation.streams.resolver')
v_det_mod = importlib.import_module('01_vehicle_detection.detector')
v_track_mod = importlib.import_module('02_tracking.pipeline')
p_det_mod = importlib.import_module('03_plate_detection.detector')
p_pipe_mod = importlib.import_module('03_plate_detection.pipeline')
quality_mod = importlib.import_module('03_plate_detection.quality')

get_camera = db_mod.get_camera
RTSPReader = reader_mod.RTSPReader
resolve_stream = res_mod.resolve_stream
VehicleDetector = v_det_mod.VehicleDetector
VehicleTrackingPipeline = v_track_mod.VehicleTrackingPipeline
PlateDetector = p_det_mod.PlateDetector
PlateDetectionPipeline = p_pipe_mod.PlateDetectionPipeline
TrackPlateAccumulator = quality_mod.TrackPlateAccumulator

REPORT_DIR = ROOT_DIR / 'reports' / 'plate_detection'
EVIDENCE_DIR = REPORT_DIR / 'evidence'


def run_live_production_validation(camera_ids: list[str], frames_per_camera: int = 15):
    print(f'[VALIDATION] Initializing Production Multi-Camera Live Validation across cameras: {camera_ids}')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    v_detector = VehicleDetector(model_path='models/vehicle/yolo11m.pt', confidence=0.25, imgsz=960)
    p_detector = PlateDetector(model_path='models/plate/production/best.pt', confidence=0.20, imgsz=960)

    overall_results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'cameras_tested': [],
        'total_frames_processed': 0,
        'total_vehicles_tracked': 0,
        'total_plates_detected': 0,
    }

    now_str = time.strftime('%Y-%m-%d %H:%M:%S')
    markdown_lines = [
        '# Sentinel Live Multi-Camera Production Validation Report',
        f'**Generated:** {now_str}',
        '',
        '| Camera ID | Name / Location | Transport | Frames | Vehicles Tracked | Plates Detected | Status |',
        '| :--- | :--- | :--- | :--- | :--- | :--- | :--- |',
    ]

    for cid in camera_ids:
        cam = get_camera(cid)
        if not cam:
            print(f'[WARN] Camera {cid} not in registry, skipping.')
            continue

        url, transport = resolve_stream(cam)
        if not url:
            print(f'[WARN] No stream available for Camera {cid}, skipping.')
            continue

        cam_name = cam.get('name') or cam.get('location') or f'Camera {cid}'
        print(f'\n--- Testing Camera {cid} ({cam_name}) via {transport} ---')

        v_pipe = VehicleTrackingPipeline(detector=v_detector, sampling_interval_ms=150.0)
        p_pipe = PlateDetectionPipeline(plate_detector=p_detector, target_crop_width=960)
        accumulator = TrackPlateAccumulator(max_candidates_per_track=5)

        reader = RTSPReader(url=url, camera_id=str(cid))

        cam_frames = 0
        cam_plates = 0
        quality_scores = []
        track_ids_seen = set()

        start_time = time.time()

        for packet in reader.packets():
            cam_frames += 1
            tracks = v_pipe.process(packet)
            plates = p_pipe.process(packet, tracks)

            for t in tracks:
                track_ids_seen.add(t.track_id)

            for p in plates:
                accumulator.add(p)
                quality_scores.append(p.quality_score)
                cam_plates += 1

                # Save evidence crop if plate is detected
                evidence_img = packet.image.copy()
                cv2.rectangle(evidence_img, (int(p.x1), int(p.y1)), (int(p.x2), int(p.y2)), (0, 255, 0), 2)
                ev_name = f'cam_{cid}_track_{p.track_id}_frame_{cam_frames}.jpg'
                cv2.imwrite(str(EVIDENCE_DIR / ev_name), evidence_img)

            if cam_frames % 5 == 0 or len(plates) > 0:
                print(f'  Frame #{cam_frames:<2} | PTS: {packet.pts_ms:>7.1f}ms | Active Tracks: {len(tracks)} | Genuine Plates: {len(plates)}')
                for p in plates:
                    print(f'    -> Track #{p.track_id:<2} ({p.vehicle_class.upper()}) | Box: [{p.x1:.0f},{p.y1:.0f},{p.x2:.0f},{p.y2:.0f}] ({p.width:.0f}x{p.height:.0f}) | Aspect: {p.aspect_ratio:.2f} | Q: {p.quality_score:.2f}')

            if cam_frames >= frames_per_camera:
                break

        elapsed = max(0.001, time.time() - start_time)
        avg_q = (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0

        obs_status = "Positive plate detections recorded" if cam_plates > 0 else "No positive plate-validation opportunity observed (wide-angle/far view)"

        cam_summary = {
            'camera_id': cid,
            'name': cam_name,
            'transport': transport,
            'frames_processed': cam_frames,
            'unique_vehicles_tracked': len(track_ids_seen),
            'plates_detected': cam_plates,
            'average_quality_score': round(avg_q, 3),
            'status': obs_status,
            'elapsed_seconds': round(elapsed, 2),
            'fps': round(cam_frames / elapsed, 2),
        }

        overall_results['cameras_tested'].append(cam_summary)
        overall_results['total_frames_processed'] += cam_frames
        overall_results['total_vehicles_tracked'] += len(track_ids_seen)
        overall_results['total_plates_detected'] += cam_plates

        markdown_lines.append(
            f'| {cid} | {cam_name} | {transport} | {cam_frames} | {len(track_ids_seen)} | {cam_plates} | {obs_status} |'
        )

    # Save JSON & Markdown reports
    json_path = REPORT_DIR / 'production_validation_report.json'
    md_path = REPORT_DIR / 'production_validation_report.md'

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(overall_results, f, indent=2)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_lines) + '\n')

    print('\n================ MULTI-CAMERA LIVE PRODUCTION VALIDATION SUMMARY ================')
    print(f"Total Cameras Tested: {len(overall_results['cameras_tested'])}")
    print(f"Total Frames: {overall_results['total_frames_processed']}")
    print(f"Total Unique Vehicles Tracked: {overall_results['total_vehicles_tracked']}")
    print(f"Total Plates Detected: {overall_results['total_plates_detected']}")
    print(f"Report written to: {json_path} and {md_path}")
    print('=================================================================================\n')


if __name__ == '__main__':
    run_live_production_validation(['1', '2', '3'], frames_per_camera=12)
