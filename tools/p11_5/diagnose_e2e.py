"""Diagnose the detector-to-OCR handoff on the locked strict test split.

This is intentionally an aggregate-only diagnostic.  It does not write crops,
raw detector predictions, or model artifacts.  It compares the current
highest-confidence AABB path with offline oracle selection, padding, GT crops,
and (when supplied) an OBB model's perspective-warp crop.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - inter
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


def load_multiframe_test_rows() -> list[dict[str, str]]:
    """Load text-labelled held-out sequence frames with XML box supervision."""
    dataset = ROOT / "datasets" / "experiments" / "multiframe_ocr_v1"
    rows: list[dict[str, str]] = []
    with (dataset / "frames.csv").open(encoding="utf-8", newline="") as handle:
        for frame in csv.DictReader(handle):
            if frame.get("split") != "test":
                continue
            xml_path = ROOT / Path(frame["source_path"]).with_suffix(".xml")
            annotation = ET.parse(xml_path).getroot()
            box = annotation.find(".//object/bndbox")
            if box is None:
                continue
            values = [box.findtext(name) for name in ("xmin", "ymin", "xmax", "ymax")]
            if any(value is None for value in values):
                continue
            rows.append({
                "output_image": frame["source_path"],
                "output_label": "",
                "bbox_json": json.dumps([[float(value) for value in values]]),
                "plate_text_normalized": frame["gt_text"],
                "track_id": frame["track_id"],
            })
    return rows


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


def clip_box(box: Iterable[float], width: int, height: int, margin: int = 0) -> tuple[int, int, int, int] | None:
    values = list(box)
    if len(values) < 4:
        return None
    x1, y1, x2, y2 = [int(round(float(value))) for value in values[:4]]
    x1, y1 = max(0, x1 - margin), max(0, y1 - margin)
    x2, y2 = min(width, x2 + margin), min(height, y2 + margin)
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def crop_from_box(image: Any, box: list[float] | None, margin: int = 0) -> Any:
    if box is None:
        return None
    height, width = image.shape[:2]
    clipped = clip_box(box, width, height, margin)
    if clipped is None:
        return None
    x1, y1, x2, y2 = clipped
    return image[y1:y2, x1:x2]


def order_quad(points: Any) -> Any:
    import numpy as np  # type: ignore

    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = pts[:, 1] - pts[:, 0]
    ordered[0] = pts[np.argmin(sums)]  # top-left
    ordered[2] = pts[np.argmax(sums)]  # bottom-right
    ordered[1] = pts[np.argmin(diffs)]  # top-right
    ordered[3] = pts[np.argmax(diffs)]  # bottom-left
    return ordered


def warp_quad(image: Any, points: Any, padding: int = 0) -> Any:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    ordered = order_quad(points)
    tl, tr, br, bl = ordered
    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    height_right = float(np.linalg.norm(br - tr))
    height_left = float(np.linalg.norm(bl - tl))
    out_w = max(16, int(round(max(width_top, width_bottom))))
    out_h = max(8, int(round(max(height_right, height_left))))
    if out_w < out_h:
        # Keep the destination landscape so the recognizer sees the same
        # orientation as a normal plate crop.
        out_w, out_h = out_h, out_w
    destination = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(ordered, destination)
    warped = cv2.warpPerspective(image, transform, (out_w, out_h), borderMode=cv2.BORDER_REPLICATE)
    if padding:
        warped = cv2.copyMakeBorder(warped, padding, padding, padding, padding, cv2.BORDER_REPLICATE)
    return warped


def detection_items(result: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    boxes = getattr(result, "boxes", None)
    if boxes is not None:
        xyxy = as_list(getattr(boxes, "xyxy", None))
        conf = as_list(getattr(boxes, "conf", None))
        classes = as_list(getattr(boxes, "cls", None))
        for box, score, cls in zip(xyxy, conf, classes):
            if int(cls) == 0:
                values.append({"box": [float(v) for v in box[:4]], "conf": float(score), "kind": "aabb"})
    return values


def obb_items(result: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    obb = getattr(result, "obb", None)
    if obb is None:
        return values
    polygons = as_list(getattr(obb, "xyxyxyxy", None))
    conf = as_list(getattr(obb, "conf", None))
    classes = as_list(getattr(obb, "cls", None))
    for polygon, score, cls in zip(polygons, conf, classes):
        if int(cls) != 0:
            continue
        points = [[float(point[0]), float(point[1])] for point in polygon[:4]]
        values.append({
            "polygon": points,
            "box": [min(point[0] for point in points), min(point[1] for point in points), max(point[0] for point in points), max(point[1] for point in points)],
            "conf": float(score),
            "kind": "obb",
        })
    return values


def summarize_numbers(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p10": None, "median": None, "p90": None}
    ordered = sorted(values)
    def percentile(p: float) -> float:
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
        return ordered[index]
    return {"mean": round(statistics.mean(values), 4), "p10": round(percentile(0.10), 4), "median": round(statistics.median(values), 4), "p90": round(percentile(0.90), 4)}


def evaluate_crops(
    crops: list[Any],
    truths: list[str],
    eval_mod: Any,
    recognizer: Any,
    matched_mask: list[bool] | None = None,
) -> dict[str, Any]:
    prepared = []
    for crop in crops:
        image, _ = eval_mod.preprocess_crop(crop, variant="raw", target_height=48)
        prepared.append(image)
    started = time.perf_counter()
    # The deployable path and the reference benchmark call recognize() per
    # crop.  The ONNX model's dynamic-width batch path can decode a different
    # time horizon, so it is deliberately not used for this comparison.
    outputs = [recognizer.recognize(image) for image in prepared]
    elapsed = (time.perf_counter() - started) * 1000
    predictions = [item[0] or "" for item in outputs]
    all_metrics = eval_mod.calculate_metrics(predictions, truths)
    result: dict[str, Any] = {
        "all_images": all_metrics,
        "recognizer_batch_ms": round(elapsed, 3),
    }
    if matched_mask is not None:
        matched_predictions = [pred for pred, matched in zip(predictions, matched_mask) if matched]
        matched_truths = [truth for truth, matched in zip(truths, matched_mask) if matched]
        result["matched_detections"] = eval_mod.calculate_metrics(matched_predictions, matched_truths)
        result["matched_count"] = len(matched_predictions)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="models/plate/production/best.pt,runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt")
    parser.add_argument("--obb-model", default="")
    parser.add_argument("--data", default="datasets/experiments/plate_detection_v2_strict")
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def run_aabb_model(model_path: Path, rows: list[dict[str, str]], data_root: Path, device: str, eval_mod: Any, rec_mod: Any, cv2: Any) -> dict[str, Any]:
    from ultralytics import YOLO  # type: ignore

    model = YOLO(str(model_path))
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    truths: list[str] = []
    current_crops: dict[str, list[Any]] = {f"aabb_margin_{margin}": [] for margin in (0, 2, 4, 6, 8)}
    current_mask: list[bool] = []
    oracle_crops: list[Any] = []
    gt_crops: list[Any] = []
    oracle_mask: list[bool] = []
    ious: list[float] = []
    widths: list[float] = []
    heights: list[float] = []
    aspects: list[float] = []
    confidences: list[float] = []
    all_detections = 0
    fp = fn = tp = 0
    image_rows: list[tuple[dict[str, str], Any, list[float] | None]] = []
    for row in rows:
        image = cv2.imread(str(data_root / row["output_image"]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        h, w = image.shape[:2]
        image_rows.append((row, image, truth_box(row, w, h, data_root)))
    detector_started = time.perf_counter()
    for index, (row, image, truth) in enumerate(image_rows, start=1):
        result = model.predict(source=image, imgsz=640, conf=0.25, device=device, verbose=False)[0]
        detections = detection_items(result)
        all_detections += len(detections)
        current = max(detections, key=lambda item: item["conf"], default=None)
        oracle = max(detections, key=lambda item: iou(item["box"], truth) if truth is not None else 0.0, default=None)
        current_match = bool(current and truth is not None and iou(current["box"], truth) >= 0.5)
        if current_match:
            tp += 1
        else:
            if current is not None:
                fp += 1
            if truth is not None:
                fn += 1
        truths.append(row.get("plate_text_normalized", ""))
        current_mask.append(current_match)
        if current is not None and truth is not None:
            current_iou = iou(current["box"], truth)
            ious.append(current_iou)
            confidences.append(current["conf"])
            cw = max(0.0, current["box"][2] - current["box"][0])
            ch = max(0.0, current["box"][3] - current["box"][1])
            widths.append(cw)
            heights.append(ch)
            aspects.append(cw / max(ch, 1.0))
        for margin in (0, 2, 4, 6, 8):
            current_crops[f"aabb_margin_{margin}"].append(crop_from_box(image, current["box"] if current else None, margin))
        oracle_crops.append(crop_from_box(image, oracle["box"] if oracle else None, 0))
        gt_crops.append(crop_from_box(image, truth, 0))
        oracle_mask.append(bool(oracle and truth is not None and iou(oracle["box"], truth) >= 0.5))
        if index % 50 == 0 or index == len(image_rows):
            print(f"{model_path.name}: detector {index}/{len(image_rows)}", flush=True)

    detector_elapsed_ms = (time.perf_counter() - detector_started) * 1000

    crop_results = {name: evaluate_crops(crops, truths, eval_mod, recognizer, current_mask) for name, crops in current_crops.items()}
    crop_results["oracle_best_iou_aabb"] = evaluate_crops(oracle_crops, truths, eval_mod, recognizer, oracle_mask)
    crop_results["gt_aabb_oracle"] = evaluate_crops(gt_crops, truths, eval_mod, recognizer)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        "model_sha256": sha256(model_path),
        "images": len(truths),
        "detector": {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 6), "recall": round(recall, 6),
            "all_class0_detections": all_detections,
            "batch_elapsed_ms": round(detector_elapsed_ms, 3),
            "mean_latency_ms": round(detector_elapsed_ms / max(1, len(image_rows)), 3),
        },
        "current_high_conf_geometry": {
            "iou": summarize_numbers(ious),
            "confidence": summarize_numbers(confidences),
            "width_px": summarize_numbers(widths),
            "height_px": summarize_numbers(heights),
            "aspect_ratio": summarize_numbers(aspects),
        },
        "crop_results": crop_results,
        "interpretation": {
            "current_aabb_metrics_are_full_frame": True,
            "conditional_metrics_only_include_current_iou_ge_0_5": True,
            "gt_aabb_is_an_ocr_upper_bound_not_a_deployable_path": True,
        },
    }


def run_obb_model(model_path: Path, rows: list[dict[str, str]], data_root: Path, device: str, eval_mod: Any, rec_mod: Any, cv2: Any) -> dict[str, Any]:
    from ultralytics import YOLO  # type: ignore

    model = YOLO(str(model_path))
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    truths: list[str] = []
    aabb_crops: list[Any] = []
    warp_crops: list[Any] = []
    masks: list[bool] = []
    ious: list[float] = []
    warp_widths: list[float] = []
    warp_heights: list[float] = []
    tp = fp = fn = 0
    image_rows: list[tuple[dict[str, str], Any, list[float] | None]] = []
    for row in rows:
        image = cv2.imread(str(data_root / row["output_image"]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        h, w = image.shape[:2]
        image_rows.append((row, image, truth_box(row, w, h, data_root)))
    detector_started = time.perf_counter()
    for index, (row, image, truth) in enumerate(image_rows, start=1):
        result = model.predict(source=image, imgsz=640, conf=0.25, device=device, verbose=False)[0]
        detections = obb_items(result)
        current = max(detections, key=lambda item: item["conf"], default=None)
        current_match = bool(current and truth is not None and iou(current["box"], truth) >= 0.5)
        if current_match:
            tp += 1
        else:
            if current is not None:
                fp += 1
            if truth is not None:
                fn += 1
        truths.append(row.get("plate_text_normalized", ""))
        masks.append(current_match)
        if current is None:
            aabb_crops.append(None)
            warp_crops.append(None)
        else:
            aabb_crops.append(crop_from_box(image, current["box"], 0))
            warp = warp_quad(image, current["polygon"])
            warp_crops.append(warp)
            warp_heights.append(float(warp.shape[0]))
            warp_widths.append(float(warp.shape[1]))
            if truth is not None:
                ious.append(iou(current["box"], truth))
        if index % 50 == 0 or index == len(image_rows):
            print(f"{model_path.name}: detector {index}/{len(image_rows)}", flush=True)
    detector_elapsed_ms = (time.perf_counter() - detector_started) * 1000
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        "model_sha256": sha256(model_path),
        "images": len(truths),
        "detector": {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 6), "recall": round(recall, 6), "batch_elapsed_ms": round(detector_elapsed_ms, 3), "mean_latency_ms": round(detector_elapsed_ms / max(1, len(image_rows)), 3)},
        "predicted_obb_geometry": {"aabb_iou": summarize_numbers(ious), "warp_width_px": summarize_numbers(warp_widths), "warp_height_px": summarize_numbers(warp_heights)},
        "crop_results": {
            "obb_aabb": evaluate_crops(aabb_crops, truths, eval_mod, recognizer, masks),
            "obb_perspective_warp": evaluate_crops(warp_crops, truths, eval_mod, recognizer, masks),
        },
        "interpretation": {"obb_match_uses_polygon_aabb_iou_ge_0_5": True, "obb_perspective_warp_is_the_downstream_test": True},
    }


def main() -> int:
    args = parse_args()
    import cv2  # type: ignore

    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    if args.data == "multiframe-test":
        data_root = ROOT
        rows = load_multiframe_test_rows()
        dataset_name = "datasets/experiments/multiframe_ocr_v1 (source images; test sequences)"
        output_name = "e2e_crop_diagnosis_multiframe_test.json"
    else:
        data_root = (ROOT / args.data).resolve()
        with (data_root / "manifest.csv").open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("split") == "test"]
        if not rows or not all(row.get("plate_text_normalized", "").strip() for row in rows):
            raise ValueError("Refusing crop/OCR diagnosis: selected manifest does not have complete non-empty plate_text_normalized ground truth for every test row")
        dataset_name = str(data_root.relative_to(ROOT)).replace("\\", "/")
        output_name = "e2e_crop_diagnosis.json"
    results = [run_aabb_model((ROOT / value.strip()).resolve(), rows, data_root, args.device, eval_mod, rec_mod, cv2) for value in args.models.split(",") if value.strip()]
    obb_result = None
    if args.obb_model.strip():
        obb_result = run_obb_model((ROOT / args.obb_model.strip()).resolve(), rows, data_root, args.device, eval_mod, rec_mod, cv2)
    report = {
        "status": "COMPLETE",
        "dataset": dataset_name,
        "split": "test",
        "rows": len(rows),
        "purpose": "aggregate diagnosis of predicted detector crop to OCR accuracy collapse",
        "aabb_models": results,
        "obb_model": obb_result,
    }
    output = ROOT / "reports" / "p11_5" / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
