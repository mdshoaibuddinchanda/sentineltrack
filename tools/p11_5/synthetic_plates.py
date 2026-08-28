"""Deterministic synthetic Indian-style plate corpus generator.

This is an isolated augmentation tool.  It creates clearly labelled synthetic
examples and never modifies the frozen real datasets.  It uses OpenCV's
built-in Hershey font so it does not redistribute a third-party font.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "datasets" / "experiments" / "synthetic_indian_v1"


def _plate_text(index: int, rng: random.Random) -> str:
    states = ["GJ", "MH", "DL", "KA", "RJ", "UP", "TN", "WB", "HR", "TS"]
    state = states[index % len(states)]
    district = f"{1 + (index * 7) % 99:02d}"
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    serial = f"{1 + (index * 137) % 9999:04d}"
    return f"{state}{district}{letters}{serial}"


def _draw_plate(text: str, variant: str, difficulty: str, rng: random.Random, np_rng: Any) -> tuple[Any, list[float]]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    canvas = np.zeros((160, 480, 3), dtype=np.uint8)
    canvas[:] = (35, 35, 35)
    x1, y1, x2, y2 = 22, 40, 458, 120
    if variant == "yellow":
        fill = (25, 205, 235)
    elif variant == "green":
        fill = (75, 170, 95)
    else:
        fill = (245, 245, 245)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), fill, thickness=-1)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (15, 15, 15), thickness=3)

    if "two_line" in difficulty:
        first, second = text[:4], text[4:]
        font_scale = 1.02
        for value, baseline in ((first, 76), (second, 108)):
            size = cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)[0]
            start_x = int((x1 + x2 - size[0]) / 2)
            cv2.putText(canvas, value, (start_x, baseline), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (10, 10, 10), 2, cv2.LINE_AA)
    else:
        font_scale = 1.55
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 3)[0]
        while size[0] > x2 - x1 - 18:
            font_scale -= 0.05
            size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 3)[0]
        start_x = int((x1 + x2 - size[0]) / 2)
        baseline = int((y1 + y2 + size[1]) / 2)
        cv2.putText(canvas, text, (start_x, baseline), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (10, 10, 10), 3, cv2.LINE_AA)

    if difficulty in {"hard", "extreme", "two_line_hard"}:
        angle = rng.uniform(-5.0, 5.0)
        matrix = cv2.getRotationMatrix2D((240, 80), angle, 1.0)
        canvas = cv2.warpAffine(canvas, matrix, (480, 160), borderValue=(35, 35, 35))
        noise = np_rng.normal(0, 8 if difficulty == "hard" else 16, canvas.shape).astype(np.int16)
        canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    if difficulty in {"medium", "hard", "extreme", "two_line_hard"}:
        kernel = 3 if difficulty in {"medium", "hard", "two_line_hard"} else 5
        canvas = cv2.GaussianBlur(canvas, (kernel, kernel), 0)
    if difficulty == "extreme":
        canvas = cv2.resize(canvas, (240, 80), interpolation=cv2.INTER_AREA)
        canvas = cv2.resize(canvas, (480, 160), interpolation=cv2.INTER_LINEAR)
        canvas = cv2.convertScaleAbs(canvas, alpha=0.72, beta=-18)
    return canvas, [x1 / 480.0, y1 / 160.0, x2 / 480.0, y2 / 160.0]


def generate_dataset(output_root: Path, count: int = 32, seed: int = 115, allow_existing: bool = False) -> dict[str, Any]:
    import cv2  # type: ignore

    if count < 1:
        raise ValueError("count must be positive")
    existing = [item for item in output_root.rglob("*")] if output_root.exists() else []
    if existing and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite non-empty synthetic output: {output_root}")
    rng = random.Random(seed)
    try:
        import numpy as np  # type: ignore
        np_rng = np.random.default_rng(seed)
    except ImportError as exc:
        raise RuntimeError("numpy is required for synthetic generation") from exc

    difficulties = ["easy", "medium", "hard", "extreme", "two_line", "two_line_hard"]
    variants = ["white", "yellow", "green"]
    rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    for index in range(count):
        split = "test" if index % 10 == 0 else ("val" if index % 5 == 0 else "train")
        difficulty = difficulties[index % len(difficulties)]
        variant = variants[index % len(variants)]
        text = _plate_text(index, rng)
        image, box = _draw_plate(text, variant, difficulty, rng, np_rng)
        stem = f"synthetic_{index:06d}"
        image_dir = output_root / "images" / split
        detection_dir = output_root / "detection_labels" / split
        ocr_dir = output_root / "ocr_labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        detection_dir.mkdir(parents=True, exist_ok=True)
        ocr_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{stem}.png"
        if not cv2.imwrite(str(image_path), image):
            raise RuntimeError(f"OpenCV could not write {image_path}")
        center_x = (box[0] + box[2]) / 2.0
        center_y = (box[1] + box[3]) / 2.0
        width = box[2] - box[0]
        height = box[3] - box[1]
        (detection_dir / f"{stem}.txt").write_text(f"0 {center_x:.8f} {center_y:.8f} {width:.8f} {height:.8f}\n", encoding="utf-8")
        (ocr_dir / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
        rows.append({"id": stem, "split": split, "variant": variant, "difficulty": difficulty, "plate_text": text, "seed": seed})
        split_counts[split] += 1
        difficulty_counts[difficulty] += 1

    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "status": "SYNTHETIC_GENERATED",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "count": count,
        "split_counts": dict(sorted(split_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "generator": "tools/p11_5/synthetic_plates.py",
        "rows": rows,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "rows"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--seed", type=int, default=115)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    print(json.dumps(generate_dataset(args.output, args.count, args.seed, args.allow_existing), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
