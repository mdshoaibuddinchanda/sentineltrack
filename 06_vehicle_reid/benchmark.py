"""Bounded P6 proxy evaluation and hardware/gallery benchmark."""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import statistics
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import cv2
import numpy as np

from .config import ReIDConfig
from .extractor import AppearanceEmbeddingExtractor, assess_crop_quality
from .gallery import TrackEmbeddingGallery
from .matcher import ReIDMatcher
from .models import TrackProfile, TrackKey, VehicleAppearanceEmbedding


ROOT_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT_DIR / "reports" / "p6"


def percentile(values: Iterable[float], q: float) -> float:
    values = list(values)
    return round(float(np.percentile(values, q)), 4) if values else 0.0


def _sync_device(extractor: AppearanceEmbeddingExtractor) -> None:
    try:
        import torch

        if extractor.device_name.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        return


def _xml_plate_box(xml_path: Path) -> Optional[tuple[float, float, float, float]]:
    if not xml_path.exists():
        return None
    try:
        root = ET.parse(xml_path).getroot()
        box = root.find(".//bndbox")
        if box is None:
            return None
        return tuple(float(box.findtext(name, "0")) for name in ("xmin", "ymin", "xmax", "ymax"))  # type: ignore[return-value]
    except (ET.ParseError, TypeError, ValueError):
        return None


