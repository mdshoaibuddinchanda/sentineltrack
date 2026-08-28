"""Build isolated P11.5 derivative datasets from the audited inventory.

This module is deliberately conservative:

* frozen V1 datasets are read only;
* exact duplicate image hashes are represented once;
* canonical plate_detection splits are preserved;
* raw sources are grouped by plate identity/sequence before splitting;
* VOC labels are converted to one ``license_plate`` class;
* OCR crops are generated from validated annotation boxes, never by hand.

Run after ``audit_dataset.py``:
    python tools/p11_5/build_v2.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "datasets"
INVENTORY = DATASETS / "experiments" / "manifests" / "source_inventory.csv"
DETECTION_V2 = DATASETS / "experiments" / "plate_detection_v2"
OBB_V1 = DATASETS / "experiments" / "plate_detection_obb_v1"
OCR_V2 = DATASETS / "experiments" / "plate_ocr_v2"


def safe_bool(value: str) -> bool:
    return value.lower() == "true"


def load_inventory() -> list[dict[str, Any]]:
    if not INVENTORY.exists():
        raise FileNotFoundError(f"Run audit_dataset.py first: {INVENTORY}")
    with INVENTORY.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    for record in records:
        record["width"] = int(record["width"] or 0)
        record["height"] = int(record["height"] or 0)
        record["plate_bbox"] = json.loads(record["plate_bbox"] or "[]")
        record["polygon"] = json.loads(record["polygon"] or "[]")
        record["quality_flags"] = json.loads(record["quality_flags"] or "[]")
        for key in ("usable_detection", "usable_ocr", "usable_multiframe"):
            record[key] = safe_bool(record[key])
    return records


def source_path(record: dict[str, Any]) -> Path:
    return ROOT / Path(record["source_path"])


def make_group_key(record: dict[str, Any]) -> str:
    if record.get("sequence_id"):
        return f"sequence:{record['sequence_id']}"
    if record.get("plate_identity"):
        return f"identity:{record['plate_identity']}"
    return f"sample:{record['sha256']}"


def deterministic_split(group_key: str) -> str:
    bucket = hashlib.sha256(group_key.encode("utf-8")).digest()[0]
    if bucket < 204:
        return "train"
    if bucket < 230:
        return "val"
    return "test"


def grouping_keys(record: dict[str, Any]) -> list[str]:
    keys = []
    if record.get("sequence_id"):
        keys.append(f"sequence:{record['sequence_id']}")
    if record.get("plate_identity"):
        keys.append(f"identity:{record['plate_identity']}")
    if not keys:
        keys.append(f"sample:{record['sha256']}")
    return keys


def grouped_assignments(records: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Connect sequence and identity keys so neither can cross a split."""
    parent: dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    record_keys: dict[str, list[str]] = {}
    for record in records:
        keys = grouping_keys(record)
        record_keys[record["sample_id"]] = keys
        for key in keys:
            find(key)
        for key in keys[1:]:
            union(keys[0], key)

    components: dict[str, list[str]] = defaultdict(list)
    for key in parent:
        components[find(key)].append(key)
    component_assignment = {
        root: (f"component:{min(keys)}", deterministic_split(min(keys)))
        for root, keys in components.items()
    }
    return {
        sample_id: component_assignment[find(keys[0])]
        for sample_id, keys in record_keys.items()
    }


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()[:36]


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite derived artifact: {destination}")
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def ensure_empty_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if any(path.rglob("*")):
        raise FileExistsError(f"Derived output is not empty; refusing to overwrite: {path}")


def bbox_to_yolo(box: list[float], width: int, height: int) -> list[float] | None:
    if width <= 0 or height <= 0 or len(box) != 4:
        return None
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return [
        ((x1 + x2) / 2) / width,
        ((y1 + y2) / 2) / height,
        (x2 - x1) / width,
        (y2 - y1) / height,
    ]


