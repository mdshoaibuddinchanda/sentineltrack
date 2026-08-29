"""Evaluate an isolated YOLO OBB candidate on the frozen strict OBB test split."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", default="datasets/experiments/plate_detection_obb_v2_strict")
    parser.add_argument("--split", default="test")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from ultralytics import YOLO  # type: ignore

    data_root = (ROOT / args.data).resolve()
    if data_root.is_file():
        data_root = data_root.parent
    weights = (ROOT / args.weights).resolve()
    config = ROOT / "reports" / "p11_5" / "obb_eval" / f"{args.run_id}_dataset.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "path: " + data_root.as_posix() + "\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    model = YOLO(str(weights))
    metrics = model.val(
        data=str(config),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=0,
        plots=False,
        verbose=False,
        project=str(ROOT / "runs" / "p11_5" / "obb_eval"),
        name=f"{args.run_id}_{args.split}_{args.imgsz}",
        exist_ok=False,
    )
    metric_box: Any = getattr(metrics, "box", metrics)
    result = {
        "run_id": args.run_id,
        "weights": args.weights,
        "weights_sha256": sha256(weights),
        "dataset": str(data_root.relative_to(ROOT)).replace("\\", "/"),
        "dataset_manifest_sha256": sha256(data_root / "manifest.csv"),
        "split": args.split,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "task": "OBB_detection",
        "map50": float(getattr(metric_box, "map50", 0.0)),
        "map50_95": float(getattr(metric_box, "map", 0.0)),
        "precision": float(getattr(metric_box, "mp", 0.0)),
        "recall": float(getattr(metric_box, "mr", 0.0)),
    }
    result["f1"] = round(2 * result["precision"] * result["recall"] / max(1e-12, result["precision"] + result["recall"]), 6)
    output = ROOT / "reports" / "p11_5" / "obb_eval" / f"{args.run_id}_{args.split}_{args.imgsz}.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
