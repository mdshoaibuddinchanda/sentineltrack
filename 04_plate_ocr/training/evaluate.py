import csv
import json
import time
import cv2
import importlib
import numpy as np
from pathlib import Path
from collections import defaultdict

models_mod = importlib.import_module('04_plate_ocr.models')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
gram_mod = importlib.import_module('04_plate_ocr.grammar')
vote_mod = importlib.import_module('04_plate_ocr.voting')
prep_mod = importlib.import_module('04_plate_ocr.preprocess')
rec_mod = importlib.import_module('04_plate_ocr.recognizers')

OCRHypothesis = models_mod.OCRHypothesis
normalize_plate_text = norm_mod.normalize_plate_text
score_indian_grammar = gram_mod.score_indian_grammar
weighted_levenshtein = vote_mod.weighted_levenshtein
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
    edit_dists = []

    for pred, gt in zip(predictions, ground_truths):
        norm_p = normalize_plate_text(pred)
        norm_g = normalize_plate_text(gt)

        if norm_p == norm_g:
            exact_matches += 1

        if score_indian_grammar(norm_p) >= 0.70:
            grammar_valid += 1

        gt_len = max(len(norm_g), 1)
        total_gt_chars += gt_len

        dist = weighted_levenshtein(norm_p, norm_g, confusion_cost=1.0)
        total_lev_dist += dist
        norm_dist = dist / gt_len
        edit_dists.append(norm_dist)

        min_l = min(len(norm_p), len(norm_g))
        matched = sum(1 for i in range(min_l) if norm_p[i] == norm_g[i])
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


def run_preprocessing_ablation(recognizer: BasePlateRecognizer) -> dict:
    print('\n[ABLATION] Running Preprocessing Variant Study on 100% Real Validation Set...')
    val_items = load_split_dataset('val')
    variants = ['raw', 'gray', 'clahe', 'sharpen', 'rectify']
    ablation_results = []

    for var in variants:
        preds = []
        gts = []
        latencies = []

        for img, gt, _ in val_items:
            t0 = time.perf_counter()
            prep_img, _ = preprocess_crop(img, variant=var)
            t_prep = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            raw_text, _, _ = recognizer.recognize(prep_img)
            t_ocr = (time.perf_counter() - t0) * 1000

            preds.append(raw_text)
            gts.append(gt)
            latencies.append(t_prep + t_ocr)

        metrics = calculate_metrics(preds, gts)
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))

        res = {
            'variant': var,
            'exact_accuracy': metrics['exact_accuracy'],
            'character_accuracy': metrics['character_accuracy'],
            'cer': metrics['cer'],
            'p50_latency_ms': round(p50, 2),
            'p95_latency_ms': round(p95, 2),
        }
        ablation_results.append(res)
        print(f"  Variant: {var:<8} | Exact Acc: {metrics['exact_accuracy']*100:>5.2f}% | Char Acc: {metrics['character_accuracy']*100:>5.2f}% | CER: {metrics['cer']:.4f} | P50: {p50:>5.1f}ms")

    out_csv = REPORT_DIR / 'ablations' / 'preprocessing.csv'
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(ablation_results[0].keys()))
        writer.writeheader()
        writer.writerows(ablation_results)

    return ablation_results


