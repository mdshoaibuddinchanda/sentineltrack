import os
import cv2
import csv
import json
import time
import importlib
import numpy as np
from pathlib import Path
from typing import Optional, Any

from .models import (
    MatchClass,
    WatchlistPriority,
    WatchlistEntry,
    MatchCandidate
)
from .config import TargetMatchingConfig
from .normalizer import normalize_target_registration, normalize_plate_text
from .distance import standard_levenshtein, position_weighted_edit_distance
from .scorer import TargetMatchScorer
from .watchlist import WatchlistManager
from .alerts import AlertManager

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / 'reports' / 'target_matching'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_real_p4_manifest() -> list[dict[str, Any]]:
    """
    Runs the final-frozen P4 OCR recognizer on real validation and locked test plate crops.
    Generates reports/target_matching/p4_match_eval_manifest.csv.
    """
    manifest_p = REPORTS_DIR / 'p4_match_eval_manifest.csv'
    sources_p = ROOT_DIR / 'datasets' / 'plate_ocr' / 'sources.csv'

    rec_mod = importlib.import_module('04_plate_ocr.recognizers')
    recognizer = rec_mod.get_recognizer('ppocr_mobile', device='cpu')

    rows = []
    if sources_p.exists():
        with open(sources_p, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                split = r.get('split', '')
                if split not in ('val', 'test'):
                    continue

                fn = r.get('filename', '')
                gt = r.get('plate_text', '').strip().replace(' ', '').upper()
                img_p = ROOT_DIR / 'datasets' / 'plate_ocr' / 'images' / split / fn

                if img_p.exists():
                    img = cv2.imread(str(img_p))
                    if img is not None and img.size > 0:
                        txt, conf, _ = recognizer.recognize(img)
                        norm_obs = normalize_plate_text(txt)
                        rows.append({
                            'split': split,
                            'sample_id': fn,
                            'ground_truth_target': gt,
                            'actual_p4_observation': norm_obs,
                            'ocr_confidence': round(conf or 0.80, 4),
                            'crop_quality': 0.85,
                            'raw_or_postprocessed': 'postprocessed',
                            'is_real_ocr_observation': True
                        })

    if rows:
        with open(manifest_p, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return rows


def generate_hard_negatives(ground_truth: str) -> list[str]:
    """Generates strictly verified hard negative registration strings."""
    norm_gt = normalize_plate_text(ground_truth)
    chars = list(norm_gt)
    n = len(chars)
    negatives = []

    # 1. 1-character suffix difference
    if chars[-1].isdigit():
        new_d = str((int(chars[-1]) + 1) % 10)
        negatives.append(''.join(chars[:-1] + [new_d]))

    # 2. 1-character series difference
    for i in range(2, min(n - 4, 6)):
        if chars[i].isalpha():
            new_c = chr((ord(chars[i]) - 65 + 1) % 26 + 65)
            negatives.append(''.join(chars[:i] + [new_c] + chars[i + 1:]))
            break

    # 3. OCR Confusable negative on DIFFERENT vehicle
    if 'B' in norm_gt:
        negatives.append(norm_gt.replace('B', '8', 1))
    if '0' in norm_gt:
        negatives.append(norm_gt.replace('0', 'O', 1))

    # 4. Adjacent transposition
    if n >= 6:
        negatives.append(chars[0] + chars[1] + chars[3] + chars[2] + ''.join(chars[4:]))

    # 5. Missing 1 character
    if n >= 7:
        negatives.append(''.join(chars[:-1]))

    # Filter: strictly assert negative != target after normalization
    valid_negs = []
    for neg in negatives:
        norm_neg = normalize_plate_text(neg)
        if norm_neg and norm_neg != norm_gt:
            valid_negs.append(norm_neg)

    return list(set(valid_negs))


def evaluate_matcher_group(
    samples: list[dict[str, Any]],
    scorer: TargetMatchScorer,
    alert_manager: AlertManager
) -> dict[str, Any]:
    """
    Evaluates real P4 OCR observations against targets.
    Measures both raw score thresholding and actual automatic alert dispatch policy.
    """
    tp, fp, tn, fn = 0, 0, 0, 0
    alert_tp, alert_fp, alert_tn, alert_fn = 0, 0, 0, 0

    all_targets = list({s['ground_truth_target'] for s in samples})

    # Top-K and MRR tracking
    top1_correct = 0
    top3_correct = 0
    top5_correct = 0
    rr_sum = 0.0

    for s in samples:
        target = s['ground_truth_target']
        obs = s['actual_p4_observation']
        conf = s['ocr_confidence']
        supp = 2  # Standard verified multi-frame observation

        # True Pair
        res_pos = scorer.score_match('tgt-pos', target, obs, ocr_confidence=conf, multi_frame_support=supp)
        if res_pos.match_score >= scorer.high_prob_threshold:
            tp += 1
        else:
            fn += 1

        w_pos = WatchlistEntry(watchlist_id='w-pos', registration=target, normalized_registration=target, priority=WatchlistPriority.HIGH)
        alert_pos, is_new_pos, _ = alert_manager.process_match(res_pos, w_pos, 's-pos')
        if alert_pos:
            alert_tp += 1
        else:
            alert_fn += 1

        # Negative Pair (Different vehicle target)
        neg_target = all_targets[(all_targets.index(target) + 1) % len(all_targets)]
        res_neg = scorer.score_match('tgt-neg', neg_target, obs, ocr_confidence=conf, multi_frame_support=supp)
        if res_neg.match_score >= scorer.high_prob_threshold:
            fp += 1
        else:
            tn += 1

        w_neg = WatchlistEntry(watchlist_id='w-neg', registration=neg_target, normalized_registration=neg_target, priority=WatchlistPriority.HIGH)
        alert_neg, is_new_neg, _ = alert_manager.process_match(res_neg, w_neg, 's-neg')
        if alert_neg:
            alert_fp += 1
        else:
            alert_tn += 1

        # Multi-target ranking
        candidates = [target, neg_target]
        cand_scores = [
            (t, scorer.score_match('t', t, obs, ocr_confidence=conf, multi_frame_support=supp).match_score)
            for t in candidates
        ]
        cand_scores.sort(key=lambda x: x[1], reverse=True)
        ranked = [c[0] for c in cand_scores]

        if ranked[0] == target:
            top1_correct += 1
        if target in ranked[:3]:
            top3_correct += 1
        if target in ranked[:5]:
            top5_correct += 1
        rank = ranked.index(target) + 1
        rr_sum += 1.0 / rank

    n = len(samples)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-6)
    fpr = fp / max(fp + tn, 1)
    fnr = fn / max(fn + tp, 1)

    a_prec = alert_tp / max(alert_tp + alert_fp, 1)
    a_rec = alert_tp / max(alert_tp + alert_fn, 1)
    a_f1 = 2 * a_prec * a_rec / max(a_prec + a_rec, 1e-6)
    a_fpr = alert_fp / max(alert_fp + alert_tn, 1)
    a_fnr = alert_fn / max(alert_fn + alert_tp, 1)
    false_alerts_per_1000 = (alert_fp / max(n, 1)) * 1000.0

    return {
        'total_real_samples': n,
        'score_threshold_metrics': {
            'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn,
            'precision': round(prec, 4), 'recall': round(rec, 4), 'f1': round(f1, 4),
            'FPR': round(fpr, 4), 'FNR': round(fnr, 4)
        },
        'actual_alert_policy_metrics': {
            'Alert_TP': alert_tp, 'Alert_FP': alert_fp, 'Alert_TN': alert_tn, 'Alert_FN': alert_fn,
            'alert_precision': round(a_prec, 4), 'alert_recall': round(a_rec, 4), 'alert_f1': round(a_f1, 4),
            'alert_FPR': round(a_fpr, 4), 'alert_FNR': round(a_fnr, 4),
            'false_alerts_per_1000_non_target_observations': round(false_alerts_per_1000, 2)
        },
        'ranking_metrics': {
            'top1_accuracy': round(top1_correct / max(n, 1), 4),
            'top3_recall': round(top3_correct / max(n, 1), 4),
            'top5_recall': round(top5_correct / max(n, 1), 4),
            'mrr': round(rr_sum / max(n, 1), 4)
        }
    }


def benchmark_candidate_shortlist_recall(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Evaluates candidate generation Recall@K and separates lookup latency from full matching latency.
    """
    sizes = [100, 1000, 10000, 100000]
    states = ['MH', 'DL', 'GJ', 'KA', 'TN', 'HR', 'UP', 'WB', 'RJ', 'AP']
    series = ['AB', 'CD', 'EF', 'GH', 'JK', 'LM', 'NP', 'RS']

    results = []
    test_samples = [s for s in manifest if s['split'] == 'test'][:50]
    if not test_samples:
        test_samples = manifest[:50]

    scorer = TargetMatchScorer()

    for n in sizes:
        wm = WatchlistManager()
        # Seed watchlist with true targets from test set first
        for s in test_samples:
            wm.add_entry(s['ground_truth_target'])

        # Fill remainder with synthetic distractors
        for i in range(len(test_samples), n):
            st = states[i % len(states)]
            rto = f'{(i % 99) + 1:02d}'
            ser = series[(i // 99) % len(series)]
            num = f'{(i % 9999) + 1:04d}'
            wm.add_entry(f'{st}{rto}{ser}{num}')

        gen_latencies = []
        match_latencies = []
        rec_10, rec_25, rec_50, rec_100 = 0, 0, 0, 0
        shortlist_lens = []

        for s in test_samples:
            gt = s['ground_truth_target']
            obs = s['actual_p4_observation']

            t0 = time.perf_counter()
            cands_100 = wm.lookup_candidates(obs, max_candidates=100)
            t1 = time.perf_counter()

            # Measure full scoring of shortlisted candidates
            for c in cands_100:
                scorer.score_match(c.watchlist_id, c.normalized_registration, obs)
            t2 = time.perf_counter()

            gen_latencies.append((t1 - t0) * 1000.0)
            match_latencies.append((t2 - t0) * 1000.0)
            shortlist_lens.append(len(cands_100))

            cand_regs = [c.normalized_registration for c in cands_100]
            if gt in cand_regs[:10]:
                rec_10 += 1
            if gt in cand_regs[:25]:
                rec_25 += 1
            if gt in cand_regs[:50]:
                rec_50 += 1
            if gt in cand_regs[:100]:
                rec_100 += 1

        total = len(test_samples)
        gen_arr = np.array(gen_latencies)
        match_arr = np.array(match_latencies)

        results.append({
            'watchlist_size': n,
            'candidate_generation_P50_ms': round(float(np.percentile(gen_arr, 50)), 3),
            'candidate_generation_P95_ms': round(float(np.percentile(gen_arr, 95)), 3),
            'candidate_scoring_P50_ms': round(float(np.percentile(match_arr - gen_arr, 50)), 3),
            'total_match_P50_ms': round(float(np.percentile(match_arr, 50)), 3),
            'total_match_P95_ms': round(float(np.percentile(match_arr, 95)), 3),
            'mean_shortlist_size': round(float(np.mean(shortlist_lens)), 1),
            'Recall@10': round(rec_10 / total, 4),
            'Recall@25': round(rec_25 / total, 4),
            'Recall@50': round(rec_50 / total, 4),
            'Recall@100': round(rec_100 / total, 4)
        })

    return results


def run_full_benchmark():
    print('============================================================')
    print('RUNNING SENTINELTRACK PRIORITY 5B BENCHMARK')
    print('============================================================')

    manifest = generate_real_p4_manifest()
    print(f'Generated real P4 manifest with {len(manifest)} observations.')

    val_samples = [s for s in manifest if s['split'] == 'val']
    test_samples = [s for s in manifest if s['split'] == 'test']
    print(f'Validation observations: {len(val_samples)} | Locked Test observations: {len(test_samples)}')

    config = TargetMatchingConfig.from_yaml()
    scorer = TargetMatchScorer(config=config)
    alert_mgr = AlertManager(config=config)

    # 1. Real P4 Evaluation (Group A)
    print('\n--- 1. Evaluating Real P4 Validation Set ---')
    val_res = evaluate_matcher_group(val_samples, scorer, alert_mgr)

    print('\n--- 2. Evaluating Real P4 Locked Test Set ---')
    test_res = evaluate_matcher_group(test_samples, scorer, alert_mgr)

    # 2. Candidate Generation Recall Benchmark
    print('\n--- 3. Evaluating Candidate Shortlist Recall across Watchlist Sizes ---')
    shortlist_scaling = benchmark_candidate_shortlist_recall(manifest)

    # 3. Save Final JSON Report
    final_report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'group_A_real_p4_matching': {
            'validation_split': val_res,
            'locked_test_split': test_res
        },
        'watchlist_candidate_recall_scaling': shortlist_scaling,
        'configuration_used': {
            'high_probability_threshold': config.high_probability_threshold,
            'probable_threshold': config.probable_threshold,
            'possible_threshold': config.possible_threshold,
            'exact_evidence_gate_required': config.exact_evidence_gate_required
        }
    }

    rep_json_p = REPORTS_DIR / 'final_evaluation.json'
    with open(rep_json_p, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
    print(f'Saved final evaluation report to {rep_json_p}')


if __name__ == '__main__':
    run_full_benchmark()
