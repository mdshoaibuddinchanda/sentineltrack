"""Read-only audit and manifest builder for SentinelTrack P11.5.

The script reads the existing datasets and writes only derived manifests and
reports. It never rewrites, moves, deletes, or relabels source data.

Run with the project environment:
    python experiments/archive/p11_5/audit_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DATASETS = ROOT / "datasets"
MANIFEST_DIR = DATASETS / "experiments" / "manifests"
REPORT_DIR = ROOT / "reports" / "p11_5" / "dataset"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PLATE_PATTERN = re.compile(
    r"^(?:[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}|BH[0-9]{2}[A-Z]{1,2}[0-9]{4})$"
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read dimensions without requiring a heavyweight image library."""
    try:
        data = path.read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if data[:2] == b"\xff\xd8":
            index = 2
            sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8))
            sof_markers |= set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
            while index + 9 < len(data):
                if data[index] != 0xFF:
                    index += 1
                    continue
                while index < len(data) and data[index] == 0xFF:
                    index += 1
                if index >= len(data):
                    break
                marker = data[index]
                index += 1
                if marker in (0xD8, 0xD9):
                    continue
                if index + 2 > len(data):
                    break
                segment_length = struct.unpack(">H", data[index : index + 2])[0]
                if marker in sof_markers and index + 7 <= len(data):
                    height, width = struct.unpack(">HH", data[index + 3 : index + 7])
                    return width, height
                index += segment_length
    except (OSError, ValueError, struct.error):
        pass
    # A few archive entries have a .jpg suffix but contain valid WEBP bytes.
    # OpenCV can still decode them; retain that fact as a quality flag below.
    try:
        import cv2  # type: ignore

        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is not None and len(image.shape) >= 2:
            return int(image.shape[1]), int(image.shape[0])
    except Exception:
        pass
    return None


def perceptual_hash(path: Path) -> str:
    """Return a small average hash; ``unavailable`` if OpenCV is absent/broken."""
    try:
        import cv2  # type: ignore

        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return "unavailable"
        small = cv2.resize(image, (16, 8), interpolation=cv2.INTER_AREA)
        threshold = float(small.mean())
        bits = 0
        for value in small.reshape(-1):
            bits = (bits << 1) | int(float(value) >= threshold)
        return f"{bits:016x}"
    except Exception:
        return "unavailable"


def normalize_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def valid_plate(text: str) -> bool:
    return bool(PLATE_PATTERN.fullmatch(normalize_plate(text)))


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_yolo(path: Path, width: int, height: int) -> dict[str, Any]:
    boxes: list[list[float]] = []
    polygons: list[list[list[float]]] = []
    flags: list[str] = []
    line_count = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"boxes": [], "polygons": [], "flags": ["annotation_unreadable"], "line_count": 0}

    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        line_count += 1
        try:
            values = [float(token) for token in line.split()]
        except ValueError:
            flags.append(f"non_numeric_line_{line_number}")
            continue
        if len(values) < 5 or values[0] != 0:
            flags.append(f"invalid_yolo_line_{line_number}")
            continue
        if any(value < 0 or value > 1 for value in values[1:]):
            flags.append(f"normalized_coordinate_out_of_range_{line_number}")
            continue
        if len(values) == 5:
            _, xc, yc, box_width, box_height = values
            boxes.append([
                (xc - box_width / 2) * width,
                (yc - box_height / 2) * height,
                (xc + box_width / 2) * width,
                (yc + box_height / 2) * height,
            ])
        elif len(values) >= 7 and len(values[1:]) % 2 == 0:
            points = [
                [values[index] * width, values[index + 1] * height]
                for index in range(1, len(values), 2)
            ]
            polygons.append(points)
            boxes.append([
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points),
                max(point[1] for point in points),
            ])
        else:
            flags.append(f"invalid_polygon_line_{line_number}")

    if not boxes:
        flags.append("empty_annotation")
    return {"boxes": boxes, "polygons": polygons, "flags": sorted(set(flags)), "line_count": line_count}


