"""Evaluate temporal OCR methods on one fixed same-track population.

The original temporal leaderboard changes its denominator for every window.
This companion keeps only tracks with at least eight observations and reuses
that exact track set for windows 1, 3, 5, and 8, making the window comparison
paired rather than cohort-shifted.
"""

from __future__ import annotations

import csv
import importlib
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "experiments" / "multiframe_ocr_v1"
REPORT_DIR = ROOT / "reports" / "p11_5"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def metric(predictions: list[str], truths: list[str], weighted_levenshtein: Any, normalize: Any) -> dict[str, Any]:
    normalized_predictions = [normalize(value) for value in predictions]
    normalized_truths = [normalize(value) for value in truths]
    exact = sum(pred == truth for pred, truth in zip(normalized_predictions, normalized_truths))
    distance = sum(weighted_levenshtein(pred, truth, confusion_cost=1.0) for pred, truth in zip(normalized_predictions, normalized_truths))
    gt_chars = sum(max(1, len(truth)) for truth in normalized_truths)
    char_correct = sum(sum(a == b for a, b in zip(pred, truth)) for pred, truth in zip(normalized_predictions, normalized_truths))
    return {
        "tracks": len(truths),
        "exact_matches": exact,
        "exact_accuracy": round(exact / max(1, len(truths)), 6),
        "character_accuracy": round(char_correct / max(1, gt_chars), 6),
        "cer": round(distance / max(1, gt_chars), 6),
    }


def load_frames() -> list[dict[str, str]]:
    with (DATASET / "frames.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_methods(items: list[dict[str, Any]], eval_mod: Any, models_mod: Any, voter_mod: Any, temporal_mod: Any) -> dict[str, str]:
    methods: dict[str, str] = {}
    best = temporal_mod.best_observation(items)
    methods["single_best"] = best["text"] if best else ""
    weighted = temporal_mod.temporal_vote(items, min_support=1)
    methods["weighted_vote"] = weighted.get("selected_text") or ""
    candidates = [(item["text"], max(0.01, item["confidence"] * item["quality"])) for item in items if item["text"]]
    methods["character_fusion"] = voter_mod.resolve_character_consensus(candidates)
    hypotheses = []
    for index, item in enumerate(items):
        hypotheses.append(models_mod.OCRHypothesis(
            camera_id="multiframe_v1", track_id=index, stream_epoch=0,
            pts_ms=float(item["frame_index"]), raw_text=item["text"],
            normalized_text=eval_mod.normalize_plate_text(item["text"]),
            ocr_confidence=item["confidence"], crop_quality=item["quality"],
            grammar_score=eval_mod.score_indian_grammar(eval_mod.normalize_plate_text(item["text"])),
            character_confidences=item.get("char_confidences", []), plate_width=0, plate_height=0,
        ))
    voted = voter_mod.MultiFramePlateVoter(min_support_count=1).vote(hypotheses)
    methods["current_voter"] = voted.best_text or ""
    return methods


def main() -> int:
    import cv2  # type: ignore

    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    models_mod = importlib.import_module("04_plate_ocr.models")
    voter_mod = importlib.import_module("04_plate_ocr.voting")
    temporal_mod = importlib.import_module("tools.p11_5.temporal")
    quality_mod = importlib.import_module("tools.p11_5.quality")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")

    by_track: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_frames():
        by_track[row["track_id"]].append(row)
    for items in by_track.values():
        items.sort(key=lambda row: int(row["frame_index"]))

    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    observations: dict[str, list[dict[str, Any]]] = {}
    latencies: list[float] = []
    for track_id, items in by_track.items():
        values: list[dict[str, Any]] = []
        for row in items:
            image = cv2.imread(str(DATASET / row["crop_path"]))
            if image is None:
                continue
            started = time.perf_counter()
            text, confidence, char_confidences = recognizer.recognize(image)
            latencies.append((time.perf_counter() - started) * 1000)
            values.append({
                "text": text or "", "confidence": float(confidence or 0.0),
                "quality": float(quality_mod.crop_quality(image).get("score", 0.0)),
                "frame_index": int(row["frame_index"]), "char_confidences": char_confidences,
                "gt": row["gt_text"],
            })
        observations[track_id] = values

    max_window = 8
    paired_ids = sorted(track_id for track_id, items in observations.items() if len(items) >= max_window)
    rows_out: list[dict[str, Any]] = []
    for window in (1, 3, 5, 8):
        methods = defaultdict(list)
        truths: list[str] = []
        for track_id in paired_ids:
            sample = observations[track_id][:window]
            truths.append(sample[0]["gt"])
            for method, value in evaluate_methods(sample, eval_mod, models_mod, voter_mod, temporal_mod).items():
                methods[method].append(value)
        for method, predictions in sorted(methods.items()):
            rows_out.append({
                "window": window, "method": method, "population": "tracks_with_at_least_8_observations",
                "eligible_tracks": len(paired_ids),
                **metric(predictions, truths, eval_mod.weighted_levenshtein, eval_mod.normalize_plate_text),
            })

    output = {
        "status": "COMPLETE",
        "dataset": str(DATASET.relative_to(ROOT)).replace("\\", "/"),
        "tracks": len(by_track), "frames": sum(len(items) for items in observations.values()),
        "recognizer": "PP-OCRv5 mobile", "paired_population": {"minimum_window": max_window, "track_count": len(paired_ids)},
        "inference_latency_ms": {"p50": round(statistics.median(latencies), 3) if latencies else None, "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3) if latencies else None},
        "results": rows_out,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "temporal_paired_evaluation.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (REPORT_DIR / "temporal_paired_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["window", "method", "population", "eligible_tracks", "tracks", "exact_matches", "exact_accuracy", "character_accuracy", "cer"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
