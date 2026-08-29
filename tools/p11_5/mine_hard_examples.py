"""Mine detector failure categories without persisting raw predictions or crops."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p11_5.evaluate_detector import iou, match, read_gt, sha256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", default="datasets/experiments/plate_detection_v2_strict")
    parser.add_argument("--split", default="val")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--top", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import cv2  # type: ignore
    from ultralytics import YOLO  # type: ignore

    data_root = (ROOT / args.data).resolve()
    if data_root.is_file():
        data_root = data_root.parent
    rows = [
        row for row in csv.DictReader((data_root / "manifest.csv").open(encoding="utf-8", newline=""))
        if row.get("split") == args.split
    ]
    model = YOLO(str((ROOT / args.weights).resolve()))
    def predictions_one_at_a_time():
        for row in rows:
            yield model.predict(
                source=str(data_root / row["output_image"]),
                imgsz=args.imgsz,
                conf=args.conf,
                device=args.device,
                verbose=False,
            )[0]

    predictions = predictions_one_at_a_time()
    category_counts: Counter[str] = Counter()
    hard_rows = []
    for row, result in zip(rows, predictions):
        image_path = data_root / row["output_image"]
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        height, width = image.shape[:2]
        ground_truth = read_gt(data_root / row["output_label"], width, height)
        boxes = result.boxes.xyxy.cpu().tolist() if result.boxes is not None else []
        _, false_positive, false_negative, matched = match(boxes, ground_truth)
        best_iou = max((max((iou(prediction, truth) for prediction in boxes), default=0.0) for truth in ground_truth), default=0.0)
        if false_negative and not boxes:
            category = "miss_no_prediction"
        elif false_negative:
            category = "partial_miss"
        elif false_positive:
            category = "false_positive"
        elif best_iou < 0.75:
            category = "low_iou_match"
        else:
            category = "clean"
        category_counts[category] += 1
        if category != "clean":
            image_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            hard_rows.append({
                "image_sha256": image_digest,
                "image": row.get("output_image", ""),
                "source_id": row.get("source_id", ""),
                "category": category,
                "ground_truth_count": len(ground_truth),
                "prediction_count": len(boxes),
                "false_positive_count": false_positive,
                "false_negative_count": false_negative,
                "best_iou": round(best_iou, 6),
                "width": width,
                "height": height,
            })
    hard_rows.sort(key=lambda row: (row["best_iou"], row["category"], row["image"]))
    output = ROOT / "reports" / "p11_5" / "hard_examples" / f"{args.run_id}_{args.split}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "AGGREGATE_HARD_EXAMPLES",
        "run_id": args.run_id,
        "weights": args.weights,
        "weights_sha256": sha256((ROOT / args.weights).resolve()),
        "dataset": str(data_root.relative_to(ROOT)).replace("\\", "/"),
        "split": args.split,
        "imgsz": args.imgsz,
        "images": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "hard_example_count": len(hard_rows),
        "hard_examples": hard_rows[: args.top],
        "raw_predictions_persisted": False,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "hard_examples"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
