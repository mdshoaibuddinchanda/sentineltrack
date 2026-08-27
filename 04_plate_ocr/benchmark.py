import time
import torch
import importlib
import numpy as np
from pathlib import Path

models_mod = importlib.import_module('04_plate_ocr.models')
prep_mod = importlib.import_module('04_plate_ocr.preprocess')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
gram_mod = importlib.import_module('04_plate_ocr.grammar')
vote_mod = importlib.import_module('04_plate_ocr.voting')
rec_mod = importlib.import_module('04_plate_ocr.recognizers')

OCRHypothesis = models_mod.OCRHypothesis
preprocess_crop = prep_mod.preprocess_crop
normalize_plate_text = norm_mod.normalize_plate_text
score_indian_grammar = gram_mod.score_indian_grammar
MultiFramePlateVoter = vote_mod.MultiFramePlateVoter
get_recognizer = rec_mod.get_recognizer

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
REPORT_DIR = ROOT_DIR / 'reports' / 'plate_ocr' / 'benchmarks'


def benchmark_ocr_subsystem(num_samples: int = 50, batch_sizes: list[int] = [1, 2, 4, 8]):
    print('[BENCHMARK] Initializing Priority 4 Subsystem Benchmark...')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    img_files = list((DATASET_DIR / 'images' / 'val').glob('*.jpg'))[:num_samples]
    if not img_files:
        raise FileNotFoundError('No validation images found for benchmark.')

    import cv2
    crops = [cv2.imread(str(f)) for f in img_files if cv2.imread(str(f)) is not None]
    if not crops:
        raise ValueError('Could not load crops for benchmark.')

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
    vram_mb = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024) if torch.cuda.is_available() else 0

    recognizer = get_recognizer('easyocr_crnn', device='cuda')
    voter = MultiFramePlateVoter()

    print('[BENCHMARK] Warming up GPU...')
    for _ in range(5):
        _ = recognizer.recognize(crops[0])

    t_preps = []
    t_ocrs = []
    t_norms = []
    t_grams = []
    t_votes = []
    t_totals = []

    for i, crop in enumerate(crops):
        t_start = time.perf_counter()

        t0 = time.perf_counter()
        prep_img, _ = preprocess_crop(crop, variant='clahe')
        t_preps.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        raw_text, conf, _ = recognizer.recognize(prep_img)
        t_ocrs.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        norm_text = normalize_plate_text(raw_text)
        t_norms.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        gram_sc = score_indian_grammar(norm_text)
        t_grams.append((time.perf_counter() - t0) * 1000)

        hyps = [
            OCRHypothesis('cam1', 1, 1, 0.0, raw_text, norm_text, conf, 0.7, gram_sc),
            OCRHypothesis('cam1', 1, 1, 150.0, raw_text, norm_text, conf, 0.7, gram_sc)
        ]
        t0 = time.perf_counter()
        _ = voter.vote(hyps)
        t_votes.append((time.perf_counter() - t0) * 1000)

        t_totals.append((time.perf_counter() - t_start) * 1000)

    batch_results = []
    for bs in batch_sizes:
        batched_crops = [crops[i % len(crops)] for i in range(bs * 5)]
        t0 = time.perf_counter()
        for b_idx in range(0, len(batched_crops), bs):
            chunk = batched_crops[b_idx:b_idx + bs]
            _ = recognizer.recognize_batch(chunk)
        elapsed = time.perf_counter() - t0
        fps = len(batched_crops) / max(elapsed, 1e-6)
        batch_results.append({'batch_size': bs, 'throughput_crops_per_sec': round(fps, 2), 'latency_per_batch_ms': round((elapsed / 5) * 1000, 2)})

    summary = {
        'hardware': {
            'gpu_name': gpu_name,
            'vram_mb': round(vram_mb, 1),
            'torch_version': torch.__version__,
        },
        'sample_size': len(crops),
        'stage_latencies_ms': {
            'preprocessing': {
                'mean': round(float(np.mean(t_preps)), 2),
                'p50': round(float(np.percentile(t_preps, 50)), 2),
                'p95': round(float(np.percentile(t_preps, 95)), 2),
            },
            'ocr_inference': {
                'mean': round(float(np.mean(t_ocrs)), 2),
                'p50': round(float(np.percentile(t_ocrs, 50)), 2),
                'p95': round(float(np.percentile(t_ocrs, 95)), 2),
            },
            'normalization_and_grammar': {
                'mean': round(float(np.mean(t_norms)) + float(np.mean(t_grams)), 3),
                'p50': round(float(np.percentile(t_norms, 50)) + float(np.percentile(t_grams, 50)), 3),
                'p95': round(float(np.percentile(t_norms, 95)) + float(np.percentile(t_grams, 95)), 3),
            },
            'voting': {
                'mean': round(float(np.mean(t_votes)), 3),
                'p50': round(float(np.percentile(t_votes, 50)), 3),
                'p95': round(float(np.percentile(t_votes, 95)), 3),
            },
            'total_p4_pipeline': {
                'mean': round(float(np.mean(t_totals)), 2),
                'p50': round(float(np.percentile(t_totals, 50)), 2),
                'p95': round(float(np.percentile(t_totals, 95)), 2),
            }
        },
        'batching_performance': batch_results
    }

    print('\n================ PRIORITY 4 BENCHMARK RESULTS ================')
    print(f"Device: {gpu_name} ({vram_mb:.0f} MB)")
    print(f"Preprocessing Latency:  P50 = {summary['stage_latencies_ms']['preprocessing']['p50']}ms | P95 = {summary['stage_latencies_ms']['preprocessing']['p95']}ms")
    print(f"OCR Inference Latency:  P50 = {summary['stage_latencies_ms']['ocr_inference']['p50']}ms | P95 = {summary['stage_latencies_ms']['ocr_inference']['p95']}ms")
    print(f"Voting Latency:         P50 = {summary['stage_latencies_ms']['voting']['p50']}ms | P95 = {summary['stage_latencies_ms']['voting']['p95']}ms")
    print(f"Total P4 Pipeline:      P50 = {summary['stage_latencies_ms']['total_p4_pipeline']['p50']}ms | P95 = {summary['stage_latencies_ms']['total_p4_pipeline']['p95']}ms")
    print('Batching Throughput:', batch_results)
    print('===============================================================\n')

    import json
    with open(REPORT_DIR / 'ocr_latency_benchmark.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == '__main__':
    benchmark_ocr_subsystem()
