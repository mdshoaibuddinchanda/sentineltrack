"""Safe isolated YOLO11-OBB training for the P11.5 angled-plate stage."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.archive.p11_5.train_detector import append_registry, sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--weights", default="yolo11s-obb.pt")
    parser.add_argument("--data", default="datasets/experiments/plate_detection_obb_v2_strict")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--patience", type=int, default=7)
    args = parser.parse_args()
    from ultralytics import YOLO  # type: ignore

    data_root = (ROOT / args.data).resolve()
    data_yaml = data_root / "dataset.yaml"
    run_root = ROOT / "runs" / "p11_5" / args.run_id
    if run_root.exists() and any(run_root.rglob("*")):
        raise FileExistsError(run_root)
    config_dir = ROOT / "runs" / "p11_5" / "_configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = config_dir / f"{args.run_id}_obb_dataset.yaml"
    config.write_text("path: " + data_root.as_posix() + "\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n", encoding="utf-8")
    input_path = Path(args.weights)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    record = {
        "run_id": args.run_id, "task": "OBB_detection", "model_family": "Ultralytics-OBB", "variant": input_path.stem,
        "dataset_sha256": sha256(data_root / "manifest.csv") or "", "seed": 115, "epochs": args.epochs, "batch": args.batch,
        "imgsz": args.imgsz, "precision": "amp", "device": args.device, "training_time_seconds": "", "metrics_json": "",
        "weight_path": "", "weight_sha256": "", "status": "RUNNING", "decision": "", "notes": "official YOLO11s-OBB checkpoint; isolated run",
    }
    started = time.perf_counter()
    try:
        model = YOLO(str(input_path))
        results = model.train(data=str(config), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=args.device, patience=args.patience, workers=0, amp=True, cache=False, plots=False, project=str(ROOT / "runs" / "p11_5"), name=args.run_id, exist_ok=False, seed=115, deterministic=True, val=True, verbose=True)
        elapsed = time.perf_counter() - started
        save_dir = Path(getattr(getattr(model, "trainer", None), "save_dir", run_root))
        best = save_dir / "weights" / "best.pt"
        last = save_dir / "weights" / "last.pt"
        chosen = best if best.is_file() else last
        metrics = getattr(results, "results_dict", {})
        metrics = {str(k): (v.item() if hasattr(v, "item") else v) for k, v in metrics.items()}
        record.update({"training_time_seconds": round(elapsed, 3), "metrics_json": json.dumps(metrics, sort_keys=True), "weight_path": chosen.relative_to(ROOT).as_posix() if chosen.is_file() else "", "weight_sha256": sha256(chosen) or "", "status": "TRAINED" if chosen.is_file() else "TRAINED_WEIGHT_MISSING", "decision": "PENDING_EVALUATION"})
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "train_result.json").write_text(json.dumps({**record, "metrics": metrics}, indent=2), encoding="utf-8")
        append_registry(record)
        print(json.dumps(record, indent=2))
        return 0 if chosen.is_file() else 2
    except RuntimeError as exc:
        message = str(exc)
        record.update({"training_time_seconds": round(time.perf_counter() - started, 3), "status": "OOM" if "out of memory" in message.lower() else "FAILED", "decision": "TRAINING_REQUIRES_LARGER_GPU" if "out of memory" in message.lower() else "INVESTIGATE", "notes": message[:500].replace("\n", " ")})
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "train_failure.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        append_registry(record)
        print(json.dumps(record, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
