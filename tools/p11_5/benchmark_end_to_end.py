"""Measure detector -> crop -> OCR end-to-end on the strict real test set."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from detection_matching import greedy_one_to_one_matches


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


def truth_box(row: dict[str, str], width: int, height: int, data_root: Path) -> list[float] | None:
    if row.get("bbox_json"):
        values = json.loads(row["bbox_json"])
        if values and len(values[0]) == 4:
            return [float(value) for value in values[0]]
        return None
    label = row.get("output_label", "")
    return gt_box(data_root / label, width, height) if label else None


def truth_boxes(row: dict[str, str], width: int, height: int, data_root: Path) -> list[dict[str, str | list[float]]]:
    """Return every GT plate box and its text for one source frame."""
    if row.get("bbox_json"):
        values = json.loads(row["bbox_json"])
        texts = json.loads(row["gt_texts_json"]) if row.get("gt_texts_json") else []
        return [
            {"box": [float(value) for value in box], "text": str(texts[index] if index < len(texts) else row.get("plate_text_normalized", ""))}
            for index, box in enumerate(values)
            if isinstance(box, list) and len(box) == 4
        ]
    single = truth_box(row, width, height, data_root)
    return [{"box": single, "text": row.get("plate_text_normalized", "")} ] if single is not None else []


def load_multiframe_test_rows() -> list[dict[str, str]]:
    dataset = ROOT / "datasets" / "experiments" / "multiframe_ocr_v1"
    rows: list[dict[str, str]] = []
    with (dataset / "frames.csv").open(encoding="utf-8", newline="") as handle:
        for frame in csv.DictReader(handle):
            if frame.get("split") != "test":
                continue
            annotation = ET.parse(ROOT / Path(frame["source_path"]).with_suffix(".xml")).getroot()
            boxes = []
            for obj in annotation.findall(".//object"):
                box = obj.find("bndbox")
                if box is None:
                    continue
                values = [box.findtext(name) for name in ("xmin", "ymin", "xmax", "ymax")]
                if any(value is None for value in values):
                    continue
                boxes.append([float(value) for value in values])
            if not boxes:
                continue
            rows.append({
                "output_image": frame["source_path"],
                "output_label": "",
                "bbox_json": json.dumps(boxes),
                "plate_text_normalized": frame["gt_text"],
                "track_id": frame["track_id"],
            })
    return rows


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

    def postprocessed_text(value: str) -> tuple[str, str]:
        normalized = eval_mod.normalize_plate_text(value or "")
        alternatives = eval_mod.generate_grammar_alternatives(normalized)
        best = alternatives[0][0] if alternatives else normalized
        return normalized, best

    model = YOLO(str(model_path))
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    latencies: list[float] = []
    predictions: list[str] = []
    truths: list[str] = []
    matched_flags: list[bool] = []
    tp = fp = fn = 0
    detector_miss = ocr_wrong = ocr_exact = ocr_raw_exact = 0
    for row in rows:
        image = cv2.imread(str(data_root / row["output_image"]))
        if image is None:
            continue
        height, width = image.shape[:2]
        ground_truths = truth_boxes(row, width, height, data_root)
        started = time.perf_counter()
        result = model.predict(source=image, imgsz=640, conf=0.25, device=device, verbose=False)[0]
        detections: list[dict[str, Any]] = []
        if result.boxes is not None:
            for box, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                if int(cls) == 0:
                    detections.append({"box": [float(value) for value in box[:4]], "conf": float(confidence)})
        matches = greedy_one_to_one_matches(detections, [entry["box"] for entry in ground_truths])
        matched_by_gt = {item["ground_truth_index"]: item for item in matches}
        tp += len(matches)
        fp += len(detections) - len(matches)
        fn += len(ground_truths) - len(matches)
        detector_miss += len(ground_truths) - len(matches)
        for gt_index, ground_truth in enumerate(ground_truths):
            match = matched_by_gt.get(gt_index)
            matched = match is not None
            truth_text = str(ground_truth["text"])
            truths.append(truth_text)
            matched_flags.append(matched)
            text = ""
            if match is not None:
                matched_box = detections[match["prediction_index"]]["box"]
                x1, y1, x2, y2 = [int(round(value)) for value in matched_box]
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
                crop = image[y1:y2, x1:x2]
                prepared, _ = eval_mod.preprocess_crop(crop, variant="raw", target_height=48)
                text, _, _ = recognizer.recognize(prepared)
                text = text or ""
                normalized_text, postprocessed = postprocessed_text(text)
                normalized_truth = eval_mod.normalize_plate_text(truth_text)
                ocr_raw_exact += int(normalized_text == normalized_truth)
                ocr_exact += int(postprocessed == normalized_truth)
                ocr_wrong += int(postprocessed != normalized_truth)
            predictions.append(text)
        latencies.append((time.perf_counter() - started) * 1000)
    ocr_metrics = eval_mod.calculate_metrics(predictions, truths)
    # Missed plates remain empty predictions, so the complete-chain metrics use
    # every GT plate while conditional OCR metrics use matched GT plates only.
    conditional_predictions = [prediction for prediction, matched in zip(predictions, matched_flags) if matched]
    conditional_truths = [truth for truth, matched in zip(truths, matched_flags) if matched]
    conditional_metrics = eval_mod.calculate_metrics(conditional_predictions, conditional_truths)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    gt_count = len(truths)
    matched_gt_count = tp
    return {
        "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        "model_sha256": sha256(model_path),
        "images": len(rows),
        "detector": {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 6), "recall": round(recall, 6),
            "f1": round(2 * precision * recall / max(1e-12, precision + recall), 6),
        },
        "recognition_chain": {
            "gt_count": gt_count,
            "detector_matched_gt_count": matched_gt_count,
            "DETECTOR_MISS": detector_miss,
            "OCR_WRONG": ocr_wrong,
            "OCR_EXACT": ocr_exact,
            "OCR_RAW_EXACT": ocr_raw_exact,
            "conditional_ocr_exact": round(ocr_exact / max(1, matched_gt_count), 6),
            "complete_chain_exact": round(ocr_exact / max(1, gt_count), 6),
            "raw_exact": ocr_metrics.get("raw_exact_accuracy", 0.0),
            "postprocessed_exact": ocr_metrics.get("postprocessed_exact_accuracy", 0.0),
            "character_accuracy": ocr_metrics.get("postprocessed_character_accuracy", 0.0),
            "cer": ocr_metrics.get("postprocessed_cer", 0.0),
            "empty_read_rate": ocr_metrics.get("empty_read_rate", 0.0),
            "conditional_postprocessed_exact": conditional_metrics.get("postprocessed_exact_accuracy", 0.0),
            "conditional_postprocessed_cer": conditional_metrics.get("postprocessed_cer", 0.0),
        },
        "latency_ms": {"mean": round(statistics.mean(latencies), 3) if latencies else None, "p50": round(statistics.median(latencies), 3) if latencies else None, "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3) if latencies else None, "p99": round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 3) if latencies else None},
        "fps": round(1000 / statistics.mean(latencies), 3) if latencies and statistics.mean(latencies) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="models/plate/production/best.pt")
    parser.add_argument("--data", default="multiframe-test", help="multiframe-test or a detection derivative with non-empty OCR text")
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    import cv2  # type: ignore
    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    if args.data == "multiframe-test":
        data_root = ROOT
        rows = load_multiframe_test_rows()
        dataset_name = "datasets/experiments/multiframe_ocr_v1 (source images; test sequences)"
    else:
        data_root = (ROOT / args.data).resolve()
        with (data_root / "manifest.csv").open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("split") == "test"]
        if not rows or not all(row.get("plate_text_normalized", "").strip() for row in rows):
            raise ValueError("Refusing E2E OCR evaluation: selected manifest does not have complete non-empty plate_text_normalized ground truth for every test row")
        dataset_name = str(data_root.relative_to(ROOT)).replace("\\", "/")
    results = []
    for value in args.models.split(","):
        model_path = (ROOT / value.strip()).resolve()
        results.append(run_model(model_path, rows, data_root, args.device, eval_mod, rec_mod))
    report = {
        "status": "COMPLETE_WITH_TEXT_GT",
        "dataset": dataset_name,
        "split": "test",
        "pipeline": "plate recognition chain: detector -> predicted AABB crop -> PP-OCRv5 mobile -> existing structural decoder metrics",
        "matching": "all class-0 predictions and all GT boxes are greedily matched one-to-one at IoU >= 0.5",
        "p5_safety": {"status": "UNAVAILABLE_NO_NEGATIVE_VEHICLE_OR_BACKGROUND_GT", "false_positive_rate": None, "note": "The held-out sequence test contains positive plate objects only; it cannot support a safety/P5 FPR claim."},
        "results": results,
    }
    output = ROOT / "reports" / "p11_5" / "end_to_end_evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (ROOT / "reports" / "p11_5" / "end_to_end_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "model", "model_sha256", "images", "detector_tp", "detector_fp", "detector_fn",
            "detector_precision", "detector_recall", "detector_f1", "gt_count",
            "detector_matched_gt_count", "DETECTOR_MISS", "OCR_WRONG", "OCR_EXACT",
            "conditional_ocr_exact", "complete_chain_exact", "raw_exact", "postprocessed_exact",
            "character_accuracy", "cer", "empty_read_rate", "p50_ms", "p95_ms", "crops_per_sec",
        ]
        for row in results:
            detector = row["detector"]
            chain = row["recognition_chain"]
            latency = row["latency_ms"]
            row.update({
                "detector_tp": detector["tp"], "detector_fp": detector["fp"], "detector_fn": detector["fn"],
                "detector_precision": detector["precision"], "detector_recall": detector["recall"], "detector_f1": detector["f1"],
                "gt_count": chain["gt_count"], "detector_matched_gt_count": chain["detector_matched_gt_count"],
                "DETECTOR_MISS": chain["DETECTOR_MISS"], "OCR_WRONG": chain["OCR_WRONG"], "OCR_EXACT": chain["OCR_EXACT"],
                "conditional_ocr_exact": chain["conditional_ocr_exact"], "complete_chain_exact": chain["complete_chain_exact"],
                "raw_exact": chain["raw_exact"], "postprocessed_exact": chain["postprocessed_exact"],
                "character_accuracy": chain["character_accuracy"], "cer": chain["cer"], "empty_read_rate": chain["empty_read_rate"],
                "p50_ms": latency["p50"], "p95_ms": latency["p95"], "crops_per_sec": row["fps"],
            })
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