def _expand_plate_to_vehicle(
    image: np.ndarray,
    plate_box: tuple[float, float, float, float],
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Build a clearly labelled vehicle-region proxy from a plate-labelled frame."""

    height, width = image.shape[:2]
    x1, y1, x2, y2 = plate_box
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    crop_x1 = max(0, int(round(x1 - 2.0 * box_width)))
    crop_y1 = max(0, int(round(y1 - 2.0 * box_height)))
    crop_x2 = min(width, int(round(x2 + 2.0 * box_width)))
    crop_y2 = min(height, int(round(y2 + 0.75 * box_height)))
    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        return image, plate_box
    crop = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()
    local_box = (x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1)
    return crop, local_box


def load_proxy_samples(
    *,
    max_crops_per_track: int = 3,
    max_tracks: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Load same-ByteTrack-track crops without pretending they are cross-camera GT."""

    frames_csv = ROOT_DIR / "datasets" / "experiments" / "multiframe_ocr_v1" / "frames.csv"
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with frames_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped[row["track_id"]].append(row)
    track_ids = sorted(grouped)
    if max_tracks is not None:
        track_ids = track_ids[:max_tracks]
    samples: list[dict[str, Any]] = []
    for track_id in track_ids:
        rows = sorted(grouped[track_id], key=lambda row: int(row["frame_index"]))
        if len(rows) > max_crops_per_track:
            indices = np.linspace(0, len(rows) - 1, max_crops_per_track, dtype=int)
            rows = [rows[int(index)] for index in sorted(set(indices))]
        for row in rows:
            image_path = ROOT_DIR / row["source_path"]
            image = cv2.imread(str(image_path))
            plate_box = _xml_plate_box(image_path.with_suffix(".xml")) if image is not None else None
            if image is None or plate_box is None:
                continue
            crop, local_box = _expand_plate_to_vehicle(image, plate_box)
            if crop.size == 0:
                continue
            samples.append(
                {
                    "track_id": track_id,
                    "sequence_id": row["sequence_id"],
                    "frame_index": int(row["frame_index"]),
                    "crop": crop,
                    "plate_bbox": local_box,
                    "source_path": row["source_path"],
                }
            )
    return samples


def _split_track_ids(samples: list[dict[str, Any]]) -> dict[str, set[str]]:
    track_ids = sorted({sample["track_id"] for sample in samples})
    if not track_ids:
        return {"calibration": set(), "test": set()}
    split = max(1, int(math.floor(len(track_ids) * 0.70)))
    return {"calibration": set(track_ids[:split]), "test": set(track_ids[split:])}


def _pair_scores(
    samples: list[dict[str, Any]],
    vectors: list[Optional[np.ndarray]],
    track_split: set[str],
) -> tuple[list[float], list[float], dict[str, int]]:
    by_track: dict[str, list[int]] = defaultdict(list)
    by_sequence: dict[str, list[int]] = defaultdict(list)
    for index, sample in enumerate(samples):
        if sample["track_id"] in track_split and vectors[index] is not None:
            by_track[sample["track_id"]].append(index)
            by_sequence[sample["sequence_id"]].append(index)

    positives: list[float] = []
    negatives: list[float] = []
    for indices in by_track.values():
        for left, right in itertools.combinations(indices, 2):
            positives.append(float(np.dot(vectors[left], vectors[right])))

    # One hard negative per nearby same-source-video track pair prevents a huge
    # easy-negative population from dominating the calibration.
    tracks_by_sequence: dict[str, list[str]] = defaultdict(list)
    for sequence, indices in by_sequence.items():
        tracks_by_sequence[sequence] = sorted({samples[index]["track_id"] for index in indices})
    for sequence, track_ids in tracks_by_sequence.items():
        for left_track, right_track in itertools.combinations(track_ids, 2):
            left_indices = by_track[left_track]
            right_indices = by_track[right_track]
            best_pair = min(
                itertools.product(left_indices, right_indices),
                key=lambda pair: abs(samples[pair[0]]["frame_index"] - samples[pair[1]]["frame_index"]),
            )
            negatives.append(float(np.dot(vectors[best_pair[0]], vectors[best_pair[1]])))
    return positives, negatives, {"track_count": len(by_track), "positive_pairs": len(positives), "negative_pairs": len(negatives)}


def roc_auc(positives: list[float], negatives: list[float]) -> Optional[float]:
    if not positives or not negatives:
        return None
    comparisons = [float(positive > negative) + 0.5 * float(positive == negative) for positive in positives for negative in negatives]
    return round(float(np.mean(comparisons)), 6)


def calibrate_threshold(
    positives: list[float],
    negatives: list[float],
    *,
    maximum_false_match_rate: float,
    fallback: float,
) -> dict[str, Any]:
    if not positives or not negatives:
        return {"threshold": fallback, "false_match_rate": None, "false_non_match_rate": None, "review_only": True}
    thresholds = sorted(set([fallback] + positives + negatives))
    valid = []
    for threshold in thresholds:
        fmr = sum(score >= threshold for score in negatives) / len(negatives)
        fnmr = sum(score < threshold for score in positives) / len(positives)
        if fmr <= maximum_false_match_rate:
            valid.append((fnmr, threshold, fmr))
    if not valid:
        return {"threshold": fallback, "false_match_rate": 1.0, "false_non_match_rate": None, "review_only": True}
    fnmr, threshold, fmr = min(valid, key=lambda item: (item[0], item[1]))
    return {
        "threshold": round(float(threshold), 6),
        "false_match_rate": round(float(fmr), 6),
        "false_non_match_rate": round(float(fnmr), 6),
        # No true cross-camera identity labels exist locally. The calibrated
        # value is therefore usable for review/ranking only, never automatic
        # appearance identity escalation.
        "review_only": True,
    }


def run_proxy_evaluation(
    extractor: AppearanceEmbeddingExtractor,
    *,
    max_crops_per_track: int = 3,
    max_tracks: Optional[int] = None,
) -> dict[str, Any]:
    samples = load_proxy_samples(max_crops_per_track=max_crops_per_track, max_tracks=max_tracks)
    crops = [sample["crop"] for sample in samples]
    bboxes = [sample["plate_bbox"] for sample in samples]
    vectors: list[Optional[np.ndarray]] = []
    for start in range(0, len(crops), 32):
        vectors.extend(extractor.embed_batch(crops[start : start + 32], bboxes[start : start + 32]))
    splits = _split_track_ids(samples)
    calibration_pos, calibration_neg, calibration_population = _pair_scores(samples, vectors, splits["calibration"])
    test_pos, test_neg, test_population = _pair_scores(samples, vectors, splits["test"])
    calibration = calibrate_threshold(
        calibration_pos,
        calibration_neg,
        maximum_false_match_rate=extractor.config.maximum_false_match_rate,
        fallback=extractor.config.minimum_similarity_for_support,
    )
    threshold = float(calibration["threshold"])
    test_fmr = sum(score >= threshold for score in test_neg) / len(test_neg) if test_neg else None
    test_fnmr = sum(score < threshold for score in test_pos) / len(test_pos) if test_pos else None
    all_masked = all(
        extractor.config.plate_region_masked_for_reid and sample.get("plate_bbox") is not None
        for sample in samples
    )
    return {
        "evaluation_name": "P6_APPEARANCE_PROXY_EVALUATION",
        "true_cross_camera_identity_gt_available": False,
        "warning": "NO TRUE CROSS_CAMERA IDENTITY GT — METRICS ARE APPEARANCE PROXY EVIDENCE ONLY",
        "source": "datasets/experiments/multiframe_ocr_v1/frames.csv and datasets/video_images",
        "source_description": "Verified ByteTrack track sequences; vehicle-region proxies expanded from plate-labelled frames; no camera IDs or same-vehicle cross-camera links.",
        "track_identity_split": {
            "calibration_tracks": len(splits["calibration"]),
            "test_tracks": len(splits["test"]),
            "no_track_overlap": splits["calibration"].isdisjoint(splits["test"]),
        },
        "sample_count": len(samples),
        "plate_region_masked_for_reid": all_masked,
        "calibration": {
            **calibration_population,
            "positive_similarity": {
                "count": len(calibration_pos),
                "mean": round(float(np.mean(calibration_pos)), 6) if calibration_pos else None,
                "p50": percentile(calibration_pos, 50),
                "p05": percentile(calibration_pos, 5),
            },
            "negative_similarity": {
                "count": len(calibration_neg),
                "mean": round(float(np.mean(calibration_neg)), 6) if calibration_neg else None,
                "p50": percentile(calibration_neg, 50),
                "p95": percentile(calibration_neg, 95),
            },
            **calibration,
            "roc_auc": roc_auc(calibration_pos, calibration_neg),
        },
        "locked_test": {
            **test_population,
            "positive_similarity": {
                "count": len(test_pos),
                "mean": round(float(np.mean(test_pos)), 6) if test_pos else None,
                "p50": percentile(test_pos, 50),
                "p05": percentile(test_pos, 5),
            },
            "negative_similarity": {
                "count": len(test_neg),
                "mean": round(float(np.mean(test_neg)), 6) if test_neg else None,
                "p50": percentile(test_neg, 50),
                "p95": percentile(test_neg, 95),
            },
            "false_match_rate": round(float(test_fmr), 6) if test_fmr is not None else None,
            "false_non_match_rate": round(float(test_fnmr), 6) if test_fnmr is not None else None,
            "roc_auc": roc_auc(test_pos, test_neg),
        },
    }


def benchmark_extractor(extractor: AppearanceEmbeddingExtractor) -> dict[str, Any]:
    base = np.zeros((256, 384, 3), dtype=np.uint8)
    cv2.rectangle(base, (40, 70), (340, 225), (45, 100, 165), -1)
    cv2.circle(base, (110, 185), 27, (15, 15, 15), -1)
    cv2.circle(base, (275, 185), 27, (15, 15, 15), -1)
    crops = [np.roll(base, shift=index % 7, axis=1) for index in range(8)]
    results: dict[str, Any] = {}
    for batch_size in (1, 4, 8):
        batch = crops[:batch_size]
        timings: list[float] = []
        for _ in range(2):
            extractor.embed_batch(batch, [None] * len(batch))
        for _ in range(8):
            _sync_device(extractor)
            start = time.perf_counter()
            extractor.embed_batch(batch, [None] * len(batch))
            _sync_device(extractor)
            timings.append((time.perf_counter() - start) * 1000.0)
        median_ms = float(np.median(timings))
        results[f"batch_{batch_size}"] = {
            "p50_latency_ms": round(median_ms, 4),
            "p95_latency_ms": percentile(timings, 95),
            "embeddings_per_second": round(batch_size / max(median_ms / 1000.0, 1e-9), 4),
        }

    aggregation_gallery = TrackEmbeddingGallery(extractor.config, max_tracks=1000, top_k_crops=5)
    aggregation_timings: list[float] = []
    for track_index in range(100):
        for crop_index in range(5):
            vector = np.zeros(extractor.embedding_dimension, dtype=np.float32)
            vector[(track_index + crop_index) % extractor.embedding_dimension] = 1.0
            observation = VehicleAppearanceEmbedding(
                camera_id=f"agg-{track_index % 4}",
                stream_epoch=1,
                track_id=track_index,
                embedding=vector,
                model=extractor.config.model_name,
                model_version=extractor.config.model_version,
                crop_quality=float(crop_index) / 5.0,
                plate_region_masked_for_reid=True,
            )
            start = time.perf_counter()
            aggregation_gallery.add_observation(observation, vehicle_class="car")
            aggregation_timings.append((time.perf_counter() - start) * 1000.0)

    gallery_results: dict[str, Any] = {}
    matcher = ReIDMatcher(extractor.config)
    for gallery_size in (100, 1000, 10000):
        gallery = TrackEmbeddingGallery(extractor.config, max_tracks=gallery_size)
        for index in range(gallery_size):
            vector = np.zeros(extractor.embedding_dimension, dtype=np.float32)
            vector[index % extractor.embedding_dimension] = 1.0
            observation = VehicleAppearanceEmbedding(
                camera_id=f"gallery-{index % 16}",
                stream_epoch=1,
                track_id=index,
                embedding=vector,
                model=extractor.config.model_name,
                model_version=extractor.config.model_version,
                crop_quality=0.8,
                plate_region_masked_for_reid=True,
            )
            gallery.add_observation(observation, vehicle_class="car")
        query = VehicleAppearanceEmbedding(
            camera_id="query-camera",
            stream_epoch=1,
            track_id=999999,
            embedding=np.ones(extractor.embedding_dimension, dtype=np.float32),
            model=extractor.config.model_name,
            model_version=extractor.config.model_version,
            crop_quality=0.8,
            plate_region_masked_for_reid=True,
        )
        timings = []
        for _ in range(12):
            start = time.perf_counter()
            matcher.search(query, gallery, top_k=5, vehicle_class="car")
            timings.append((time.perf_counter() - start) * 1000.0)
        gallery_results[str(gallery_size)] = {
            "gallery_embeddings": len(gallery),
            "p50_search_ms": percentile(timings, 50),
            "p95_search_ms": percentile(timings, 95),
        }

    memory: dict[str, Any] = {}
    try:
        import psutil

        memory["cpu_rss_mb"] = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except Exception:
        memory["cpu_rss_mb"] = None
    try:
        import torch

        if extractor.device_name.startswith("cuda") and torch.cuda.is_available():
            memory.update(
                {
                    "gpu_vram_total_mb": round(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024), 2),
                    "gpu_vram_allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
                    "gpu_vram_reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
                }
            )
        else:
            memory["gpu_vram_total_mb"] = 0
    except Exception:
        memory["gpu_vram_total_mb"] = None
    return {
        "model": extractor.checkpoint_provenance(),
        "device": extractor.device_name,
        "embedding_dimension": extractor.embedding_dimension,
        "extractor": results,
        "track_level_aggregation": {
            "gallery_tracks": len(aggregation_gallery),
            "top_k_crops": aggregation_gallery.top_k_crops,
            "p50_add_observation_ms": percentile(aggregation_timings, 50),
            "p95_add_observation_ms": percentile(aggregation_timings, 95),
        },
        "gallery_search": gallery_results,
        "memory": memory,
        "conditional_compute": {
            "strong_plate": "skip_reid",
            "partial_plate": "run_reid",
            "no_usable_plate": "run_reid_review_only",
            "capacity_claim": "bounded benchmark only; no 80k-camera capacity claim",
        },
    }


