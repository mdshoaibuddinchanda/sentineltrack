import json
import time
import importlib
import numpy as np
from pathlib import Path

prep_mod = importlib.import_module('04_plate_ocr.preprocess')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
gram_mod = importlib.import_module('04_plate_ocr.grammar')
vote_mod = importlib.import_module('04_plate_ocr.voting')
rec_mod = importlib.import_module('04_plate_ocr.recognizers')
models_mod = importlib.import_module('04_plate_ocr.models')

preprocess_crop = prep_mod.preprocess_crop
normalize_plate_text = norm_mod.normalize_plate_text
score_indian_grammar = gram_mod.score_indian_grammar
MultiFramePlateVoter = vote_mod.MultiFramePlateVoter
get_recognizer = rec_mod.get_recognizer
OCRHypothesis = models_mod.OCRHypothesis

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
REPORT_DIR = ROOT_DIR / 'reports' / 'plate_ocr' / 'benchmarks'


def benchmark_ocr_subsystem(num_samples: int = 50, batch_sizes: list[int] = [1, 2, 4, 8], num_iterations: int = 50):
    print('================ RUNNING PRIORITY 4 BENCHMARK WITH STRICT PERCENTILES ================')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    img_files = list((DATASET_DIR / 'images' / 'val').glob('*.jpg'))[:num_samples]
    if not img_files:
        raise FileNotFoundError('No validation images found for benchmark.')

    import cv2
    crops = [cv2.imread(str(f)) for f in img_files if cv2.imread(str(f)) is not None]
    if not crops:
        raise ValueError('Could not load crops for benchmark.')

    recognizer = get_recognizer('ppocr_mobile', device='cpu')
    voter = MultiFramePlateVoter(min_support_count=2)

    print('Warming up engine (10 iterations)...')
    for _ in range(10):
        _ = recognizer.recognize(crops[0])
        _ = recognizer.recognize_batch([crops[0], crops[1]])

    # 1. Pipeline stage breakdown
    t_preps, t_ocrs, t_norms, t_grams, t_votes, t_totals = [], [], [], [], [], []

    for crop in crops:
        t_start = time.perf_counter()

        t0 = time.perf_counter()
        prep_img, _ = preprocess_crop(crop, variant='raw', target_height=48)
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
            OCRHypothesis('cam1', 1, 1, 0.0, raw_text, norm_text, conf or 0.5, 0.7, gram_sc),
            OCRHypothesis('cam1', 1, 1, 150.0, raw_text, norm_text, conf or 0.5, 0.7, gram_sc)
        ]
        t0 = time.perf_counter()
        _ = voter.vote(hyps)
        t_votes.append((time.perf_counter() - t0) * 1000)

        t_totals.append((time.perf_counter() - t_start) * 1000)

    # 2. Strict Batch Benchmark (>=50 timed iterations per batch size)
    batch_benchmarks = []

    for bs in batch_sizes:
        batch_slice = [crops[i % len(crops)] for i in range(bs)]
        iteration_latencies_ms = []

        # Warmup for this batch size
        for _ in range(5):
            _ = recognizer.recognize_batch(batch_slice)

        for _ in range(num_iterations):
            t0 = time.perf_counter()
            _ = recognizer.recognize_batch(batch_slice)
            lat_ms = (time.perf_counter() - t0) * 1000
            iteration_latencies_ms.append(lat_ms)

        mean_batch_lat = float(np.mean(iteration_latencies_ms))
        p50_batch_lat = float(np.percentile(iteration_latencies_ms, 50))
        p95_batch_lat = float(np.percentile(iteration_latencies_ms, 95))
        p99_batch_lat = float(np.percentile(iteration_latencies_ms, 99))
        mean_amortized = mean_batch_lat / bs
        throughput = 1000.0 / mean_amortized

        b_entry = {
            'batch_size': bs,
            'timed_iterations': num_iterations,
            'mean_batch_latency_ms': round(mean_batch_lat, 2),
            'p50_batch_latency_ms': round(p50_batch_lat, 2),
            'p95_batch_latency_ms': round(p95_batch_lat, 2),
            'p99_batch_latency_ms': round(p99_batch_lat, 2),
            'mean_amortized_per_crop_ms': round(mean_amortized, 2),
            'throughput_crops_per_sec': round(throughput, 2),
            'batching_mode': 'TRUE_TENSOR_BATCHING'
        }
        batch_benchmarks.append(b_entry)

        print(f"Batch Size: B={bs:<2} | Mean Batch: {mean_batch_lat:>5.2f}ms | P50: {p50_batch_lat:>5.2f}ms | P95: {p95_batch_lat:>5.2f}ms | Amortized/Crop: {mean_amortized:>5.2f}ms | Throughput: {throughput:>6.2f} c/s")

    summary = {
        'hardware': {
            'device': 'CPU (ONNX Runtime)',
            'threads': 8,
        },
        'recognizer_name': recognizer.model_name,
        'sample_size': len(crops),
        'stage_latencies_ms': {
            'preprocessing': {
                'mean': round(float(np.mean(t_preps)), 3),
                'p50': round(float(np.percentile(t_preps, 50)), 3),
                'p95': round(float(np.percentile(t_preps, 95)), 3),
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
        'batching_performance': batch_benchmarks
    }

    out_file = REPORT_DIR / 'ocr_latency_benchmark.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved benchmark results to: {out_file}")
    print('======================================================================================\n')
    return summary


if __name__ == '__main__':
    benchmark_ocr_subsystem()
