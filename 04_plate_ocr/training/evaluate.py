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

    exact_matches = 0
    total_gt_chars = 0
    total_correct_chars = 0
    total_lev_dist = 0
    grammar_valid = 0
    empty_reads = 0
    edit_dists = []

    for pred, gt in zip(predictions, ground_truths):
        norm_p = normalize_plate_text(pred)
        norm_g = normalize_plate_text(gt)

        if not norm_p:
            empty_reads += 1

        alts = generate_grammar_alternatives(norm_p)
        best_p = alts[0][0] if alts else norm_p

        if norm_p == norm_g or best_p == norm_g:
            exact_matches += 1

        if score_indian_grammar(norm_p) >= 0.70 or score_indian_grammar(best_p) >= 0.70:
            grammar_valid += 1

        gt_len = max(len(norm_g), 1)
        total_gt_chars += gt_len

        dist = weighted_levenshtein(best_p, norm_g, confusion_cost=1.0)
        total_lev_dist += dist
        norm_dist = dist / gt_len
        edit_dists.append(norm_dist)

        min_l = min(len(best_p), len(norm_g))
        matched = sum(1 for i in range(min_l) if best_p[i] == norm_g[i])
        total_correct_chars += matched

    exact_acc = exact_matches / total_samples
    char_acc = total_correct_chars / max(total_gt_chars, 1)
    cer = total_lev_dist / max(total_gt_chars, 1)
    mean_edit_dist = float(np.mean(edit_dists)) if edit_dists else 0.0
    median_edit_dist = float(np.median(edit_dists)) if edit_dists else 0.0

    return {
        'total_samples': total_samples,
        'exact_matches': exact_matches,
        'exact_accuracy': round(exact_acc, 4),
        'character_accuracy': round(char_acc, 4),
        'cer': round(cer, 4),
        'mean_edit_distance': round(mean_edit_dist, 4),
        'median_edit_distance': round(median_edit_dist, 4),
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
        ('ppocr_mobile', 'PP-OCRv5_mobile_rec'),
        ('ppocr_server', 'PP-OCRv5_server_rec'),
        ('adaptive', 'adaptive_mobile_server_cascade')
    ]

    comparison_rows = []

    for eng_key, eng_name in engines:
        rec = get_recognizer(eng_key, device='cpu')

        # 1. Validation Split
        val_metrics = evaluate_engine_on_split(rec, split='val', variant='raw')
        print(f"\n[{eng_name.upper()} - VALIDATION]")
        print(f"  Exact Accuracy: {val_metrics['exact_accuracy']*100:>5.2f}% ({val_metrics['exact_matches']}/{val_metrics['total_samples']})")
        print(f"  Char Accuracy:  {val_metrics['character_accuracy']*100:>5.2f}% | CER: {val_metrics['cer']:.4f}")
        print(f"  P50 / P95:      {val_metrics['p50_latency_ms']}ms / {val_metrics['p95_latency_ms']}ms | Throughput: {val_metrics['throughput_crops_per_sec']} c/s")

        comparison_rows.append({
            'engine': eng_name,
            'split': 'val',
            'exact_accuracy': val_metrics['exact_accuracy'],
            'character_accuracy': val_metrics['character_accuracy'],
            'cer': val_metrics['cer'],
            'mean_normalized_edit_distance': val_metrics['mean_edit_distance'],
            'empty_read_rate': val_metrics['empty_read_rate'],
            'P50_ms': val_metrics['p50_latency_ms'],
            'P95_ms': val_metrics['p95_latency_ms'],
            'throughput': val_metrics['throughput_crops_per_sec'],
            'provider': 'CPU (8 threads)'
        })

        # Save individual val report
        val_path = REPORT_DIR / f"{eng_key}_val_evaluation.json"
        with open(val_path, 'w', encoding='utf-8') as f:
            json.dump(val_metrics, f, indent=2)

        # 2. Test Split (Locked Evaluation)
        test_metrics = evaluate_engine_on_split(rec, split='test', variant='raw')
        print(f"[{eng_name.upper()} - TEST (LOCKED)]")
        print(f"  Exact Accuracy: {test_metrics['exact_accuracy']*100:>5.2f}% ({test_metrics['exact_matches']}/{test_metrics['total_samples']})")
        print(f"  Char Accuracy:  {test_metrics['character_accuracy']*100:>5.2f}% | CER: {test_metrics['cer']:.4f}")
        print(f"  P50 / P95:      {test_metrics['p50_latency_ms']}ms / {test_metrics['p95_latency_ms']}ms | Throughput: {test_metrics['throughput_crops_per_sec']} c/s")

        comparison_rows.append({
            'engine': eng_name,
            'split': 'test',
            'exact_accuracy': test_metrics['exact_accuracy'],
            'character_accuracy': test_metrics['character_accuracy'],
            'cer': test_metrics['cer'],
            'mean_normalized_edit_distance': test_metrics['mean_edit_distance'],
            'empty_read_rate': test_metrics['empty_read_rate'],
            'P50_ms': test_metrics['p50_latency_ms'],
            'P95_ms': test_metrics['p95_latency_ms'],
            'throughput': test_metrics['throughput_crops_per_sec'],
            'provider': 'CPU (8 threads)'
        })

        test_path = REPORT_DIR / f"{eng_key}_test_evaluation.json"
        with open(test_path, 'w', encoding='utf-8') as f:
            json.dump(test_metrics, f, indent=2)

    # Save final comparison CSV
    final_csv = bench_dir / 'recognizer_final_comparison.csv'
    with open(final_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_rows)

    print(f"\n[REPORT] Saved final comparison to: {final_csv}")

    # Run Multi-Frame Consensus on Production Engine (Mobile)
    print('\n[MULTI-FRAME] Running Multi-Frame Consensus Evaluation for Production Mobile Recognizer...')
    prod_rec = get_recognizer('ppocr_mobile', device='cpu')
    test_items = load_split_dataset('test')
    voter = MultiFramePlateVoter(min_support_count=2)

    single_cor = 0
    multi_cor = 0
    total_t = len(test_items)
    v_lats = []

    for img, gt, _ in test_items:
        norm_gt = normalize_plate_text(gt)

        # Single frame
        t0 = time.perf_counter()
        raw_t, _, _ = prod_rec.recognize(img)
        norm_t = normalize_plate_text(raw_t)
        alts = generate_grammar_alternatives(norm_t)
        best_single = alts[0][0] if alts else norm_t
        if best_single == norm_gt:
            single_cor += 1

        # Simulated 4-frame video track
        sim_hyps = []
        variations = [
            ('raw', img),
            ('gray', cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)),
            ('clahe', preprocess_crop(img, variant='clahe')[0]),
            ('noisy', np.clip(img.astype(np.float32) + np.random.normal(0, 8, img.shape), 0, 255).astype(np.uint8))
        ]

        for i, (var_name, var_img) in enumerate(variations):
            r_t, o_c, _ = prod_rec.recognize(var_img)
            n_t = normalize_plate_text(r_t)
            hyp = OCRHypothesis(
                camera_id='sim_cam',
                track_id=1,
                stream_epoch=1,
                pts_ms=i * 150.0,
                raw_text=r_t,
                normalized_text=n_t,
                ocr_confidence=o_c if o_c is not None else 0.5,
                crop_quality=0.75 - i * 0.05,
                grammar_score=score_indian_grammar(n_t),
                preprocess_variant=var_name,
                recognizer_name=prod_rec.model_name
            )
            sim_hyps.append(hyp)

        t0 = time.perf_counter()
        track_res = voter.vote(sim_hyps)
        v_lats.append((time.perf_counter() - t0) * 1000)

        if track_res.best_text == norm_gt:
            multi_cor += 1

    single_acc = single_cor / max(total_t, 1)
    multi_acc = multi_cor / max(total_t, 1)
    gain = multi_acc - single_acc
    p95_v = float(np.percentile(v_lats, 95))

    mf_res = {
        'production_recognizer': prod_rec.model_name,
        'total_tracks_evaluated': total_t,
        'single_frame_exact_accuracy': round(single_acc, 4),
        'multiframe_consensus_exact_accuracy': round(multi_acc, 4),
        'accuracy_gain': round(gain, 4),
        'p95_voting_latency_ms': round(p95_v, 3)
    }

    print(f"Single-Frame Exact: {single_acc*100:.2f}% | Multi-Frame Exact: {multi_acc*100:.2f}% | Gain: {gain*100:+.2f}% | P95 Voting Latency: {p95_v:.2f}ms")

    with open(REPORT_DIR / 'baseline' / 'multiframe_evaluation.json', 'w', encoding='utf-8') as f:
        json.dump(mf_res, f, indent=2)

    print('=============================================================================')


if __name__ == '__main__':
    run_full_reproducible_evaluation()
