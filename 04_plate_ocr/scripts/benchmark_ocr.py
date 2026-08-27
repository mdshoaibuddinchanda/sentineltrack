import sys
import csv
import time
import cv2
import importlib
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
eval_mod = importlib.import_module('04_plate_ocr.training.evaluate')

get_recognizer = rec_mod.get_recognizer
load_split_dataset = eval_mod.load_split_dataset
calculate_metrics = eval_mod.calculate_metrics

REPORT_DIR = ROOT_DIR / 'reports' / 'plate_ocr' / 'benchmarks'


def compare_recognizers(sample_limit: int = 50):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    val_items = load_split_dataset('val')[:sample_limit]
    print(f'[ENGINE COMPARISON] Comparing OCR engines on {len(val_items)} validation plate crops...')

    engines = ['easyocr_crnn', 'mock_rec']
    comparison_rows = []

    for eng in engines:
        print(f'\n--- Benchmarking Engine: {eng} ---')
        rec = get_recognizer(eng, device='cuda')

        preds = []
        gts = []
        latencies = []

        # Warm up
        if val_items:
            rec.recognize(val_items[0][0])

        for img, gt, _ in val_items:
            t0 = time.perf_counter()
            raw_t, conf, _ = rec.recognize(img)
            lat = (time.perf_counter() - t0) * 1000

            preds.append(raw_t)
            gts.append(gt)
            latencies.append(lat)

        metrics = calculate_metrics(preds, gts)
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))
        throughput = len(val_items) / (sum(latencies) / 1000.0) if latencies else 0.0

        row = {
            'engine': eng,
            'exact_accuracy': metrics['exact_accuracy'],
            'character_accuracy': metrics['character_accuracy'],
            'cer': metrics['cer'],
            'p50_latency_ms': round(p50, 2),
            'p95_latency_ms': round(p95, 2),
            'throughput_crops_per_sec': round(throughput, 2),
            'device': 'CUDA (RTX 3050)' if eng != 'mock_rec' else 'CPU',
        }
        comparison_rows.append(row)
        print(f"  Exact Acc: {row['exact_accuracy']*100:.2f}% | Char Acc: {row['character_accuracy']*100:.2f}% | P50: {row['p50_latency_ms']}ms | Throughput: {row['throughput_crops_per_sec']} crops/s")

    csv_path = REPORT_DIR / 'recognizer_comparison.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_rows)

    print(f'\n[SUCCESS] Engine comparison report written to: {csv_path}')
    return comparison_rows


if __name__ == '__main__':
    compare_recognizers(50)
