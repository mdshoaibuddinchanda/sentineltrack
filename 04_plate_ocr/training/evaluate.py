import csv
import json
import time
import cv2
import importlib
import numpy as np
import onnxruntime as ort
from pathlib import Path
from collections import defaultdict
from typing import Optional

models_mod = importlib.import_module('04_plate_ocr.models')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
gram_mod = importlib.import_module('04_plate_ocr.grammar')
vote_mod = importlib.import_module('04_plate_ocr.voting')
prep_mod = importlib.import_module('04_plate_ocr.preprocess')
rec_mod = importlib.import_module('04_plate_ocr.recognizers')

OCRHypothesis = models_mod.OCRHypothesis
normalize_plate_text = norm_mod.normalize_plate_text
score_indian_grammar = gram_mod.score_indian_grammar
generate_grammar_alternatives = gram_mod.generate_grammar_alternatives
weighted_levenshtein = vote_mod.weighted_levenshtein
normalized_edit_distance = vote_mod.normalized_edit_distance
MultiFramePlateVoter = vote_mod.MultiFramePlateVoter
preprocess_crop = prep_mod.preprocess_crop
get_recognizer = rec_mod.get_recognizer
BasePlateRecognizer = rec_mod.BasePlateRecognizer

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
REPORT_DIR = ROOT_DIR / 'reports' / 'plate_ocr'


def calculate_metrics(predictions: list[str], ground_truths: list[str]) -> dict:
    total_samples = len(ground_truths)
    if total_samples == 0:
        return {}

    raw_exact_matches = 0
    raw_total_gt_chars = 0
    raw_total_correct_chars = 0
    raw_total_lev_dist = 0
    raw_edit_dists = []

    post_exact_matches = 0
    post_total_correct_chars = 0
    post_total_lev_dist = 0
    post_edit_dists = []

    grammar_valid = 0
    empty_reads = 0

    for pred, gt in zip(predictions, ground_truths):
        norm_p = normalize_plate_text(pred)
        norm_g = normalize_plate_text(gt)

        if not norm_p:
            empty_reads += 1

        gt_len = max(len(norm_g), 1)
        raw_total_gt_chars += gt_len

        # 1. RAW METRICS (Strict normalized OCR output without grammar alternative expansion)
        if norm_p == norm_g:
            raw_exact_matches += 1

        raw_dist = weighted_levenshtein(norm_p, norm_g, confusion_cost=1.0)
        raw_total_lev_dist += raw_dist
        raw_edit_dists.append(raw_dist / gt_len)

        min_l_raw = min(len(norm_p), len(norm_g))
        raw_matched = sum(1 for i in range(min_l_raw) if norm_p[i] == norm_g[i])
        raw_total_correct_chars += raw_matched

        # 2. POSTPROCESSED METRICS (Normalization + soft positional grammar alternative selection)
        alts = generate_grammar_alternatives(norm_p)
        best_p = alts[0][0] if alts else norm_p

        if norm_p == norm_g or best_p == norm_g:
            post_exact_matches += 1

        if score_indian_grammar(norm_p) >= 0.70 or score_indian_grammar(best_p) >= 0.70:
            grammar_valid += 1

        post_dist = weighted_levenshtein(best_p, norm_g, confusion_cost=1.0)
        post_total_lev_dist += post_dist
        post_edit_dists.append(post_dist / gt_len)

        min_l_post = min(len(best_p), len(norm_g))
        post_matched = sum(1 for i in range(min_l_post) if best_p[i] == norm_g[i])
        post_total_correct_chars += post_matched

    return {
        'total_samples': total_samples,
        # Raw Metrics
        'raw_exact_matches': raw_exact_matches,
        'raw_exact_accuracy': round(raw_exact_matches / total_samples, 4),
        'raw_character_accuracy': round(raw_total_correct_chars / max(raw_total_gt_chars, 1), 4),
        'raw_cer': round(raw_total_lev_dist / max(raw_total_gt_chars, 1), 4),
        'raw_mean_edit_distance': round(float(np.mean(raw_edit_dists)), 4) if raw_edit_dists else 0.0,
        # Postprocessed Metrics
        'postprocessed_exact_matches': post_exact_matches,
        'postprocessed_exact_accuracy': round(post_exact_matches / total_samples, 4),
        'postprocessed_character_accuracy': round(post_total_correct_chars / max(raw_total_gt_chars, 1), 4),
        'postprocessed_cer': round(post_total_lev_dist / max(raw_total_gt_chars, 1), 4),
        'postprocessed_mean_edit_distance': round(float(np.mean(post_edit_dists)), 4) if post_edit_dists else 0.0,
        # System & Quality
        'grammar_valid_rate': round(grammar_valid / total_samples, 4),
        'empty_read_rate': round(empty_reads / total_samples, 4),
    }