def render_report(evaluation: dict[str, Any], benchmark: dict[str, Any]) -> str:
    model = benchmark["model"]
    calibration = evaluation["calibration"]
    locked = evaluation["locked_test"]
    lines = [
        "# SentinelTrack Priority 6 — Vehicle ReID Fallback",
        "",
        "> **P6_APPEARANCE_PROXY_EVALUATION** — NO TRUE CROSS_CAMERA IDENTITY GT — METRICS ARE APPEARANCE PROXY EVIDENCE ONLY",
        "",
        "## Decision",
        "",
        "Vehicle ReID is a fallback appearance signal when ANPR is partial or unavailable. Strong ANPR remains authoritative; appearance-only results remain REVIEW/POSSIBLE and cannot produce an automatic HIGH or CRITICAL alert.",
        "",
        "## Selected appearance model",
        "",
        f"- Architecture: `{model['architecture']}` with ImageNet weights; appearance-retrieval baseline, not vehicle-domain ReID.",
        f"- Model/version: `{model['model']}` / `{model['model_version']}`.",
        f"- Checkpoint URL: `{model['checkpoint_url']}`.",
        f"- Checkpoint SHA-256: `{model.get('checkpoint_sha256') or 'not available in this run'}`.",
        f"- Input: `{model['input_resolution'][0]}x{model['input_resolution'][1]}`, BGR-to-RGB, area resize, ImageNet mean/std normalization.",
        f"- Embedding dimension: `{model['embedding_dimension']}`; L2 normalization: `true`.",
        f"- Plate masking: `{model['plate_region_masked_for_reid']}` whenever a local plate box is available; OCR text is never input.",
        f"- Runtime/device: `{model['device']}`.",
        "",
        "## Evaluation provenance",
        "",
        f"- Source: `{evaluation['source']}`.",
        f"- Population: `{evaluation['source_description']}`.",
        f"- Samples: `{evaluation['sample_count']}`; calibration tracks `{evaluation['track_identity_split']['calibration_tracks']}`, locked test tracks `{evaluation['track_identity_split']['test_tracks']}`.",
        f"- Track leakage check: `{evaluation['track_identity_split']['no_track_overlap']}`.",
        "- There is no camera ID or verified same-vehicle cross-camera annotation, so Rank-1, Rank-5, mAP, and cross-camera accuracy are intentionally not reported.",
        "",
        "## Threshold and proxy evidence",
        "",
        f"- Calibration threshold: `{calibration['threshold']}`; selected using calibration only with maximum false-match rate `{evaluation['calibration'].get('false_match_rate')}`.",
        f"- Threshold mode: `REVIEW_ONLY={calibration.get('review_only', True)}`; the threshold ranks/supports operator review and is not an automatic appearance identity gate.",
        f"- Calibration ROC-AUC: `{calibration.get('roc_auc')}`; false-match `{calibration.get('false_match_rate')}`; false-non-match `{calibration.get('false_non_match_rate')}`.",
        f"- Locked proxy ROC-AUC: `{locked.get('roc_auc')}`; false-match `{locked.get('false_match_rate')}`; false-non-match `{locked.get('false_non_match_rate')}`.",
        f"- Similarity distributions: calibration positive p50 `{calibration['positive_similarity']['p50']}`, negative p50 `{calibration['negative_similarity']['p50']}`; locked positive p50 `{locked['positive_similarity']['p50']}`, negative p50 `{locked['negative_similarity']['p50']}`.",
        f"- Automatic appearance escalation: `{bool(evaluation['true_cross_camera_identity_gt_available'] and not calibration.get('review_only', True))}` (P6 remains review-safe because true cross-camera identity ground truth is unavailable).",
        "",
        "## Fusion and safety",
        "",
        "- `STRONG_PLATE`: skip candidate search; `identity_source=ANPR`; ReID cannot override; disagreements are diagnostics only.",
        "- `PARTIAL_PLATE`: `plate_score + reid_score + temporal compatibility + optional route feasibility` can support a plausible P5 candidate; it cannot create EXACT from an unrelated plate.",
        "- `NO_USABLE_PLATE`: `identity_source=REID_REVIEW`; `POSSIBLE/REVIEW` only; no automatic HIGH/CRITICAL alert or exact identity claim.",
        "- Candidates are pruned by camera, stream epoch, vehicle class, chronological window, and optional P7 feasibility callback. Same-camera epoch changes cannot reuse stale track identity.",
        "- Track cache is keyed by `(camera_id, stream_epoch, track_id)`, retains the top five quality crops, and has bounded TTL/capacity.",
        "",
        "## Hardware and gallery benchmark",
        "",
        f"- Batch 1: `{benchmark['extractor']['batch_1']}`.",
        f"- Batch 4: `{benchmark['extractor']['batch_4']}`.",
        f"- Batch 8: `{benchmark['extractor']['batch_8']}`.",
        f"- Track aggregation: `{benchmark['track_level_aggregation']}`.",
        f"- In-memory cosine search: `{benchmark['gallery_search']}`.",
        f"- Memory: `{benchmark['memory']}`.",
        "- ReID runs conditionally for partial/no-plate tracks; strong ANPR tracks skip the expensive search.",
        "",
        "## Limitations",
        "",
        "- The proxy crops are expanded from plate-labelled frames and do not establish cross-camera identity. A verified multi-camera vehicle-ID dataset is required before making ReID accuracy or automatic identity claims.",
        "- The selected ImageNet backbone is not fine-tuned for Indian traffic or cross-camera domain shift.",
        "- P7 remains a chronological lower-bound feasibility signal; this module does not implement road-level routing.",
        "",
        "## Reproducibility",
        "",
        "```text",
        "python -m 06_vehicle_reid.benchmark",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    config = ReIDConfig.from_yaml()
    extractor = AppearanceEmbeddingExtractor(config, eager=True)
    evaluation = run_proxy_evaluation(extractor)
    benchmark = benchmark_extractor(extractor)
    stamp = datetime.now(timezone.utc).isoformat()
    evaluation["generated_at_utc"] = stamp
    benchmark["generated_at_utc"] = stamp
    (REPORT_DIR / "P6_EVALUATION.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    (REPORT_DIR / "P6_BENCHMARK.json").write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    (REPORT_DIR / "P6_REPORT.md").write_text(render_report(evaluation, benchmark), encoding="utf-8")
    print(json.dumps({"evaluation": evaluation, "benchmark": benchmark}, indent=2))


if __name__ == "__main__":
    main()
