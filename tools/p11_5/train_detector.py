"""Safe isolated Ultralytics detector training for P11.5.

The legacy detector trainer copies weights into production paths.  This
runner never does that: every run gets its own directory under
``runs/p11_5`` and a machine-readable registry record.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments" / "p11_5" / "registry.csv"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def append_registry(record: dict[str, Any]) -> None:
    fields = [
        "run_id", "task", "model_family", "variant", "dataset_sha256", "seed",
        "epochs", "batch", "imgsz", "precision", "device", "training_time_seconds",
        "metrics_json", "weight_path", "weight_sha256", "status", "decision", "notes",
    ]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    existing = REGISTRY.exists() and REGISTRY.stat().st_size > 0
    with REGISTRY.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not existing:
            writer.writeheader()
        writer.writerow({field: record.get(field, "") for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--weights", required=True, help="Existing local .pt or an Ultralytics model name")
    parser.add_argument("--data", default="datasets/experiments/plate_detection_v2_strict/dataset.yaml")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--seed", type=int, default=115)
    parser.add_argument("--device", default="0")
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--accumulate", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from ultralytics import YOLO  # type: ignore

    data_path = (ROOT / args.data).resolve()
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    run_root = ROOT / "runs" / "p11_5" / args.run_id
    if run_root.exists() and any(run_root.rglob("*")):
        raise FileExistsError(f"Refusing to overwrite existing run: {run_root}")
    config_root = ROOT / "runs" / "p11_5" / "_configs"
    config_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    input_path = Path(args.weights)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    input_sha = sha256(input_path)
    manifest_path = data_path.parent / "manifest.csv"
    dataset_sha = sha256(manifest_path)
    record: dict[str, Any] = {
        "run_id": args.run_id,
        "task": "P3_detection",
        "model_family": "Ultralytics",
        "variant": Path(args.weights).stem,
        "dataset_sha256": dataset_sha or "",
        "seed": args.seed,
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "precision": "amp" if args.amp else "fp32",
        "device": args.device,
        "training_time_seconds": "",
        "metrics_json": "",
        "weight_path": "",
        "weight_sha256": "",
        "status": "RUNNING",
        "decision": "",
        "notes": f"input={args.weights};input_sha256={input_sha or 'unresolved'};started_at={started_at}",
    }
    # Ultralytics resolves ``path: .`` from the process working directory in
    # this release.  Give every run an absolute-path dataset YAML so a run is
    # reproducible regardless of where the command is launched.
    dataset_config = config_root / f"{args.run_id}_dataset.yaml"
    dataset_config.write_text(
        "path: " + data_path.parent.as_posix() + "\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: license_plate\n",
        encoding="utf-8",
    )
    run_config = config_root / f"{args.run_id}.json"
    run_config.write_text(json.dumps({**record, "data": str(dataset_config), "input_sha256": input_sha}, indent=2), encoding="utf-8")
    try:
        model = YOLO(str(input_path) if input_sha else args.weights)
        train_kwargs = {
            "data": str(dataset_config),
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "patience": args.patience,
            "workers": args.workers,
            "amp": args.amp,
            "cache": False,
            "plots": False,
            "project": str(ROOT / "runs" / "p11_5"),
            "name": args.run_id,
            "exist_ok": False,
            "seed": args.seed,
            "deterministic": True,
            "val": True,
            "verbose": True,
        }
        if args.accumulate > 1:
            train_kwargs["accumulate"] = args.accumulate
        results = model.train(**train_kwargs)
        elapsed = time.perf_counter() - started
        save_dir = Path(getattr(getattr(model, "trainer", None), "save_dir", run_root))
        best = save_dir / "weights" / "best.pt"
        last = save_dir / "weights" / "last.pt"
        chosen = best if best.is_file() else last
        metrics = json_value(getattr(results, "results_dict", {}))
        record.update({
            "training_time_seconds": round(elapsed, 3),
            "metrics_json": json.dumps(metrics, sort_keys=True),
            "weight_path": chosen.relative_to(ROOT).as_posix() if chosen.is_file() else "",
            "weight_sha256": sha256(chosen) or "",
            "status": "TRAINED" if chosen.is_file() else "TRAINED_WEIGHT_MISSING",
            "decision": "PENDING_EVALUATION",
        })
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "train_result.json").write_text(json.dumps({**record, "metrics": metrics}, indent=2), encoding="utf-8")
        append_registry(record)
        print(json.dumps({"run_id": args.run_id, "status": record["status"], "weight_path": record["weight_path"], "training_time_seconds": elapsed, "metrics": metrics}, indent=2))
        return 0 if chosen.is_file() else 2
    except RuntimeError as exc:
        elapsed = time.perf_counter() - started
        message = str(exc)
        record.update({
            "training_time_seconds": round(elapsed, 3),
            "status": "OOM" if "out of memory" in message.lower() or "cuda" in message.lower() else "FAILED",
            "decision": "TRAINING_REQUIRES_LARGER_GPU" if "out of memory" in message.lower() else "INVESTIGATE",
            "notes": record["notes"] + ";error=" + message[:500].replace("\n", " "),
        })
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / "train_failure.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        append_registry(record)
        print(json.dumps(record, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