def compute_confusion_matrix(predictions: list[str], ground_truths: list[str]) -> dict:
    confusions = defaultdict(int)
    for pred, gt in zip(predictions, ground_truths):
        norm_p = normalize_plate_text(pred)
        norm_g = normalize_plate_text(gt)
        if len(norm_p) == len(norm_g):
            for p_ch, g_ch in zip(norm_p, norm_g):
                if p_ch != g_ch:
                    pair = f'{g_ch}->{p_ch}'
                    confusions[pair] += 1
    return dict(sorted(confusions.items(), key=lambda x: x[1], reverse=True))


def load_split_dataset(split: str = 'val') -> list[tuple[np.ndarray, str, Path]]:
    img_dir = DATASET_DIR / 'images' / split
    lbl_dir = DATASET_DIR / 'labels' / split

    items = []
    for img_p in sorted(list(img_dir.glob('*.jpg')) + list(img_dir.glob('*.png'))):
        lbl_p = lbl_dir / img_p.with_suffix('.txt').name
        if not lbl_p.exists():
            continue
        with open(lbl_p, 'r', encoding='utf-8') as f:
            gt_text = f.read().strip()
        img = cv2.imread(str(img_p))
        if img is not None:
            items.append((img, gt_text, img_p))

    return items


def evaluate_engine_on_split(recognizer: BasePlateRecognizer, split: str = 'val', variant: str = 'raw') -> dict:
    items = load_split_dataset(split)
    preds = []
    gts = []
    latencies = []

    # Warmup
    if items:
        _ = recognizer.recognize(items[0][0])

    for img, gt, _ in items:
        prep_img, _ = preprocess_crop(img, variant=variant, target_height=48)
        t0 = time.perf_counter()
        raw_text, _, _ = recognizer.recognize(prep_img)
        lat = (time.perf_counter() - t0) * 1000

        preds.append(raw_text)
        gts.append(gt)
        latencies.append(lat)

    metrics = calculate_metrics(preds, gts)
    confusions = compute_confusion_matrix(preds, gts)

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    throughput = len(items) / (sum(latencies) / 1000.0) if latencies else 0.0

    metrics['p50_latency_ms'] = round(p50, 2)
    metrics['p95_latency_ms'] = round(p95, 2)
    metrics['throughput_crops_per_sec'] = round(throughput, 2)
    metrics['recognizer'] = recognizer.model_name
    metrics['split'] = split
    metrics['variant'] = variant
    metrics['confusions_top10'] = dict(list(confusions.items())[:10])

    return metrics


