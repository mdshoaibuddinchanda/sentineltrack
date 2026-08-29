"""Run small isolated synthetic-to-real detector screening ablations.

The generated corpus is deliberately staged with hard links/copies into an
ignored workspace directory.  Only aggregate metrics and the experiment
definition are reported; synthetic images and weights are never committed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "datasets" / "experiments" / "plate_detection_v2_strict"
SYNTHETIC = ROOT / "datasets" / "experiments" / "synthetic_indian_v2"
STAGING = ROOT / "datasets" / "experiments" / "_p11_5_synthetic_screening"
REPORT_DIR = ROOT / "reports" / "p11_5"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardlink_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        target.hardlink_to(source)
    except OSError:
        shutil.copyfile(source, target)


def stage_variant(name: str, synthetic_count: int, staging_root: Path, max_real_train: int) -> tuple[Path, dict[str, int]]:
    target = staging_root / name
    if target.exists() and any(target.rglob("*")):
        raise FileExistsError(f"Refusing to overwrite existing staging dataset: {target}")
    counts = {"real_train": 0, "synthetic_train": 0, "real_val": 0, "real_test": 0}
    for split in ("val", "test"):
        for image in sorted((REAL / "images" / split).glob("*")):
            label = REAL / "labels" / split / f"{image.stem}.txt"
            if not label.is_file():
                continue
            hardlink_or_copy(image, target / "images" / split / image.name)
            hardlink_or_copy(label, target / "labels" / split / label.name)
            counts[f"real_{split}"] += 1
    for image in sorted((REAL / "images" / "train").glob("*")):
        if max_real_train and counts["real_train"] >= max_real_train:
            break
        label = REAL / "labels" / "train" / f"{image.stem}.txt"
        if not label.is_file():
            continue
        hardlink_or_copy(image, target / "images" / "train" / image.name)
        hardlink_or_copy(label, target / "labels" / "train" / label.name)
        counts["real_train"] += 1
    if synthetic_count:
        candidates = sorted((SYNTHETIC / "images" / "train").glob("*.jpg"))
        selected = 0
        for image in candidates:
            label = SYNTHETIC / "detection_labels" / "train" / f"{image.stem}.txt"
            if not label.is_file():
                continue
            hardlink_or_copy(image, target / "images" / "train" / f"synthetic_{image.name}")
            hardlink_or_copy(label, target / "labels" / "train" / f"synthetic_{label.name}")
            selected += 1
            if selected >= synthetic_count:
                break
        counts["synthetic_train"] = selected
    return target, counts


def write_yaml(dataset: Path, run_id: str) -> Path:
    config = ROOT / "runs" / "p11_5" / "_configs" / f"{run_id}_synthetic_screen.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "path: " + dataset.as_posix() + "\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: license_plate\n",
        encoding="utf-8",
    )
    return config


def metric_summary(metrics: Any) -> dict[str, float]:
    box = getattr(metrics, "box", metrics)
    precision = float(getattr(box, "mp", 0.0))
    recall = float(getattr(box, "mr", 0.0))
    return {
        "precision": round(precision, 6), "recall": round(recall, 6),
        "f1": round(2 * precision * recall / max(1e-12, precision + recall), 6),
        "map50": round(float(getattr(box, "map50", 0.0)), 6),
        "map50_95": round(float(getattr(box, "map", 0.0)), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--device", default="0")
    parser.add_argument("--keep-staging", action="store_true")
    parser.add_argument("--max-real-train", type=int, default=0, help="optional real-train cap for a fast screening pilot")
    parser.add_argument("--staging-dir", default=str(STAGING), help="ignored staging directory; choose a new path after an interrupted run")
    args = parser.parse_args()

    from ultralytics import YOLO  # type: ignore

    real_train_count = len(list((REAL / "images" / "train").glob("*")))
    if args.max_real_train:
        real_train_count = min(real_train_count, args.max_real_train)
    variants = [("real_only_screen_e3", 0), ("real_plus_synthetic_25pct_screen_e3", round(real_train_count * 0.25)), ("real_plus_synthetic_50pct_screen_e3", round(real_train_count * 0.50))]
    staging_root = (ROOT / args.staging_dir).resolve() if not Path(args.staging_dir).is_absolute() else Path(args.staging_dir).resolve()
    results: list[dict[str, Any]] = []
    for name, synthetic_count in variants:
        dataset, counts = stage_variant(name, synthetic_count, staging_root, args.max_real_train)
        config = write_yaml(dataset, name)
        started = time.perf_counter()
        record: dict[str, Any] = {
            "run_id": name, "status": "RUNNING", "epochs": args.epochs, "batch": 1, "imgsz": 640,
            "device": args.device, "dataset": str(dataset.relative_to(ROOT)).replace("\\", "/"), "counts": counts,
            "real_train_limit": args.max_real_train or None,
            "initial_weights": args.weights.replace("\\", "/"), "initial_weights_sha256": sha256((ROOT / args.weights).resolve()),
        }
        try:
            model = YOLO(str((ROOT / args.weights).resolve()))
            model.train(
                data=str(config), epochs=args.epochs, imgsz=640, batch=1, device=args.device,
                patience=args.epochs, workers=0, amp=True, cache=False, plots=False,
                project=str(ROOT / "runs" / "p11_5"), name=name, exist_ok=False, seed=115,
                deterministic=True, val=True, verbose=False,
            )
            save_dir = Path(getattr(getattr(model, "trainer", None), "save_dir", ROOT / "runs" / "p11_5" / name))
            best = save_dir / "weights" / "best.pt"
            chosen = best if best.is_file() else save_dir / "weights" / "last.pt"
            eval_model = YOLO(str(chosen))
            test_metrics = eval_model.val(data=str(config), split="test", imgsz=640, batch=1, device=args.device, workers=0, plots=False, verbose=False, project=str(ROOT / "runs" / "p11_5" / "synthetic_screen_eval"), name=name, exist_ok=False)
            record.update({"status": "COMPLETE", "weight_path": str(chosen.relative_to(ROOT)).replace("\\", "/"), "weight_sha256": sha256(chosen), "test_metrics": metric_summary(test_metrics)})
        except RuntimeError as exc:
            record.update({"status": "OOM" if "out of memory" in str(exc).lower() or "cuda" in str(exc).lower() else "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        results.append(record)
        if not args.keep_staging:
            shutil.rmtree(dataset, ignore_errors=False)

    output = {"status": "COMPLETE_WITH_SCREENING_OR_BLOCKERS", "real_dataset": str(REAL.relative_to(ROOT)).replace("\\", "/"), "synthetic_dataset": str(SYNTHETIC.relative_to(ROOT)).replace("\\", "/"), "synthetic_manifest_sha256": sha256(SYNTHETIC / "manifest.json"), "screening_definition": "same candidate initialization; 3-epoch isolated real-only, +25%, +50% synthetic train screens; real strict val/test retained", "real_train_limit": args.max_real_train or None, "results": results}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "synthetic_screening.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (REPORT_DIR / "synthetic_screening.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["run_id", "status", "epochs", "batch", "imgsz", "device", "dataset", "elapsed_seconds", "weight_path", "weight_sha256", "test_metrics", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
