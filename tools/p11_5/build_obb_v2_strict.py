"""Build the OBB counterpart of the strict detection derivative."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "datasets" / "experiments" / "plate_detection_obb_v1"
STRICT_DETECTION = ROOT / "datasets" / "experiments" / "plate_detection_v2_strict" / "manifest.csv"
OUTPUT = ROOT / "datasets" / "experiments" / "plate_detection_obb_v2_strict"
REPORT = ROOT / "reports" / "p11_5" / "dataset" / "OBB_V2_STRICT_FREEZE.json"
KNOWN_CORRUPT_JPEG_SHA256 = "75a3933904200f80e22f640dd37e947d7428937877306623cecc46086b7782c6"


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep OBB training/evaluation isolated from the upstream derivative.
    shutil.copy2(source, destination)
    return "copy"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_known_corrupt_jpeg(path: Path, source_sha256: str) -> bool:
    if source_sha256 != KNOWN_CORRUPT_JPEG_SHA256:
        return False
    ImageOps.exif_transpose(Image.open(path)).save(path, "JPEG", subsampling=0, quality=100)
    return True


def main() -> int:
    if OUTPUT.exists() and any(OUTPUT.rglob("*")):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {OUTPUT}")
    with STRICT_DETECTION.open(encoding="utf-8", newline="") as handle:
        allowed = {row["sha256"] for row in csv.DictReader(handle)}
    with (UPSTREAM / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("sha256") in allowed]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    links = Counter()
    splits = Counter()
    normalized_count = 0
    output_rows = []
    for row in rows:
        image_out = OUTPUT / row["image"]
        label_out = OUTPUT / row["label"]
        links["image_" + link_or_copy(UPSTREAM / row["image"], image_out)] += 1
        links["label_" + link_or_copy(UPSTREAM / row["label"], label_out)] += 1
        normalized_count += int(normalize_known_corrupt_jpeg(image_out, row.get("sha256", "")))
        output_rows.append({**row, "materialized_sha256": digest(image_out)})
        splits[row["split"]] += 1
    with (OUTPUT / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    (OUTPUT / "dataset.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    stats = {
        "status": "FROZEN_READY_FOR_TRAINING",
        "upstream_manifest_sha256": hashlib.sha256((UPSTREAM / "manifest.csv").read_bytes()).hexdigest(),
        "strict_detection_manifest_sha256": hashlib.sha256(STRICT_DETECTION.read_bytes()).hexdigest(),
        "selected_unique_images": len(output_rows),
        "split_counts": dict(splits),
        "link_modes": dict(links),
        "materialized_normalization_count": normalized_count,
        "materialized_normalization": "Ultralytics-compatible JPEG repair for the known source with missing EOI marker; source sha256 remains recorded in sha256.",
        "geometry": "polygon_min_area_rect where available; axis-aligned fallback retained from upstream",
    }
    (OUTPUT / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (OUTPUT / "README.md").write_text(
        "# Plate Detection OBB V2 Strict\n\n"
        "Strict no-exact-cross-split-pHash derivative of the audited OBB labels.\n",
        encoding="utf-8",
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
