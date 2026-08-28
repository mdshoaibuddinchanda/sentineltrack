"""Create a conservative no-cross-split-pHash detection derivative.

The previously built Detection V2 remains untouched as an upstream artifact.
This derivative removes non-canonical source rows whose exact perceptual hash
also occurs in another split.  Canonical ``plate_detection`` rows retain their
locked split assignment, so duplicate-source copies cannot leak into train
from a test image.  The rule is intentionally conservative and is recorded
in the resulting manifest and report.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "datasets" / "experiments" / "plate_detection_v2"
OUTPUT = ROOT / "datasets" / "experiments" / "plate_detection_v2_strict"
REPORT = ROOT / "reports" / "p11_5" / "dataset" / "DETECTION_V2_STRICT_FREEZE.json"


def copy_or_link(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def main() -> int:
    manifest = UPSTREAM / "manifest.csv"
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if OUTPUT.exists() and any(OUTPUT.rglob("*")):
        raise FileExistsError(f"Refusing to overwrite non-empty output: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    phash_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("perceptual_hash"):
            phash_groups[row["perceptual_hash"]].append(row)
    cross_groups = {
        value: group for value, group in phash_groups.items()
        if len({row.get("split", "") for row in group}) > 1
    }
    excluded: list[dict[str, str]] = []
    selected: list[dict[str, str]] = []
    for row in rows:
        if row.get("perceptual_hash") in cross_groups and row.get("source_dataset") != "plate_detection":
            excluded.append(row)
        else:
            selected.append(row)

    link_modes = Counter()
    split_counts = Counter()
    source_counts = Counter()
    output_rows: list[dict[str, Any]] = []
    for row in selected:
        source_image = UPSTREAM / row["output_image"]
        source_label = UPSTREAM / row["output_label"]
        image_out = OUTPUT / row["output_image"]
        label_out = OUTPUT / row["output_label"]
        link_modes["image_" + copy_or_link(source_image, image_out)] += 1
        link_modes["label_" + copy_or_link(source_label, label_out)] += 1
        output_rows.append({**row, "output_image": image_out.relative_to(OUTPUT).as_posix(), "output_label": label_out.relative_to(OUTPUT).as_posix()})
        split_counts[row.get("split", "")] += 1
        source_counts[row.get("source_dataset", "")] += 1

    fields = list(output_rows[0])
    with (OUTPUT / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    with (OUTPUT / "split_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    (OUTPUT / "dataset.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    stats = {
        "status": "FROZEN_READY_FOR_TRAINING",
        "upstream_manifest": manifest.relative_to(ROOT).as_posix(),
        "upstream_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "selected_unique_images": len(output_rows),
        "excluded_exact_phash_rows": len(excluded),
        "excluded_exact_phash_groups": len(cross_groups),
        "split_counts": dict(split_counts),
        "source_contribution": dict(source_counts),
        "link_modes": dict(link_modes),
        "policy": "retain canonical plate_detection rows; exclude non-canonical rows in exact cross-split pHash groups",
        "notes": [
            "The upstream plate_detection_v2 derivative was not modified.",
            "This strict derivative is the training/evaluation dataset for P11.5 detector comparisons.",
            "pHash-near candidates with nonzero Hamming distance remain screening evidence and are reported separately.",
        ],
    }
    (OUTPUT / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (OUTPUT / "README.md").write_text(
        "# Plate Detection V2 Strict\n\n"
        "Conservative derivative of `plate_detection_v2` for P11.5 training. "
        "Non-canonical rows in exact cross-split perceptual-hash groups are excluded; the upstream derivative and frozen V1 sources are unchanged.\n",
        encoding="utf-8",
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
