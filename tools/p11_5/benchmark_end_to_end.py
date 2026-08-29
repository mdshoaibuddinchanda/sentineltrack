"""Measure detector -> crop -> OCR end-to-end on the strict real test set."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1]) + max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1]) - inter
    return inter / union if union else 0.0


def gt_box(label: Path, width: int, height: int) -> list[float] | None:
    if not label.is_file():
        return None
    parts = label.read_text(encoding="utf-8").split()
    if len(parts) < 5:
        return None
    _, xc, yc, nw, nh = map(float, parts[:5])
    return [(xc - nw / 2) * width, (yc - nh / 2) * height, (xc + nw / 2) * width, (yc + nh / 2) * height]


def sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_model(model_path: Path, rows: list[dict[str, str]], data_root: Path, device: str, eval_mod: Any, rec_mod: Any) -> dict[str, Any]:
    import cv2  # type: ignore
    from ultralytics import YOLO  # type: ignore
    model = YOLO(str(model_path))
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    latencies: list[float] = []
    predictions: list[str] = []
    truths: list[str] = []
    tp = fp = fn = 0
    ocr_matched = 0
    for row in rows:
        image = cv2.imread(str(data_root / row["output_image"]))
        if image is None:
            continue
        height, width = image.shape[:2]
        truth_box = gt_box(data_root / row["output_label"], width, height)
        started = time.perf_counter()
        result = model.predict(source=image, imgsz=640, conf=0.25, device=device, verbose=False)[0]
        best_box = None
        best_conf = -1.0
        if result.boxes is not None:
            for box, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                if int(cls) == 0 and float(confidence) > best_conf:
                    best_box, best_conf = box, float(confidence)
        matched = best_box is not None and truth_box is not None and iou(best_box, truth_box) >= 0.5
        if matched:
            tp += 1
            x1, y1, x2, y2 = [int(round(value)) for value in best_box]
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
            crop = image[y1:y2, x1:x2]
            prepared, _ = eval_mod.preprocess_crop(crop, variant="raw", target_height=48)
            text, _, _ = recognizer.recognize(prepared)
            predictions.append(text or "")
            truths.append(row.get("plate_text_normalized", ""))
            ocr_matched += 1
        else:
            if best_box is not None:
                fp += 1
            if truth_box is not None:
                fn += 1
            predictions.append("")
            truths.append(row.get("plate_text_normalized", ""))
        latencies.append((time.perf_counter() - started) * 1000)
    ocr_metrics = eval_mod.calculate_metrics(predictions, truths)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        "model_sha256": sha256(model_path),
        "images": len(rows), "detector_tp": tp, "detector_fp": fp, "detector_fn": fn,
        "detector_precision": round(precision, 6), "detector_recall": round(recall, 6),
        "ocr_matched_detections": ocr_matched,
        "end_to_end_post_exact_accuracy": ocr_metrics.get("postprocessed_exact_accuracy", 0.0),
        "end_to_end_raw_exact_accuracy": ocr_metrics.get("raw_exact_accuracy", 0.0),
        "end_to_end_post_cer": ocr_metrics.get("postprocessed_cer", 0.0),
        "latency_ms": {"mean": round(statistics.mean(latencies), 3) if latencies else None, "p50": round(statistics.median(latencies), 3) if latencies else None, "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3) if latencies else None, "p99": round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 3) if latencies else None},
        "fps": round(1000 / statistics.mean(latencies), 3) if latencies and statistics.mean(latencies) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="models/plate/production/best.pt")
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    import cv2  # type: ignore
    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    data_root = ROOT / "datasets/experiments/plate_detection_v2_strict"
    with (data_root / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("split") == "test"]
    results = []
    for value in args.models.split(","):
        model_path = (ROOT / value.strip()).resolve()
        results.append(run_model(model_path, rows, data_root, args.device, eval_mod, rec_mod))
    report = {
        "status": "COMPLETE_WITH_PLATE_ONLY_GT",
        "dataset": str(data_root.relative_to(ROOT)).replace("\\", "/"),
        "split": "test",
        "pipeline": "detector -> predicted crop -> PP-OCRv5 mobile -> existing structural decoder metrics",
        "p5_safety": {"status": "UNAVAILABLE_NO_NEGATIVE_VEHICLE_OR_BACKGROUND_GT", "false_positive_rate": None, "note": "The strict test contains one positive plate object per image; it cannot support a safety FPR claim."},
        "results": results,
    }
    output = ROOT / "reports" / "p11_5" / "end_to_end_evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (ROOT / "reports" / "p11_5" / "end_to_end_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["model", "model_sha256", "images", "detector_tp", "detector_fp", "detector_fn", "detector_precision", "detector_recall", "ocr_matched_detections", "end_to_end_post_exact_accuracy", "end_to_end_raw_exact_accuracy", "end_to_end_post_cer", "latency_ms", "fps"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