def parse_voc(path: Path) -> dict[str, Any]:
    boxes: list[list[float]] = []
    polygons: list[list[list[float]]] = []
    names: list[str] = []
    flags: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {"boxes": [], "polygons": [], "names": [], "flags": ["xml_unreadable"]}

    objects = root.findall(".//object")
    for object_node in objects:
        name = (object_node.findtext("name") or "").strip()
        names.append(name)
        box = object_node.find("bndbox")
        if box is None:
            flags.append("object_missing_bndbox")
            continue
        try:
            boxes.append([
                float(box.findtext("xmin", "nan")),
                float(box.findtext("ymin", "nan")),
                float(box.findtext("xmax", "nan")),
                float(box.findtext("ymax", "nan")),
            ])
        except ValueError:
            flags.append("non_numeric_bbox")
    if not objects:
        flags.append("empty_annotation")
    return {"boxes": boxes, "polygons": polygons, "names": names, "flags": sorted(set(flags))}


def boxes_valid(boxes: list[list[float]], width: int, height: int) -> bool:
    if not boxes:
        return False
    # A few YOLO files contain values rounded at the image boundary. Allow a
    # tiny image-relative epsilon, but still reject genuine out-of-frame boxes.
    tolerance = max(1e-3, max(width, height) * 1e-5)
    for x1, y1, x2, y2 in boxes:
        if not (x1 < x2 and y1 < y2):
            return False
        if x1 < -tolerance or y1 < -tolerance or x2 > width + tolerance or y2 > height + tolerance:
            return False
    return True


