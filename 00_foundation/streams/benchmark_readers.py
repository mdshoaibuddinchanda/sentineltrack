import time
import json
import cv2
import importlib
import numpy as np
from pathlib import Path

tools_bm = importlib.import_module('tools.benchmarking')
benchmark_callable = tools_bm.benchmark_callable

p0_reader = importlib.import_module('00_foundation.streams.reader')
p0_pyav = importlib.import_module('00_foundation.streams.pyav_reader')

RTSPReader = p0_reader.RTSPReader
PyAVReader = p0_pyav.PyAVReader

VIDEO_PATH = str(Path('reports/system_optimization/p0_ingestion/test_synthetic_stream.mp4').resolve())
REPORTS_P0 = Path('reports/system_optimization/p0_ingestion')


def benchmark_opencv_stream():
    reader = RTSPReader(url=VIDEO_PATH, camera_id='cam_test_cv')
    packets = []
    t0 = time.perf_counter()
    gen = reader.packets()
    first_frame_ms = None
    for p in gen:
        if first_frame_ms is None:
            first_frame_ms = (time.perf_counter() - t0) * 1000.0
        packets.append(p)
        if len(packets) >= 100:
            break
    total_time_s = time.perf_counter() - t0

    pts_list = [p.pts_ms for p in packets]
    is_monotonic = all(pts_list[i] <= pts_list[i + 1] for i in range(len(pts_list) - 1))

    return {
        'reader': 'OpenCV (cv2.VideoCapture)',
        'frames_decoded': len(packets),
        'total_time_s': round(total_time_s, 4),
        'fps': round(len(packets) / max(total_time_s, 1e-6), 2),
        'first_frame_latency_ms': round(first_frame_ms or 0.0, 2),
        'pts_monotonic': is_monotonic,
        'first_pts_ms': round(pts_list[0] if pts_list else 0.0, 2),
        'last_pts_ms': round(pts_list[-1] if pts_list else 0.0, 2)
    }


def benchmark_pyav_stream():
    reader = PyAVReader(url=VIDEO_PATH, camera_id='cam_test_av')
    packets = []
    t0 = time.perf_counter()
    gen = reader.packets()
    first_frame_ms = None
    for p in gen:
        if first_frame_ms is None:
            first_frame_ms = (time.perf_counter() - t0) * 1000.0
        packets.append(p)
        if len(packets) >= 100:
            break
    total_time_s = time.perf_counter() - t0

    pts_list = [p.pts_ms for p in packets]
    is_monotonic = all(pts_list[i] <= pts_list[i + 1] for i in range(len(pts_list) - 1))

    return {
        'reader': 'PyAV (libav Direct PTS)',
        'frames_decoded': len(packets),
        'total_time_s': round(total_time_s, 4),
        'fps': round(len(packets) / max(total_time_s, 1e-6), 2),
        'first_frame_latency_ms': round(first_frame_ms or 0.0, 2),
        'pts_monotonic': is_monotonic,
        'first_pts_ms': round(pts_list[0] if pts_list else 0.0, 2),
        'last_pts_ms': round(pts_list[-1] if pts_list else 0.0, 2)
    }


def run():
    print('============================================================')
    print('BENCHMARKING P0 STREAM READERS (OpenCV vs PyAV)')
    print('============================================================')
    cv_res = benchmark_opencv_stream()
    av_res = benchmark_pyav_stream()

    print('OpenCV Result:', cv_res)
    print('PyAV Result:  ', av_res)

    results = {
        'opencv_reader': cv_res,
        'pyav_reader': av_res
    }
    with open(REPORTS_P0 / 'reader_benchmark.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print('Saved reader benchmark to reports/system_optimization/p0_ingestion/reader_benchmark.json')


if __name__ == '__main__':
    run()
