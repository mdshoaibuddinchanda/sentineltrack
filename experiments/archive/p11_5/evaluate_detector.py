"""Evaluate an arbitrary P11.5 detector without touching production reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


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
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_left + area_right - inter
    return inter / union if union else 0.0


def read_gt(label: Path, width: int, height: int) -> list[list[float]]:
    boxes = []
    if not label.is_file():
        return boxes
    for line in label.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 5 or int(float(parts[0])) != 0:
            continue
        _, xc, yc, nw, nh = map(float, parts[:5])
        boxes.append([(xc - nw / 2) * width, (yc - nh / 2) * height, (xc + nw / 2) * width, (yc + nh / 2) * height])
    return boxes


def match(predictions: list[list[float]], ground_truth: list[list[float]], threshold: float = 0.5) -> tuple[int, int, int, list[bool]]:
    used = [False] * len(ground_truth)
    tp = fp = 0
    for prediction in predictions:
        candidate = max(((iou(prediction, truth), index) for index, truth in enumerate(ground_truth) if not used[index]), default=(0.0, -1))
        if candidate[0] >= threshold:
            tp += 1
            used[candidate[1]] = True
        else:
            fp += 1
    return tp, fp, sum(not value for value in used), used


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return float(statistics.quantiles(values, n=100, method="inclusive")[int(fraction * 100) - 1]) if len(values) > 1 else float(values[0])


def latency_probe(model: Any, paths: list[Path], imgsz: int, device: str, batch: int) -> dict[str, Any]:
    if not paths:
        return {"batch": batch, "samples": 0, "latency_ms_per_image": {}}
    import torch  # type: ignore
    timings: list[float] = []
    batches = [paths[index : index + batch] for index in range(0, min(len(paths), batch * 12), batch)]
    for cycle, batch_paths in enumerate(batches):
        if cycle < 2:
            model.predict(source=[str(path) for path in batch_paths], imgsz=imgsz, conf=0.25, device=device, verbose=False)
            continue
        if str(device) != "cpu" and torch.cuda.is_available():
            torch.cuda.synchronize()
        started = time.perf_counter()
        model.predict(source=[str(path) for path in batch_paths], imgsz=imgsz, conf=0.25, device=device, verbose=False)
        if str(device) != "cpu" and torch.cuda.is_available():
            torch.cuda.synchronize()
        timings.append((time.perf_counter() - started) * 1000 / len(batch_paths))
    return {
        "batch": batch,
        "samples": len(timings) * batch,
        "latency_ms_per_image": {
            "mean": round(statistics.mean(timings), 4) if timings else None,
            "p50": round(percentile(timings, 0.50), 4) if timings else None,
            "p90": round(percentile(timings, 0.90), 4) if timings else None,
            "p95": round(percentile(timings, 0.95), 4) if timings else None,
            "p99": round(percentile(timings, 0.99), 4) if timings else None,
        },
        "fps": round(1000 / statistics.mean(timings), 3) if timings and statistics.mean(timings) else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", default="datasets/experiments/plate_detection_v2_strict")
    parser.add_argument("--split", default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--device", default="0")
    parser.add_argument("--conf", type=float, default=0.25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import cv2  # type: ignore
    from ultralytics import YOLO  # type: ignore

    data_root = (ROOT / args.data).resolve()
    if data_root.is_file():
        data_root = data_root.parent
    manifest = data_root / "manifest.csv"
    rows = [row for row in csv.DictReader(manifest.open(encoding="utf-8", newline="")) if row.get("split") == args.split]
    model = YOLO(str((ROOT / args.weights).resolve()))
    paths = [data_root / row["output_image"] for row in rows]
    config = ROOT / "reports" / "p11_5" / "detector_eval" / f"{args.run_id}_dataset.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "path: " + data_root.as_posix() + "\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    # Stream the custom IoU pass before validation. Some Ultralytics releases
    # retain validation allocations on the model and can OOM on a second pass.
    import torch  # type: ignore
    def predictions_one_at_a_time():
        for path in paths:
            # This Ultralytics release may ignore ``batch=1`` for a large
            # source list and construct an oversized tensor. Keep the custom
            # correctness pass bounded to one image on small GPUs.
            yield model.predict(source=str(path), imgsz=args.imgsz, conf=args.conf, device=args.device, verbose=False)[0]

    predictions = predictions_one_at_a_time()
    totals = Counter()
    subsets: dict[str, Counter] = {"standard_aspect": Counter(), "square_or_tall": Counter(), "tiny_lt60": Counter(), "small_60_120": Counter(), "large_gt120": Counter()}
    for row, result in zip(rows, predictions):
        image = cv2.imread(str(data_root / row["output_image"]))
        if image is None:
            continue
        height, width = image.shape[:2]
        gt = read_gt(data_root / row["output_label"], width, height)
        pred = result.boxes.xyxy.cpu().tolist() if result.boxes is not None else []
        tp, fp, fn, matched = match(pred, gt)
        totals.update({"tp": tp, "fp": fp, "fn": fn})
        for index, truth in enumerate(gt):
            plate_width = truth[2] - truth[0]
            name = "standard_aspect" if plate_width / max(1.0, truth[3] - truth[1]) >= 2.2 else "square_or_tall"
            if plate_width < 60:
                size_name = "tiny_lt60"
            elif plate_width <= 120:
                size_name = "small_60_120"
            else:
                size_name = "large_gt120"
            for subset in {name, size_name}:
                subsets[subset]["gt"] += 1
                subsets[subset]["tp"] += int(matched[index])
    if str(args.device) != "cpu" and torch.cuda.is_available():
        torch.cuda.empty_cache()
    map_metrics = model.val(data=str(config), split=args.split, imgsz=args.imgsz, batch=args.batch, device=args.device, workers=0, plots=False, verbose=False, project=str(ROOT / "runs" / "p11_5" / "eval"), name=f"{args.run_id}_{args.split}_{args.imgsz}", exist_ok=False)
    precision = totals["tp"] / max(1, totals["tp"] + totals["fp"])
    recall = totals["tp"] / max(1, totals["tp"] + totals["fn"])
    result: dict[str, Any] = {
        "run_id": args.run_id,
        "weights": args.weights,
        "weights_sha256": sha256((ROOT / args.weights).resolve()),
        "dataset": str(data_root.relative_to(ROOT)).replace("\\", "/"),
        "dataset_manifest_sha256": sha256(manifest),
        "split": args.split,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "conf": args.conf,
        "images": len(rows),
        "tp": totals["tp"], "fp": totals["fp"], "fn": totals["fn"],
        "precision": round(precision, 6), "recall": round(recall, 6),
        "f1": round(2 * precision * recall / max(1e-12, precision + recall), 6),
        "map50": float(getattr(map_metrics.box, "map50", 0.0)),
        "map50_95": float(getattr(map_metrics.box, "map", 0.0)),
        "subsets": {name: {**dict(values), "recall": round(values["tp"] / max(1, values["gt"]), 6)} for name, values in subsets.items()},
        "latency": {str(batch): latency_probe(model, paths, args.imgsz, args.device, batch) for batch in (1, 2, 4)},
    }
    output = ROOT / "reports" / "p11_5" / "detector_eval" / f"{args.run_id}_{args.split}_{args.imgsz}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