def load_csv_map(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    result: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get(key):
                result[row[key]] = row
    return result


def base_record(source: str, image: Path, annotation: Path | None, fmt: str, split: str) -> dict[str, Any]:
    dimensions = image_dimensions(image)
    width, height = dimensions or (0, 0)
    record = {
        "sample_id": hashlib.sha256(f"{source}|{rel(image)}".encode()).hexdigest()[:20],
        "source_dataset": source,
        "source_path": rel(image),
        "annotation_path": rel(annotation) if annotation else "",
        "annotation_format": fmt,
        "split": split,
        "width": width,
        "height": height,
        "plate_bbox": [],
        "polygon": [],
        "plate_text_raw": "",
        "plate_text_normalized": "",
        "vehicle_type": "",
        "state_code": "",
        "track_id": "",
        "sequence_id": "",
        "plate_identity": "",
        "sha256": sha256(image),
        "perceptual_hash": perceptual_hash(image),
        "license_status": "UNKNOWN",
        "provenance": "",
        "usable_detection": False,
        "usable_ocr": False,
        "usable_multiframe": False,
        "quality_flags": [],
        "quarantine_reason": "",
    }
    try:
        signature = image.read_bytes()[:12]
        if image.suffix.lower() in {".jpg", ".jpeg"} and signature.startswith(b"RIFF") and b"WEBP" in signature:
            record["quality_flags"].append("image_format_extension_mismatch")
    except OSError:
        record["quality_flags"].append("image_unreadable")
    return record


def add_quality(record: dict[str, Any], flags: list[str]) -> None:
    record["quality_flags"] = sorted(set(record["quality_flags"]) | set(flags))
    if record["quality_flags"] and not record["quarantine_reason"]:
        record["quarantine_reason"] = record["quality_flags"][0]


def finish_detection_record(record: dict[str, Any], parsed: dict[str, Any]) -> None:
    record["plate_bbox"] = parsed.get("boxes", [])
    record["polygon"] = parsed.get("polygons", [])
    add_quality(record, parsed.get("flags", []))
    if record["width"] <= 0 or record["height"] <= 0:
        add_quality(record, ["invalid_image_dimensions"])
    geometry_ok = boxes_valid(record["plate_bbox"], record["width"], record["height"])
    if record["plate_bbox"] and not geometry_ok:
        add_quality(record, ["invalid_bbox_geometry"])
    record["usable_detection"] = geometry_ok and not any(
        flag.startswith("invalid_") or "out_of_range" in flag for flag in record["quality_flags"]
    )


def add_yolo_records(records: list[dict[str, Any]], source: str, image_dir: Path, label_dir: Path, split: str, license_status: str, provenance: str) -> None:
    for image in sorted(p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS):
        annotation = label_dir / f"{image.stem}.txt"
        record = base_record(source, image, annotation if annotation.exists() else None, "YOLO", split)
        record["license_status"] = license_status
        record["provenance"] = provenance
        if not annotation.exists():
            add_quality(record, ["missing_annotation"])
        else:
            finish_detection_record(record, parse_yolo(annotation, record["width"], record["height"]))
        records.append(record)


def add_voc_records(records: list[dict[str, Any]], source: str, directory: Path, license_status: str, provenance: str, sequence_prefix: str = "") -> None:
    images = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    xml_by_stem: dict[str, list[Path]] = defaultdict(list)
    for xml in directory.rglob("*.xml"):
        xml_by_stem[xml.stem.lower()].append(xml)

    for image in images:
        annotations = xml_by_stem.get(image.stem.lower(), [])
        annotation = annotations[0] if annotations else None
        record = base_record(source, image, annotation, "Pascal VOC XML", "unsplit")
        record["license_status"] = license_status
        record["provenance"] = provenance
        record["usable_multiframe"] = source == "video_images"
        if sequence_prefix:
            match = re.match(sequence_prefix, image.stem, flags=re.IGNORECASE)
            if match:
                record["sequence_id"] = match.group(0).lower()
        if not annotation:
            add_quality(record, ["missing_annotation"])
            records.append(record)
            continue
        parsed = parse_voc(annotation)
        finish_detection_record(record, parsed)
        names = parsed.get("names", [])
        if names:
            raw = names[0]
            record["plate_text_raw"] = raw
            record["plate_text_normalized"] = normalize_plate(raw)
            record["usable_ocr"] = valid_plate(raw)
            if record["usable_ocr"]:
                record["plate_identity"] = record["plate_text_normalized"]
                record["state_code"] = record["plate_text_normalized"][:2]
            else:
                add_quality(record, ["plate_text_invalid"])
        else:
            add_quality(record, ["missing_plate_text"])
        if len(names) > 1:
            add_quality(record, ["multiple_objects"])
        records.append(record)

    image_stems = {p.stem.lower() for p in images}
    for xml in sorted(directory.rglob("*.xml")):
        if xml.stem.lower() not in image_stems:
            # Keep an explicit orphan record so the audit cannot hide it.
            records.append({
                "sample_id": hashlib.sha256(f"{source}|orphan|{rel(xml)}".encode()).hexdigest()[:20],
                "source_dataset": source,
                "source_path": "",
                "annotation_path": rel(xml),
                "annotation_format": "Pascal VOC XML",
                "split": "unsplit",
                "width": 0,
                "height": 0,
                "plate_bbox": [],
                "polygon": [],
                "plate_text_raw": "",
                "plate_text_normalized": "",
                "vehicle_type": "",
                "state_code": "",
                "track_id": "",
                "sequence_id": "",
                "plate_identity": "",
                "sha256": "",
                "perceptual_hash": "",
                "license_status": license_status,
                "provenance": provenance,
                "usable_detection": False,
                "usable_ocr": False,
                "usable_multiframe": False,
                "quality_flags": ["orphan_annotation"],
                "quarantine_reason": "orphan_annotation",
            })


def add_ocr_records(records: list[dict[str, Any]]) -> None:
    source_map = load_csv_map(DATASETS / "plate_ocr" / "sources.csv", "filename")
    image_root = DATASETS / "plate_ocr" / "images"
    for image in sorted(p for p in image_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS):
        split = image.parent.name
        label = DATASETS / "plate_ocr" / "labels" / split / f"{image.stem}.txt"
        record = base_record("plate_ocr", image, label if label.exists() else None, "OCR text", split)
        record["license_status"] = "LICENSE_UNVERIFIED"
        record["provenance"] = "zenitsu09/indian-number-plate on Hugging Face"
        record["usable_multiframe"] = False
        if label.exists():
            text = label.read_text(encoding="utf-8", errors="replace").strip()
            record["plate_text_raw"] = text
            record["plate_text_normalized"] = normalize_plate(text)
            record["usable_ocr"] = bool(record["plate_text_normalized"])
        else:
            add_quality(record, ["missing_annotation"])
        metadata = source_map.get(image.name, {})
        record["plate_identity"] = metadata.get("parent_identity", "")
        record["state_code"] = record["plate_text_normalized"][:2]
        if not record["usable_ocr"]:
            add_quality(record, ["empty_ocr_text"])
        records.append(record)


def hamming(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 999


def build_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    provenance_detection = "Roboflow Quobotic Indian Number Plate v3; CC BY 4.0"
    for split_name, source_split in [("train", "train"), ("val", "valid"), ("test", "test")]:
        add_yolo_records(records, "Indian plates", DATASETS / "Indian plates" / source_split / "images", DATASETS / "Indian plates" / source_split / "labels", split_name, "CC-BY-4.0", provenance_detection)
    for split_name in ("train", "val", "test"):
        add_yolo_records(records, "plate_detection", DATASETS / "plate_detection" / "images" / split_name, DATASETS / "plate_detection" / "labels" / split_name, split_name, "CC-BY-4.0", provenance_detection)
        add_yolo_records(records, "plate_detection_source_real_public", DATASETS / "plate_detection" / "sources" / "real_public" / split_name, DATASETS / "plate_detection" / "sources" / "real_public" / split_name, split_name, "CC-BY-4.0", provenance_detection)
    add_yolo_records(records, "images_and_labels", DATASETS / "images", DATASETS / "labels", "unsplit", "UNKNOWN", "Local archive.zip; provenance not encoded")
    add_voc_records(records, "google_images", DATASETS / "google_images", "UNKNOWN", "Local archive (1).zip; Pascal VOC source collection")
    add_voc_records(records, "State-wise_OLX", DATASETS / "State-wise_OLX", "UNKNOWN", "Local archive (1).zip; state-wise source collection")
    add_voc_records(records, "video_images", DATASETS / "video_images", "UNKNOWN", "Local archive (1).zip; video-frame source collection", r"video[0-9]+")
    add_ocr_records(records)
    return records


def write_inventory(records: list[dict[str, Any]]) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "sample_id", "source_dataset", "source_path", "annotation_path", "annotation_format", "split",
        "width", "height", "plate_bbox", "polygon", "plate_text_raw", "plate_text_normalized",
        "vehicle_type", "state_code", "track_id", "sequence_id", "plate_identity", "sha256",
        "perceptual_hash", "license_status", "provenance", "usable_detection", "usable_ocr",
        "usable_multiframe", "quality_flags", "quarantine_reason",
    ]
    output = MANIFEST_DIR / "source_inventory.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["plate_bbox"] = safe_json(row["plate_bbox"])
            row["polygon"] = safe_json(row["polygon"])
            row["quality_flags"] = safe_json(row["quality_flags"])
            writer.writerow(row)


def duplicate_reports(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_phash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["sha256"]:
            by_sha[record["sha256"]].append(record)
        if record["perceptual_hash"] != "unavailable":
            by_phash[record["perceptual_hash"]].append(record)

    exact_groups = [items for items in by_sha.values() if len(items) > 1]
    near_groups: list[list[dict[str, Any]]] = []
    for bucket in by_phash.values():
        if len(bucket) < 2:
            continue
        groups: list[list[dict[str, Any]]] = []
        for record in bucket:
            placed = False
            for group in groups:
                if hamming(record["perceptual_hash"], group[0]["perceptual_hash"]) <= 8:
                    group.append(record)
                    placed = True
                    break
            if not placed:
                groups.append([record])
        near_groups.extend(group for group in groups if len(group) > 1)

    output = MANIFEST_DIR / "duplicate_groups.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["group_type", "group_id", "sha256", "perceptual_hash", "source_dataset", "source_path", "split"])
        writer.writeheader()
        group_id = 0
        for kind, groups in (("exact_sha256", exact_groups), ("near_perceptual_hash", near_groups)):
            for group in groups:
                group_id += 1
                for record in group:
                    writer.writerow({"group_type": kind, "group_id": group_id, "sha256": record["sha256"], "perceptual_hash": record["perceptual_hash"], "source_dataset": record["source_dataset"], "source_path": record["source_path"], "split": record["split"]})

    cross_split_exact = []
    for group in exact_groups:
        splits = sorted({item["split"] for item in group if item["split"] in {"train", "val", "test"}})
        if len(splits) > 1:
            cross_split_exact.append({"splits": splits, "sources": sorted({item["source_dataset"] for item in group})})
    return {
        "exact_duplicate_groups": len(exact_groups),
        "exact_duplicate_records": sum(len(group) for group in exact_groups),
        "near_duplicate_candidate_groups": len(near_groups),
        "cross_split_exact_duplicate_groups": cross_split_exact,
    }


def leakage_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    identity_sets: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record["plate_identity"] and record["split"] in {"train", "val", "test"}:
            identity_sets[record["split"]].add(record["plate_identity"])
    overlaps = {
        "train_val": sorted(identity_sets["train"] & identity_sets["val"]),
        "train_test": sorted(identity_sets["train"] & identity_sets["test"]),
        "val_test": sorted(identity_sets["val"] & identity_sets["test"]),
    }
    # Do not print or expose the actual identities in summary reports.
    return {
        "identity_counts": {key: len(value) for key, value in identity_sets.items()},
        "identity_overlap_counts": {key: len(value) for key, value in overlaps.items()},
        "identity_leakage_pass": not any(overlaps.values()),
        "sequence_counts": dict(Counter(record["sequence_id"] for record in records if record["sequence_id"])),
    }


def stats_report(records: list[dict[str, Any]], duplicate_info: dict[str, Any], leakage: dict[str, Any]) -> dict[str, Any]:
    by_source: dict[str, dict[str, Any]] = {}
    for source in sorted({record["source_dataset"] for record in records}):
        items = [record for record in records if record["source_dataset"] == source]
        by_source[source] = {
            "records": len(items),
            "images": sum(bool(item["source_path"]) for item in items),
            "orphan_annotations": sum("orphan_annotation" in item["quality_flags"] for item in items),
            "usable_detection": sum(item["usable_detection"] for item in items),
            "usable_ocr": sum(item["usable_ocr"] for item in items),
            "usable_multiframe": sum(item["usable_multiframe"] for item in items),
            "splits": dict(Counter(item["split"] for item in items)),
            "annotation_formats": dict(Counter(item["annotation_format"] for item in items)),
            "quality_flags": dict(Counter(flag for item in items for flag in item["quality_flags"])),
        }
    return {
        "record_count": len(records),
        "image_record_count": sum(bool(item["source_path"]) for item in records),
        "annotation_record_count": sum(bool(item["annotation_path"]) for item in records),
        "unlabeled_image_count": sum("missing_annotation" in item["quality_flags"] for item in records),
        "invalid_or_quarantined_count": sum(bool(item["quarantine_reason"]) for item in records),
        "by_source": by_source,
        "duplicates": duplicate_info,
        "leakage": leakage,
        "frozen_dataset_observations": {
            "plate_detection_images": 2531,
            "plate_ocr_images": 1707,
            "plate_ocr_legacy_identity_leakage": False,
            "indian_plates_is_source_equivalent_to_plate_detection": True,
        },
    }


def main() -> int:
    if not DATASETS.exists():
        print(f"Dataset root not found: {DATASETS}", file=sys.stderr)
        return 2
    print("[P11.5] Building read-only dataset inventory...")
    records = build_records()
    write_inventory(records)
    duplicates = duplicate_reports(records)
    leakage = leakage_report(records)
    stats = stats_report(records, duplicates, leakage)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (MANIFEST_DIR / "dataset_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (MANIFEST_DIR / "leakage_report.json").write_text(json.dumps(leakage, indent=2), encoding="utf-8")
    (REPORT_DIR / "audit_summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[P11.5] Image records: {stats['image_record_count']}")
    print(f"[P11.5] Exact duplicate groups: {duplicates['exact_duplicate_groups']}")
    print(f"[P11.5] Near-duplicate candidate groups: {duplicates['near_duplicate_candidate_groups']}")
    print(f"[P11.5] Unlabeled images: {stats['unlabeled_image_count']}")
    print(f"[P11.5] Identity leakage pass: {leakage['identity_leakage_pass']}")
    print(f"[P11.5] Inventory: {MANIFEST_DIR / 'source_inventory.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
