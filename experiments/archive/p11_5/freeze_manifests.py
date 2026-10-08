"""Freeze and validate the isolated P11.5 derivative manifests.

This is a read-only validation step.  It never edits a dataset manifest or
the frozen V1 sources; it records hashes, counts, path integrity, split
identity leakage, and perceptual-hash warnings for reproducible experiments.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "reports" / "p11_5" / "dataset"
DETECTION = ROOT / "datasets" / "experiments" / "plate_detection_v2"
OCR = ROOT / "datasets" / "experiments" / "plate_ocr_v2"
SOURCE_INVENTORY = ROOT / "datasets" / "experiments" / "manifests" / "source_inventory.csv"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def cross_split_values(rows: list[dict[str, str]], field: str) -> dict[str, list[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        value = (row.get(field) or "").strip()
        if value:
            values[value].add(row.get("split", ""))
    return {value: sorted(splits) for value, splits in values.items() if len(splits) > 1}


def hamming_distance(left: str, right: str) -> int | None:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except (TypeError, ValueError):
        return None


def cross_split_phash_pairs(rows: list[dict[str, str]], threshold: int = 8) -> dict[str, Any]:
    items = [(row.get("perceptual_hash", ""), row.get("split", "")) for row in rows]
    items = [(value, split) for value, split in items if value]
    exact: set[tuple[str, str, str]] = set()
    near_pairs = 0
    for index, (left, left_split) in enumerate(items):
        for right, right_split in items[index + 1 :]:
            if left_split == right_split:
                continue
            distance = hamming_distance(left, right)
            if distance is not None and distance <= threshold:
                near_pairs += 1
                exact.add((left, left_split, right_split))
    return {
        "threshold_bits": threshold,
        "cross_split_pair_count": near_pairs,
        "cross_split_exact_phash_group_count": len(exact),
        "interpretation": "Perceptual hashes are screening evidence, not identity proof; any nonzero count is retained for review.",
    }


def path_integrity(root: Path, rows: list[dict[str, str]]) -> dict[str, Any]:
    missing_images: list[str] = []
    missing_labels: list[str] = []
    for row in rows:
        image = root / (row.get("output_image") or "")
        label = root / (row.get("output_label") or "")
        if not image.is_file():
            missing_images.append(row.get("output_image", ""))
        if not label.is_file():
            missing_labels.append(row.get("output_label", ""))
    return {
        "rows": len(rows),
        "missing_images": missing_images[:20],
        "missing_image_count": len(missing_images),
        "missing_labels": missing_labels[:20],
        "missing_label_count": len(missing_labels),
    }


def freeze(name: str, root: Path, expected_counts: dict[str, int]) -> dict[str, Any]:
    manifest = root / "manifest.csv"
    rows = load_csv(manifest)
    split_counts = Counter(row.get("split", "") for row in rows)
    count_mismatches = {
        split: {"expected": expected, "actual": split_counts.get(split, 0)}
        for split, expected in expected_counts.items()
        if split_counts.get(split, 0) != expected
    }
    identity_field = "plate_identity"
    result: dict[str, Any] = {
        "status": "FROZEN",
        "dataset": name,
        "root": root.relative_to(ROOT).as_posix(),
        "manifest": manifest.relative_to(ROOT).as_posix(),
        "manifest_sha256": file_sha256(manifest),
        "row_count": len(rows),
        "split_counts": dict(split_counts),
        "expected_count_mismatches": count_mismatches,
        "path_integrity": path_integrity(root, rows),
        "cross_split_exact_sha256": cross_split_values(rows, "sha256"),
        "cross_split_identity": cross_split_values(rows, identity_field),
        "cross_split_phash": cross_split_phash_pairs(rows),
        "source_inventory_sha256": file_sha256(SOURCE_INVENTORY),
    }
    if name == "plate_ocr_v2":
        result["legacy_locked_test_rows"] = sum(
            row.get("split") == "expanded_test" and row.get("source_kind") == "legacy_frozen"
            for row in rows
        )
        result["legacy_locked_test_sha256"] = hashlib.sha256(
            "\n".join(sorted(row.get("sha256", "") for row in rows if row.get("split") == "expanded_test" and row.get("source_kind") == "legacy_frozen")).encode()
        ).hexdigest()
    hard_failures = [
        bool(count_mismatches),
        bool(result["path_integrity"]["missing_image_count"]),
        bool(result["path_integrity"]["missing_label_count"]),
        bool(result["cross_split_exact_sha256"]),
        bool(result["cross_split_identity"]),
    ]
    if any(hard_failures):
        result["status"] = "FREEZE_FAILED"
    elif result["cross_split_phash"]["cross_split_pair_count"]:
        result["status"] = "FROZEN_WITH_PHASH_REVIEW"
    return result


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    detection = freeze("plate_detection_v2", DETECTION, {"train": 4162, "val": 775, "test": 344})
    ocr = freeze("plate_ocr_v2", OCR, {"train": 1396, "expanded_val": 150, "expanded_test": 178})
    for name, result in (("DETECTION_V2_FREEZE.json", detection), ("OCR_V2_FREEZE.json", ocr)):
        (REPORT_DIR / name).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"detection": detection, "ocr": ocr}, indent=2))
    return 0 if detection["status"] != "FREEZE_FAILED" and ocr["status"] != "FREEZE_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
