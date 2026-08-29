"""Measure the P1 vehicle detector operationally when no vehicle GT corpus exists."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, max(0, int(len(values) * fraction) - 1))]


def main() -> int:
    import torch  # type: ignore
    from ultralytics import YOLO  # type: ignore

    model_path = ROOT / "models" / "vehicle" / "yolo11m.pt"
    with (ROOT / "datasets" / "experiments" / "manifests" / "source_inventory.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    paths = [ROOT / row["source_path"] for row in rows if row.get("source_dataset") == "video_images"]
    paths = [path for path in paths if path.is_file()][:25]
    model = YOLO(str(model_path))
    device = 0 if torch.cuda.is_available() else "cpu"
    measurements: list[dict[str, Any]] = []
    for batch in (1, 2, 4):
        batches = [paths[index : index + batch] for index in range(0, len(paths), batch)]
        timings = []
        for cycle, batch_paths in enumerate(batches):
            if cycle < 2:
                model.predict(source=[str(path) for path in batch_paths], imgsz=960, batch=batch, device=device, verbose=False)
                continue
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            model.predict(source=[str(path) for path in batch_paths], imgsz=960, batch=batch, device=device, verbose=False)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            timings.append((time.perf_counter() - started) * 1000 / len(batch_paths))
        mean_ms = statistics.mean(timings) if timings else 0.0
        measurements.append({
            "batch": batch, "images": len(paths), "precision": "fp32", "imgsz": 960,
            "latency_ms_per_image": {"mean": round(mean_ms, 3), "p50": round(percentile(timings, 0.5) or 0, 3), "p95": round(percentile(timings, 0.95) or 0, 3), "p99": round(percentile(timings, 0.99) or 0, 3)},
            "fps": round(1000 / mean_ms, 3) if mean_ms else 0.0,
            "peak_vram_bytes": int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0,
        })
    report = {
        "status": "OPERATIONAL_PROBE_ONLY",
        "model": "models/vehicle/yolo11m.pt",
        "model_sha256": sha256(model_path),
        "device": "cuda:0" if torch.cuda.is_available() else "cpu",
        "dataset": "datasets/video_images",
        "probe_images": len(paths),
        "accuracy": {"status": "UNAVAILABLE_NO_VEHICLE_GT", "recall": None, "false_positive_rate": None, "note": "The source inventory has plate boxes, not vehicle detection boxes; no external COCO/vehicle GT was downloaded."},
        "measurements": measurements,
    }
    output = ROOT / "reports" / "p11_5" / "p1_operational.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
