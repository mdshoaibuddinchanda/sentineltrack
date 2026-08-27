import csv
import json
import time
import cv2
import importlib
import numpy as np
from pathlib import Path

tools_bm = importlib.import_module('tools.benchmarking')
benchmark_callable = tools_bm.benchmark_callable

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
get_recognizer = rec_mod.get_recognizer

gram_mod = importlib.import_module('04_plate_ocr.grammar')
generate_grammar_alternatives = gram_mod.generate_grammar_alternatives
normalize_plate_text = importlib.import_module('04_plate_ocr.normalization').normalize_plate_text

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_P4 = Path('reports/system_optimization/p4_ocr')
REPORTS_P4.mkdir(parents=True, exist_ok=True)


def run_p4_benchmarks():
    print('============================================================')
    print('BENCHMARKING P4 OCR (PP-OCRv5 Mobile ONNX Optimization)')
    print('============================================================')

    recognizer = get_recognizer('ppocr_mobile', device='cpu')
    print(f'Active Provider: {recognizer.active_provider}')

    # Load 50 real validation crops
    sources_p = ROOT_DIR / 'datasets' / 'plate_ocr' / 'sources.csv'
    crops = []
    ground_truths = []

    if sources_p.exists():
        with open(sources_p, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get('split') == 'val':
                    fn = r.get('filename', '')
                    gt = r.get('plate_text', '').strip().replace(' ', '').upper()
                    img_p = ROOT_DIR / 'datasets' / 'plate_ocr' / 'images' / 'val' / fn
                    if img_p.exists():
                        img = cv2.imread(str(img_p))
                        if img is not None and img.size > 0:
                            crops.append(img)
                            ground_truths.append(gt)
                            if len(crops) >= 50:
                                break

    if not crops:
        crops = [np.random.randint(0, 255, (48, 160, 3), dtype=np.uint8) for _ in range(50)]
        ground_truths = ['MH12DE1432'] * 50

    results = {}

    # 1. Batch Sweep (B1 vs B2 vs B4 on CPU)
    print('\n1. OCR Batch Inference Sweep (B1 vs B2 vs B4)...')
    sample_crop = crops[0]
    for b in [1, 2, 4]:
        batch_crops = [sample_crop] * b
        res = benchmark_callable(
            f'ppocr_mobile_batch_{b}',
            lambda: recognizer.recognize_batch(batch_crops),
            warm_up=5,
            iterations=30,
            batch_size=b,
            device='cpu'
        )
        results[f'batch_{b}'] = res.to_dict()
        print(f'  Batch {b}: P50={res.p50_ms}ms, P95={res.p95_ms}ms, Throughput={res.throughput_fps} FPS, Per-Crop P50={round(res.p50_ms / b, 2)}ms')

    # 2. Alternative Quality Top-K Analysis
    print('\n2. Evaluating OCR Alternative Quality (Top-1 vs Top-3 vs Top-5 Recall)...')
    top1_correct = 0
    top3_correct = 0
    top5_correct = 0

    for crop, gt in zip(crops, ground_truths):
        txt, conf, _ = recognizer.recognize(crop)
        norm_txt = normalize_plate_text(txt)
        alts = generate_grammar_alternatives(norm_txt, max_candidates=5)
        alt_texts = [normalize_plate_text(a[0]) for a in alts]

        if norm_txt == gt:
            top1_correct += 1
        if gt in alt_texts[:3]:
            top3_correct += 1
        if gt in alt_texts[:5]:
            top5_correct += 1

    total_samples = len(crops)
    results['alternative_quality'] = {
        'total_evaluated': total_samples,
        'top1_exact_accuracy': round(top1_correct / total_samples, 4),
        'top3_recall': round(top3_correct / total_samples, 4),
        'top5_recall': round(top5_correct / total_samples, 4)
    }
    aq = results['alternative_quality']
    top1_p = aq['top1_exact_accuracy'] * 100
    top3_p = aq['top3_recall'] * 100
    top5_p = aq['top5_recall'] * 100
    print(f'  Top-1 Exact Accuracy: {top1_p:.2f}%')
    print(f'  Top-3 Candidate Recall: {top3_p:.2f}%')
    print(f'  Top-5 Candidate Recall: {top5_p:.2f}%')

    out_p = REPORTS_P4 / 'ocr_benchmarks.json'
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f'\nSaved P4 benchmarks to {out_p}')


if __name__ == '__main__':
    run_p4_benchmarks()