def write_detection_label(path: Path, record: dict[str, Any]) -> int:
    rows = []
    for box in record["plate_bbox"]:
        values = bbox_to_yolo(box, record["width"], record["height"])
        if values:
            rows.append("0 " + " ".join(f"{value:.8f}" for value in values))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return len(rows)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def detection_candidates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    # The canonical copy wins. Indian plates and real_public are source-equivalent
    # copies and are intentionally excluded from the V2 candidate pool.
    priority = {
        "plate_detection": 0,
        "images_and_labels": 1,
        "google_images": 2,
        "State-wise_OLX": 3,
        "video_images": 4,
    }
    candidates = [
        record for record in records
        if record["source_dataset"] in priority and record["source_path"] and record["usable_detection"]
    ]
    candidates.sort(key=lambda item: (priority[item["source_dataset"]], item["source_path"]))
    assignments = grouped_assignments(candidates)
    selected: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    excluded_exact = 0
    for record in candidates:
        if record["sha256"] in seen_hashes:
            excluded_exact += 1
            continue
        seen_hashes.add(record["sha256"])
        item = dict(record)
        if record["source_dataset"] == "plate_detection":
            item["v2_split"] = record["split"]
            item["group_key"] = f"canonical:{record['sample_id']}"
        else:
            item["group_key"], item["v2_split"] = assignments[record["sample_id"]]
        selected.append(item)
    return selected, {"candidate_records": len(candidates), "exact_duplicates_excluded": excluded_exact}