def run_full_evaluation(recognizer: BasePlateRecognizer, split: str = 'test', variant: str = 'raw') -> dict:
    print(f'\n[EVALUATION] Evaluating {recognizer.model_name} on 100% Real {split.upper()} Set ({variant} variant)...')
    items = load_split_dataset(split)
    preds = []
    gts = []
    latencies = []

    for img, gt, _ in items:
        prep_img, _ = preprocess_crop(img, variant=variant)
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
    metrics['p50_latency_ms'] = round(p50, 2)
    metrics['p95_latency_ms'] = round(p95, 2)
    metrics['recognizer'] = recognizer.model_name
    metrics['split'] = split
    metrics['variant'] = variant
    metrics['confusions_top10'] = dict(list(confusions.items())[:10])

    print(f"================ {split.upper()} SET EVALUATION RESULTS ================")
    print(f"Recognizer:         {recognizer.model_name}")
    print(f"Images Evaluated:   {len(items)} (100% REAL ONLY)")
    print(f"Exact Plate Acc:    {metrics['exact_accuracy']*100:.2f}% ({metrics['exact_matches']}/{len(items)})")
    print(f"Character Accuracy: {metrics['character_accuracy']*100:.2f}%")
    print(f"CER:                {metrics['cer']:.4f}")
    print(f"P50 / P95 Latency:  {p50:.1f}ms / {p95:.1f}ms")
    print(f"Top Confusions:     {list(confusions.items())[:6]}")
    print("===================================================================")

    report_file = REPORT_DIR / f'{split}_evaluation.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)

    conf_csv = REPORT_DIR / 'confusion_matrix.csv'
    with open(conf_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ground_truth_to_predicted', 'count'])
        for pair, count in confusions.items():
            writer.writerow([pair, count])

    return metrics


def run_derived_multiframe_stress_test(recognizer: BasePlateRecognizer, split: str = 'test') -> dict:
    print('\n[MULTI-FRAME] Running Derived Multi-Frame Consensus Stress Test on Real Data...')
    items = load_split_dataset(split)
    voter = MultiFramePlateVoter()

    single_frame_correct = 0
    multi_frame_correct = 0
    total_tests = len(items)
    voting_latencies = []

    for img, gt, _ in items:
        norm_gt = normalize_plate_text(gt)

        # 1. Single Frame Baseline
        raw_text, conf, _ = recognizer.recognize(img)
        single_pred = normalize_plate_text(raw_text)
        if single_pred == norm_gt:
            single_frame_correct += 1

        # 2. Simulate 4-frame video track with slight variations
        simulated_hyps = []
        variations = [
            ('raw', img),
            ('gray', cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)),
            ('clahe', preprocess_crop(img, variant='clahe')[0]),
            ('noisy', np.clip(img.astype(np.float32) + np.random.normal(0, 10, img.shape), 0, 255).astype(np.uint8))
        ]

        for i, (var_name, var_img) in enumerate(variations):
            raw_t, ocr_c, _ = recognizer.recognize(var_img)
            norm_t = normalize_plate_text(raw_t)
            hyp = OCRHypothesis(
                camera_id='sim_cam',
                track_id=1,
                stream_epoch=1,
                pts_ms=i * 150.0,
                raw_text=raw_t,
                normalized_text=norm_t,
                ocr_confidence=ocr_c,
                crop_quality=0.75 - i * 0.05,
                grammar_score=score_indian_grammar(norm_t),
                preprocess_variant=var_name,
                recognizer_name=recognizer.model_name
            )
            simulated_hyps.append(hyp)

        t0 = time.perf_counter()
        track_res = voter.vote(simulated_hyps)
        voting_latencies.append((time.perf_counter() - t0) * 1000)

        if track_res.best_text == norm_gt:
            multi_frame_correct += 1

    single_acc = single_frame_correct / max(total_tests, 1)
    multi_acc = multi_frame_correct / max(total_tests, 1)
    gain = multi_acc - single_acc
    p95_vote_lat = float(np.percentile(voting_latencies, 95))

    res = {
        'total_tracks_evaluated': total_tests,
        'single_frame_exact_accuracy': round(single_acc, 4),
        'multiframe_consensus_exact_accuracy': round(multi_acc, 4),
        'accuracy_gain': round(gain, 4),
        'average_frames_per_track': 4.0,
        'p95_voting_latency_ms': round(p95_vote_lat, 3),
    }

    print("================ MULTI-FRAME CONSENSUS EVALUATION ================")
    print(f"Single-Frame Exact Accuracy: {single_acc*100:.2f}% ({single_frame_correct}/{total_tests})")
    print(f"Multi-Frame Exact Accuracy:  {multi_acc*100:.2f}% ({multi_frame_correct}/{total_tests})")
    print(f"Consensus Accuracy Gain:     {gain*100:+.2f}%")
    print(f"P95 Voting Latency:          {p95_vote_lat:.2f}ms")
    print("==================================================================")

    out_file = REPORT_DIR / 'baseline' / 'multiframe_evaluation.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)

    return res


if __name__ == '__main__':
    rec = get_recognizer('easyocr_crnn', device='cuda')
    run_preprocessing_ablation(rec)
    run_full_evaluation(rec, split='val', variant='clahe')
    run_full_evaluation(rec, split='test', variant='clahe')
    run_derived_multiframe_stress_test(rec, split='test')