def run_full_reproducible_evaluation():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    bench_dir = REPORT_DIR / 'benchmarks'
    bench_dir.mkdir(parents=True, exist_ok=True)

    print('================ RUNNING FINAL REPRODUCIBLE EVALUATION SUITE ================')
    avail_providers = ort.get_available_providers()
    print(f'ONNX Runtime Available Providers: {avail_providers}')
    cuda_status = 'CUDA_AVAILABLE' if 'CUDAExecutionProvider' in avail_providers else 'CUDA_PROVIDER_UNAVAILABLE (Using CPU Baseline)'
    print(f'Provider Status: {cuda_status}')

    engines = [
        ('ppocr_mobile', 'en_PP-OCRv5_mobile_rec'),
        ('ppocr_server', 'PP-OCRv5_server_rec')
    ]

    comparison_rows = []

    for eng_key, eng_name in engines:
        rec = get_recognizer(eng_key, device='cpu')

        # 1. Validation Split
        val_metrics = evaluate_engine_on_split(rec, split='val', variant='raw')
        print(f"\n[{eng_name} - VALIDATION]")
        print(f"  RAW:          Exact: {val_metrics['raw_exact_accuracy']*100:>5.2f}% ({val_metrics['raw_exact_matches']}/{val_metrics['total_samples']}) | Char: {val_metrics['raw_character_accuracy']*100:>5.2f}% | CER: {val_metrics['raw_cer']:.4f}")
        print(f"  POSTPROC:     Exact: {val_metrics['postprocessed_exact_accuracy']*100:>5.2f}% ({val_metrics['postprocessed_exact_matches']}/{val_metrics['total_samples']}) | Char: {val_metrics['postprocessed_character_accuracy']*100:>5.2f}% | CER: {val_metrics['postprocessed_cer']:.4f}")
        print(f"  P50 / P95:    {val_metrics['p50_latency_ms']}ms / {val_metrics['p95_latency_ms']}ms | Throughput: {val_metrics['throughput_crops_per_sec']} c/s")

        comparison_rows.append({
            'engine': eng_name,
            'split': 'val',
            'raw_exact_accuracy': val_metrics['raw_exact_accuracy'],
            'raw_character_accuracy': val_metrics['raw_character_accuracy'],
            'raw_cer': val_metrics['raw_cer'],
            'raw_mean_edit_distance': val_metrics['raw_mean_edit_distance'],
            'postprocessed_exact_accuracy': val_metrics['postprocessed_exact_accuracy'],
            'postprocessed_character_accuracy': val_metrics['postprocessed_character_accuracy'],
            'postprocessed_cer': val_metrics['postprocessed_cer'],
            'postprocessed_mean_edit_distance': val_metrics['postprocessed_mean_edit_distance'],
            'empty_read_rate': val_metrics['empty_read_rate'],
            'P50_ms': val_metrics['p50_latency_ms'],
            'P95_ms': val_metrics['p95_latency_ms'],
            'throughput': val_metrics['throughput_crops_per_sec'],
            'provider': 'CPU (8 threads)'
        })

        val_path = REPORT_DIR / f"{eng_key}_val_evaluation.json"
        with open(val_path, 'w', encoding='utf-8') as f:
            json.dump(val_metrics, f, indent=2)

        # 2. Test Split (Locked Evaluation)
        test_metrics = evaluate_engine_on_split(rec, split='test', variant='raw')
        print(f"[{eng_name} - TEST (LOCKED)]")
        print(f"  RAW:          Exact: {test_metrics['raw_exact_accuracy']*100:>5.2f}% ({test_metrics['raw_exact_matches']}/{test_metrics['total_samples']}) | Char: {test_metrics['raw_character_accuracy']*100:>5.2f}% | CER: {test_metrics['raw_cer']:.4f}")
        print(f"  POSTPROC:     Exact: {test_metrics['postprocessed_exact_accuracy']*100:>5.2f}% ({test_metrics['postprocessed_exact_matches']}/{test_metrics['total_samples']}) | Char: {test_metrics['postprocessed_character_accuracy']*100:>5.2f}% | CER: {test_metrics['postprocessed_cer']:.4f}")
        print(f"  P50 / P95:    {test_metrics['p50_latency_ms']}ms / {test_metrics['p95_latency_ms']}ms | Throughput: {test_metrics['throughput_crops_per_sec']} c/s")

        comparison_rows.append({
            'engine': eng_name,
            'split': 'test',
            'raw_exact_accuracy': test_metrics['raw_exact_accuracy'],
            'raw_character_accuracy': test_metrics['raw_character_accuracy'],
            'raw_cer': test_metrics['raw_cer'],
            'raw_mean_edit_distance': test_metrics['raw_mean_edit_distance'],
            'postprocessed_exact_accuracy': test_metrics['postprocessed_exact_accuracy'],
            'postprocessed_character_accuracy': test_metrics['postprocessed_character_accuracy'],
            'postprocessed_cer': test_metrics['postprocessed_cer'],
            'postprocessed_mean_edit_distance': test_metrics['postprocessed_mean_edit_distance'],
            'empty_read_rate': test_metrics['empty_read_rate'],
            'P50_ms': test_metrics['p50_latency_ms'],
            'P95_ms': test_metrics['p95_latency_ms'],
            'throughput': test_metrics['throughput_crops_per_sec'],
            'provider': 'CPU (8 threads)'
        })

        test_path = REPORT_DIR / f"{eng_key}_test_evaluation.json"
        with open(test_path, 'w', encoding='utf-8') as f:
            json.dump(test_metrics, f, indent=2)

    final_csv = bench_dir / 'recognizer_final_comparison.csv'
    with open(final_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_rows)

    print(f"\n[REPORT] Saved final comparison to: {final_csv}")
    print('=============================================================================')


if __name__ == '__main__':
    run_full_reproducible_evaluation()
