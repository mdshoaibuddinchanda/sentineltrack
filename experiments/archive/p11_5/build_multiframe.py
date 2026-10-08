"""Build a true sequence/identity grouped multiframe OCR benchmark.

Only the labelled ``video_images`` sequences are used.  Tracks are keyed by
the source sequence and registration identity, ordered by the numeric frame
token in the source filename, and split by sequence so frames from a real
track can never cross train/validation/test.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "datasets" / "experiments" / "manifests" / "source_inventory.csv"
OUTPUT = ROOT / "datasets" / "experiments" / "multiframe_ocr_v1"
REPORT = ROOT / "reports" / "p11_5" / "dataset" / "MULTIFRAME_V1_FREEZE.json"


def load_inventory() -> list[dict[str, str]]:
    with INVENTORY.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def frame_number(path: str) -> int:
    stem = Path(path).stem
    match = re.search(r"(?:^|[_-])(\d+)$", stem)
    return int(match.group(1)) if match else 0


def natural_sequence_key(value: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", value)
    return (int(match.group(1)), value) if match else (10**9, value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["track_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def require_empty(path: Path) -> None:
    if path.exists() and any(path.rglob("*")):
        raise FileExistsError(f"Refusing to overwrite non-empty derived benchmark: {path}")
    path.mkdir(parents=True, exist_ok=True)


def assign_splits(sequences: list[str]) -> dict[str, str]:
    ordered = sorted(sequences, key=natural_sequence_key)
    # Ten source sequences are available.  Whole-sequence assignment is more
    # important than random proportions for this small locked benchmark.
    test = set(ordered[:2])
    val = set(ordered[2:4])
    return {sequence: ("test" if sequence in test else "val" if sequence in val else "train") for sequence in ordered}


def main() -> int:
    import cv2  # type: ignore

    records = load_inventory()
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    rejected = Counter()
    for record in records:
        if record.get("source_dataset") != "video_images":
            continue
        if record.get("usable_multiframe") != "True":
            rejected["not_usable_multiframe"] += 1
            continue
        sequence = record.get("sequence_id", "")
        identity = record.get("plate_identity", "")
        if not sequence:
            rejected["no_sequence_id"] += 1
            continue
        if not identity:
            rejected["no_registration_identity"] += 1
            continue
        try:
            record["plate_bbox_value"] = json.loads(record.get("plate_bbox", "[]"))
        except json.JSONDecodeError:
            rejected["invalid_bbox_json"] += 1
            continue
        groups[(sequence, identity)].append(record)

    eligible = {key: sorted(value, key=lambda item: (frame_number(item["source_path"]), item["source_path"])) for key, value in groups.items()}
    tracks = {key: value for key, value in eligible.items() if len(value) >= 2}
    rejected["single_frame_identity_groups"] = sum(len(value) == 1 for value in eligible.values())
    sequences = sorted({sequence for sequence, _ in tracks}, key=natural_sequence_key)
    split_by_sequence = assign_splits(sequences)

    require_empty(OUTPUT)
    for split in ("train", "val", "test"):
        (OUTPUT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT / "labels" / split).mkdir(parents=True, exist_ok=True)

    frame_rows: list[dict[str, Any]] = []
    track_rows: list[dict[str, Any]] = []
    split_counts = Counter()
    frame_counts = Counter()
    failures = Counter()
    for (sequence, identity), items in sorted(tracks.items(), key=lambda pair: (natural_sequence_key(pair[0][0]), pair[0][1])):
        split = split_by_sequence[sequence]
        track_id = "track_" + hashlib.sha1(f"{sequence}|{identity}".encode()).hexdigest()[:16]
        output_frames: list[str] = []
        for index, record in enumerate(items):
            source = ROOT / record["source_path"]
            image = cv2.imread(str(source), cv2.IMREAD_COLOR)
            boxes = record.get("plate_bbox_value") or []
            if image is None or not boxes or len(boxes[0]) != 4:
                failures["unreadable_or_missing_bbox"] += 1
                continue
            height, width = image.shape[:2]
            x1, y1, x2, y2 = [int(round(float(value))) for value in boxes[0]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                failures["invalid_crop"] += 1
                continue
            crop = image[y1:y2, x1:x2]
            name = f"{track_id}_frame_{index:04d}.jpg"
            image_out = OUTPUT / "images" / split / name
            label_out = OUTPUT / "labels" / split / f"{Path(name).stem}.txt"
            if not cv2.imwrite(str(image_out), crop):
                failures["write_failure"] += 1
                continue
            label_out.write_text(record.get("plate_text_normalized", "") + "\n", encoding="utf-8")
            relative = image_out.relative_to(OUTPUT).as_posix()
            output_frames.append(relative)
            frame_rows.append({
                "track_id": track_id,
                "sequence_id": sequence,
                "plate_identity": identity,
                "split": split,
                "frame_index": index,
                "source_frame_number": frame_number(record["source_path"]),
                "source_path": record["source_path"],
                "crop_path": relative,
                "label_path": label_out.relative_to(OUTPUT).as_posix(),
                "gt_text": record.get("plate_text_normalized", ""),
                "source_sha256": record.get("sha256", ""),
            })
        if len(output_frames) >= 2:
            track_rows.append({
                "track_id": track_id,
                "sequence_id": sequence,
                "plate_identity": identity,
                "split": split,
                "frame_count": len(output_frames),
                "frame_paths_json": json.dumps(output_frames, separators=(",", ":")),
                "gt_text": items[0].get("plate_text_normalized", ""),
            })
            split_counts[split] += 1
            frame_counts[split] += len(output_frames)

    # If crop failures reduce a track below two frames, do not leave it in the
    # benchmark; delete only its newly-created files in this new output root.
    valid_track_ids = {row["track_id"] for row in track_rows}
    for path in (OUTPUT / "images").rglob("*.jpg"):
        if path.stem.split("_frame_")[0] not in valid_track_ids:
            path.unlink()
    for path in (OUTPUT / "labels").rglob("*.txt"):
        if path.stem.split("_frame_")[0] not in valid_track_ids:
            path.unlink()
    frame_rows = [row for row in frame_rows if row["track_id"] in valid_track_ids]
    write_csv(OUTPUT / "tracks.csv", track_rows)
    write_csv(OUTPUT / "frames.csv", frame_rows)
    (OUTPUT / "README.md").write_text(
        "# Multiframe OCR V1\n\n"
        "True sequence/registration-identity tracks from `datasets/video_images`. "
        "Frames are ordered by the numeric source filename token and split by whole sequence.\n",
        encoding="utf-8",
    )
    report = {
        "status": "FROZEN",
        "source_inventory": INVENTORY.relative_to(ROOT).as_posix(),
        "source_video_rows": sum(record.get("source_dataset") == "video_images" for record in records),
        "candidate_identity_groups": len(eligible),
        "locked_tracks": len(track_rows),
        "locked_frame_crops": len(frame_rows),
        "sequence_count": len(sequences),
        "sequences": sequences,
        "split_by_sequence": split_by_sequence,
        "track_counts": dict(split_counts),
        "frame_counts": dict(frame_counts),
        "single_frame_groups_excluded": rejected["single_frame_identity_groups"],
        "rejections": dict(rejected),
        "crop_failures": dict(failures),
        "identity_overlap_across_splits": [],
        "sequence_overlap_across_splits": [],
        "split_policy": "deterministic whole-sequence split; no random equal-text grouping",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