def build_detection_v2(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ensure_empty_output(DETECTION_V2)
    selected, counters = detection_candidates(records)
    manifest_rows: list[dict[str, Any]] = []
    link_modes = Counter()
    source_counts = Counter()
    split_counts = Counter()
    label_counts = Counter()
    for index, record in enumerate(selected, 1):
        split = record["v2_split"]
        stem = f"{slug(record['source_dataset'])}_{record['sha256'][:16]}"
        suffix = source_path(record).suffix.lower() or ".jpg"
        image_out = DETECTION_V2 / "images" / split / f"{stem}{suffix}"
        label_out = DETECTION_V2 / "labels" / split / f"{stem}.txt"
        link_modes[link_or_copy(source_path(record), image_out)] += 1
        object_count = write_detection_label(label_out, record)
        source_counts[record["source_dataset"]] += 1
        split_counts[split] += 1
        label_counts[split] += object_count
        manifest_rows.append({
            "sample_id": record["sample_id"],
            "source_dataset": record["source_dataset"],
            "source_path": record["source_path"],
            "annotation_path": record["annotation_path"],
            "output_image": image_out.relative_to(DETECTION_V2).as_posix(),
            "output_label": label_out.relative_to(DETECTION_V2).as_posix(),
            "split": split,
            "group_key": record["group_key"],
            "sha256": record["sha256"],
            "perceptual_hash": record["perceptual_hash"],
            "width": record["width"],
            "height": record["height"],
            "plate_text_raw": record["plate_text_raw"],
            "plate_text_normalized": record["plate_text_normalized"],
            "plate_identity": record["plate_identity"],
            "sequence_id": record["sequence_id"],
            "license_status": record["license_status"],
            "provenance": record["provenance"],
            "original_polygon": json.dumps(record["polygon"], separators=(",", ":")),
        })
    fields = list(manifest_rows[0].keys()) if manifest_rows else []
    write_csv(DETECTION_V2 / "manifest.csv", manifest_rows, fields)
    write_csv(DETECTION_V2 / "split_manifest.csv", manifest_rows, fields)
    (DETECTION_V2 / "dataset.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n",
        encoding="utf-8",
    )
    stats = {
        "status": "DERIVATIVE_READY_NOT_TRAINED",
        "source_inventory": "datasets/experiments/manifests/source_inventory.csv",
        "candidate_records": counters["candidate_records"],
        "selected_unique_images": len(manifest_rows),
        "exact_duplicates_excluded": counters["exact_duplicates_excluded"],
        "split_counts": dict(split_counts),
        "label_object_counts": dict(label_counts),
        "source_contribution": dict(source_counts),
        "link_modes": dict(link_modes),
        "excluded_original_sources": ["Indian plates", "plate_detection_source_real_public"],
        "notes": [
            "Canonical plate_detection split assignments were preserved.",
            "Raw sources were grouped by sequence, plate identity, or image hash before deterministic splitting.",
            "VOC labels were converted to class 0 license_plate bounding boxes.",
            "The original polygon data remains in the source inventory and was not rewritten.",
        ],
    }
    (DETECTION_V2 / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (DETECTION_V2 / "README.md").write_text(
        "# Plate Detection V2\n\n"
        "Isolated derivative built from the audited source inventory. Frozen V1 data was not modified.\n\n"
        "This dataset uses one class (`license_plate`) and converts VOC/polygon source annotations to validated axis-aligned YOLO boxes.\n"
        "See `manifest.csv` and `dataset_stats.json` for provenance and exclusions.\n",
        encoding="utf-8",
    )
    return selected, stats


def obb_points(record: dict[str, Any]) -> list[list[float]]:
    points = record["polygon"][0] if record["polygon"] else []
    if len(points) >= 3:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            contour = np.asarray(points, dtype=np.float32)
            rectangle = cv2.boxPoints(cv2.minAreaRect(contour)).tolist()
            return rectangle
        except Exception:
            pass
    box = record["plate_bbox"][0] if record["plate_bbox"] else [0, 0, 0, 0]
    x1, y1, x2, y2 = box
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def build_obb(selected: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_empty_output(OBB_V1)
    rows = []
    split_counts = Counter()
    for record in selected:
        split = record["v2_split"]
        stem = f"{slug(record['source_dataset'])}_{record['sha256'][:16]}"
        source_image = DETECTION_V2 / "images" / split / f"{stem}{source_path(record).suffix.lower() or '.jpg'}"
        output_image = OBB_V1 / "images" / split / source_image.name
        output_label = OBB_V1 / "labels" / split / f"{stem}.txt"
        link_or_copy(source_image, output_image)
        corners = obb_points(record)
        values = []
        for x, y in corners:
            values.extend([max(0.0, min(1.0, x / max(record["width"], 1))), max(0.0, min(1.0, y / max(record["height"], 1)))])
        output_label.parent.mkdir(parents=True, exist_ok=True)
        output_label.write_text("0 " + " ".join(f"{value:.8f}" for value in values) + "\n", encoding="utf-8")
        split_counts[split] += 1
        rows.append({"sample_id": record["sample_id"], "source_dataset": record["source_dataset"], "split": split, "image": output_image.relative_to(OBB_V1).as_posix(), "label": output_label.relative_to(OBB_V1).as_posix(), "sha256": record["sha256"], "geometry": "polygon_min_area_rect" if record["polygon"] else "axis_aligned_bbox"})
    write_csv(OBB_V1 / "manifest.csv", rows, list(rows[0].keys()) if rows else [])
    (OBB_V1 / "dataset.yaml").write_text("path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n", encoding="utf-8")
    stats = {"status": "DERIVATIVE_READY_NOT_TRAINED", "selected_unique_images": len(rows), "split_counts": dict(split_counts), "candidate_models": ["YOLO11l-obb", "YOLO26l-obb"], "notes": ["OBB labels are derived from polygon minimum-area rectangles where polygons exist; otherwise axis-aligned rectangles are used.", "No OBB model was promoted or trained by this step."]}
    (OBB_V1 / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def crop_image(image_path: Path, box: list[float]) -> Any:
    import cv2  # type: ignore

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None or len(box) != 4:
        return None
    height, width = image.shape[:2]
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return image[y1:y2, x1:x2]


def add_ocr_row(rows: list[dict[str, Any]], output_root: Path, split: str, record: dict[str, Any], output_image: Path, label: str, source_kind: str) -> None:
    output_label = output_root / "labels" / split / f"{output_image.stem}.txt"
    output_label.parent.mkdir(parents=True, exist_ok=True)
    output_label.write_text(label + "\n", encoding="utf-8")
    rows.append({
        "sample_id": record["sample_id"],
        "source_dataset": record["source_dataset"],
        "source_path": record["source_path"],
        "annotation_path": record["annotation_path"],
        "output_image": output_image.relative_to(output_root).as_posix(),
        "output_label": output_label.relative_to(output_root).as_posix(),
        "split": split,
        "source_kind": source_kind,
        "plate_text_raw": label,
        "plate_text_normalized": record["plate_text_normalized"],
        "plate_identity": record["plate_identity"],
        "group_key": record.get("group_key", ""),
        "sha256": record["sha256"],
        "license_status": record["license_status"],
        "provenance": record["provenance"],
    })


def build_ocr_v2(records: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_empty_output(OCR_V2)
    legacy = [record for record in records if record["source_dataset"] == "plate_ocr" and record["usable_ocr"]]
    legacy_identities = {record["plate_identity"] for record in legacy if record["plate_identity"]}
    rows: list[dict[str, Any]] = []
    split_counts = Counter()
    link_modes = Counter()
    for record in sorted(legacy, key=lambda item: (item["split"], item["source_path"])):
        split = {"train": "train", "val": "expanded_val", "test": "expanded_test"}[record["split"]]
        output_image = OCR_V2 / "images" / split / f"legacy_{record['sample_id']}.jpg"
        link_modes[link_or_copy(source_path(record), output_image)] += 1
        add_ocr_row(rows, OCR_V2, split, record, output_image, record["plate_text_raw"], "legacy_frozen")
        split_counts[split] += 1

    raw_sources = {"google_images", "State-wise_OLX", "video_images"}
    raw = [record for record in records if record["source_dataset"] in raw_sources and record["usable_detection"] and record["usable_ocr"] and record["plate_identity"] not in legacy_identities]
    raw.sort(key=lambda item: (item["source_dataset"], item["source_path"]))
    seen_hashes: set[str] = set()
    assignments = grouped_assignments(raw)
    seen_groups: set[str] = set()
    new_counts = Counter()
    for record in raw:
        if record["sha256"] in seen_hashes:
            continue
        group_key, assigned_split = assignments[record["sample_id"]]
        if group_key in seen_groups:
            continue
        seen_hashes.add(record["sha256"])
        seen_groups.add(group_key)
        record = dict(record)
        record["group_key"] = group_key
        split = {"train": "train", "val": "expanded_val", "test": "expanded_test"}[assigned_split]
        crop = crop_image(source_path(record), record["plate_bbox"][0])
        if crop is None:
            new_counts["invalid_crop"] += 1
            continue
        try:
            import cv2  # type: ignore
            output_image = OCR_V2 / "images" / split / f"derived_{record['sample_id']}.jpg"
            output_image.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(output_image), crop):
                new_counts["write_failure"] += 1
                continue
        except Exception:
            new_counts["opencv_failure"] += 1
            continue
        add_ocr_row(rows, OCR_V2, split, record, output_image, record["plate_text_raw"], "derived_validated_voc")
        split_counts[split] += 1
        new_counts["added"] += 1

    fields = list(rows[0].keys()) if rows else []
    write_csv(OCR_V2 / "manifest.csv", rows, fields)
    stats = {
        "status": "DERIVATIVE_READY_NOT_TRAINED",
        "legacy_train": sum(row["source_kind"] == "legacy_frozen" and row["split"] == "train" for row in rows),
        "legacy_val": sum(row["source_kind"] == "legacy_frozen" and row["split"] == "expanded_val" for row in rows),
        "legacy_test": sum(row["source_kind"] == "legacy_frozen" and row["split"] == "expanded_test" for row in rows),
        "new_raw_candidates": len(raw),
        "new_identity_groups_considered": len(seen_groups),
        "new_counts": dict(new_counts),
        "split_counts": dict(split_counts),
        "link_modes": dict(link_modes),
        "legacy_validation_and_test_preserved": True,
        "legacy_identity_exclusion_count": len(legacy_identities),
        "notes": [
            "Legacy OCR validation and locked test crops were copied by hard link and remain unchanged.",
            "New OCR crops were generated only from validated VOC boxes and validated plate text.",
            "Raw candidates sharing a legacy plate identity were excluded from the derived corpus.",
            "Expanded splits are for development; the legacy test remains the final historical comparison set.",
        ],
    }
    (OCR_V2 / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (OCR_V2 / "README.md").write_text(
        "# Plate OCR V2\n\n"
        "Isolated OCR derivative built from the audited inventory. Frozen V1 data was not modified.\n\n"
        "`images/train` starts with the 1,382 legacy training crops. `expanded_val` and `expanded_test` retain the legacy 147/178 crops and may contain additional identity-disjoint derived samples.\n",
        encoding="utf-8",
    )
    return stats


def main() -> int:
    records = load_inventory()
    selected, detection_stats = build_detection_v2(records)
    obb_stats = build_obb(selected)
    ocr_stats = build_ocr_v2(records)
    summary = {"detection_v2": detection_stats, "obb_v1": obb_stats, "ocr_v2": ocr_stats}
    report_dir = ROOT / "reports" / "p11_5" / "dataset"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "v2_build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[P11.5] Detection V2:", detection_stats["selected_unique_images"], detection_stats["split_counts"])
    print("[P11.5] OBB V1:", obb_stats["selected_unique_images"], obb_stats["split_counts"])
    print("[P11.5] OCR V2:", ocr_stats["split_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
