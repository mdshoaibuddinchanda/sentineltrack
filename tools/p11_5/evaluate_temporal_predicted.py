"""Run paired temporal OCR on detector-predicted crops from held-out sequences."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from detection_matching import greedy_one_to_one_matches


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "experiments" / "multiframe_ocr_v1"
REPORT_DIR = ROOT / "reports" / "p11_5"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1]) + max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1]) - inter
    return inter / union if union else 0.0


def metric(predictions: list[str], truths: list[str], weighted_levenshtein: Any, normalize: Any) -> dict[str, Any]:
    normalized_predictions = [normalize(value) for value in predictions]
    normalized_truths = [normalize(value) for value in truths]
    exact = sum(pred == truth for pred, truth in zip(normalized_predictions, normalized_truths))
    distance = sum(weighted_levenshtein(pred, truth, confusion_cost=1.0) for pred, truth in zip(normalized_predictions, normalized_truths))
    gt_chars = sum(max(1, len(truth)) for truth in normalized_truths)
    char_correct = sum(sum(a == b for a, b in zip(pred, truth)) for pred, truth in zip(normalized_predictions, normalized_truths))
    return {"tracks": len(truths), "exact_matches": exact, "exact_accuracy": round(exact / max(1, len(truths)), 6), "character_accuracy": round(char_correct / max(1, gt_chars), 6), "cer": round(distance / max(1, gt_chars), 6)}


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with (DATASET / "frames.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("split") != "test":
                continue
            xml_path = ROOT / Path(row["source_path"]).with_suffix(".xml")
            import xml.etree.ElementTree as ET
            root = ET.parse(xml_path).getroot()
            boxes = []
            for obj in root.findall(".//object"):
                box = obj.find("bndbox")
                if box is None:
                    continue
                values = [box.findtext(name) for name in ("xmin", "ymin", "xmax", "ymax")]
                if any(value is None for value in values):
                    continue
                boxes.append([float(value) for value in values])
            if not boxes:
                continue
            row["bboxes"] = json.dumps(boxes)
            rows.append(row)
    return rows


def crop_from_box(image: Any, box: list[float] | None) -> Any:
    if box is None:
        return None
    height, width = image.shape[:2]
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    return image[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt")
    parser.add_argument("--device", default="0")
    args = parser.parse_args()

    import cv2  # type: ignore
    from ultralytics import YOLO  # type: ignore

    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    models_mod = importlib.import_module("04_plate_ocr.models")
    voter_mod = importlib.import_module("04_plate_ocr.voting")
    temporal_mod = importlib.import_module("tools.p11_5.temporal")
    quality_mod = importlib.import_module("tools.p11_5.quality")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    rows = load_rows()
    model_path = (ROOT / args.weights).resolve()
    model = YOLO(str(model_path))
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tp = fp = fn = 0
    latencies: list[float] = []
    for index, row in enumerate(rows, start=1):
        image = cv2.imread(str(ROOT / row["source_path"]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        truths_for_frame = json.loads(row["bboxes"])
        truth_texts = [row.get("gt_text", "")] * len(truths_for_frame)
        started = time.perf_counter()
        result = model.predict(source=image, imgsz=640, conf=0.25, device=args.device, verbose=False)[0]
        latencies.append((time.perf_counter() - started) * 1000)
        detections: list[dict[str, Any]] = []
        if result.boxes is not None:
            for box, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                if int(cls) == 0:
                    detections.append({"box": [float(value) for value in box[:4]], "conf": float(confidence)})
        matches = greedy_one_to_one_matches(detections, truths_for_frame)
        matched_by_gt = {item["ground_truth_index"]: item for item in matches}
        tp += len(matches)
        fp += len(detections) - len(matches)
        fn += len(truths_for_frame) - len(matches)
        for gt_index, truth in enumerate(truths_for_frame):
            match = matched_by_gt.get(gt_index)
            if match is not None:
                matched_box = detections[match["prediction_index"]]["box"]
                crop = crop_from_box(image, matched_box)
                prepared, _ = eval_mod.preprocess_crop(crop, variant="raw", target_height=48)
                text, confidence, char_confidences = recognizer.recognize(prepared)
                quality = quality_mod.crop_quality(crop)
            else:
                text, confidence, char_confidences = "", 0.0, []
                quality = {"score": 0.0}
            observations[row["track_id"]].append({
                "text": text or "", "confidence": float(confidence or 0.0), "quality": float(quality.get("score", 0.0)),
                "frame_index": int(row["frame_index"]), "char_confidences": char_confidences, "gt": truth_texts[gt_index],
            })
        if index % 50 == 0 or index == len(rows):
            print(f"{model_path.name}: predicted temporal {index}/{len(rows)}", flush=True)

    def methods(items: list[dict[str, Any]]) -> dict[str, str]:
        out: dict[str, str] = {}
        best = temporal_mod.best_observation(items)
        out["single_best"] = best["text"] if best else ""
        weighted = temporal_mod.temporal_vote(items, min_support=1)
        out["weighted_vote"] = weighted.get("selected_text") or ""
        candidates = [(item["text"], max(0.01, item["confidence"] * item["quality"])) for item in items if item["text"]]
        out["character_fusion"] = voter_mod.resolve_character_consensus(candidates)
        hypotheses = []
        for item_index, item in enumerate(items):
            hypotheses.append(models_mod.OCRHypothesis(
                camera_id="multiframe_v1", track_id=item_index, stream_epoch=0, pts_ms=float(item["frame_index"]),
                raw_text=item["text"], normalized_text=eval_mod.normalize_plate_text(item["text"]),
                ocr_confidence=item["confidence"], crop_quality=item["quality"],
                grammar_score=eval_mod.score_indian_grammar(eval_mod.normalize_plate_text(item["text"])),
                character_confidences=item.get("char_confidences", []), plate_width=0, plate_height=0,
            ))
        voted = voter_mod.MultiFramePlateVoter(min_support_count=1).vote(hypotheses)
        out["current_voter"] = voted.best_text or ""
        return out

    paired_ids = sorted(track_id for track_id, items in observations.items() if len(items) >= 8)
    rows_out: list[dict[str, Any]] = []
    for window in (1, 3, 5, 8):
        predictions: dict[str, list[str]] = defaultdict(list)
        truths: list[str] = []
        for track_id in paired_ids:
            sample = observations[track_id][:window]
            truths.append(sample[0]["gt"])
            for method, value in methods(sample).items():
                predictions[method].append(value)
        for method, values in sorted(predictions.items()):
            rows_out.append({"window": window, "method": method, "population": "test_tracks_with_at_least_8_source_frames", "eligible_tracks": len(paired_ids), **metric(values, truths, eval_mod.weighted_levenshtein, eval_mod.normalize_plate_text)})

    output = {
        "status": "COMPLETE", "dataset": str(DATASET.relative_to(ROOT)).replace("\\", "/"), "split": "test",
        "weights": args.weights.replace("\\", "/"), "tracks": len(observations), "frames": sum(len(items) for items in observations.values()),
        "detector": {"tp": tp, "fp": fp, "fn": fn, "precision": round(tp / max(1, tp + fp), 6), "recall": round(tp / max(1, tp + fn), 6), "f1": round(2 * tp / max(1, 2 * tp + fp + fn), 6), "mean_latency_ms": round(statistics.mean(latencies), 3) if latencies else None, "matching": "all class-0 predictions and all GT boxes greedily matched one-to-one at IoU >= 0.5"},
        "recognizer": "PP-OCRv5 mobile on predicted AABB crops", "paired_population": {"minimum_window": 8, "track_count": len(paired_ids)}, "results": rows_out,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "temporal_predicted_e2e.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (REPORT_DIR / "temporal_predicted_e2e_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["window", "method", "population", "eligible_tracks", "tracks", "exact_matches", "exact_accuracy", "character_accuracy", "cer"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
