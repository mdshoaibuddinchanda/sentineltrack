"""Generate an isolated, deterministic synthetic Indian plate corpus.

Synthetic images are augmentation material only: they are never mixed into a
locked real test set and are never used to claim real-world accuracy.  The
generator records every sampled style, degradation, severity, font family,
state/BH format, and split in its manifest so synthetic ablations are
reproducible.
"""

from __future__ import annotations

import argparse
import json
import random
import string
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "datasets" / "experiments" / "synthetic_indian_v2"
STATE_CODES = [
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ",
    "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP",
    "MZ", "NL", "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK",
    "UA", "UP", "WB",
]
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
SEVERITIES = ("easy", "medium", "hard", "extreme")
STYLES = (
    "private_white_single_line", "commercial_yellow_single_line", "electric_green_single_line",
    "motorcycle_white_two_line", "commercial_yellow_two_line", "bh_white_single_line",
)


def _available_fonts() -> list[tuple[str, Path]]:
    candidates = [
        ("Arial", Path("C:/Windows/Fonts/arial.ttf")),
        ("Arial-Bold", Path("C:/Windows/Fonts/arialbd.ttf")),
        ("Consolas", Path("C:/Windows/Fonts/consola.ttf")),
        ("Calibri-Bold", Path("C:/Windows/Fonts/calibrib.ttf")),
    ]
    return [(name, path) for name, path in candidates if path.is_file()]


def _plate_text(index: int, rng: random.Random) -> tuple[str, str]:
    if index % 11 == 0:
        year = 20 + (index % 25)
        suffix = "".join(rng.choice(string.ascii_uppercase) for _ in range(2))
        return f"{year:02d}BH{1 + (index * 37) % 9999:04d}{suffix}", "BH"
    state = STATE_CODES[index % len(STATE_CODES)]
    district = f"{1 + (index * 7) % 99:02d}"
    letters = "".join(rng.choice(LETTERS) for _ in range(2))
    serial = f"{1 + (index * 137) % 9999:04d}"
    return f"{state}{district}{letters}{serial}", state


def _font_image(text: str, width: int, height: int, font_path: Path | None, size: int, two_line: bool) -> Any:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    image = np.zeros((height, width, 3), dtype=np.uint8)
    # OpenCV's built-in families avoid redistributing fonts and are stable in
    # headless Windows runs.  The selected installed-font basename is retained
    # in metadata as a style proxy; no font file is copied into the corpus.
    font_map = {
        "arialbd": cv2.FONT_HERSHEY_TRIPLEX,
        "consola": cv2.FONT_HERSHEY_COMPLEX,
        "calibri": cv2.FONT_HERSHEY_DUPLEX,
    }
    font = cv2.FONT_HERSHEY_SIMPLEX
    if font_path is not None:
        name = font_path.stem.lower()
        font = next((value for key, value in font_map.items() if key in name), font)
    lines = [text[:4], text[4:]] if two_line else [text]
    for row, value in enumerate(lines):
        scale = 1.35 if two_line else 1.55
        thickness = 2 if two_line else 3
        while cv2.getTextSize(value, font, scale, thickness)[0][0] > width - 16:
            scale -= 0.05
        text_size = cv2.getTextSize(value, font, scale, thickness)[0]
        x = (width - text_size[0]) // 2
        y = int((height * (0.42 + row * 0.38)) + text_size[1] / 2) if two_line else (height + text_size[1]) // 2
        cv2.putText(image, value, (x, y), font, scale, (12, 12, 12), thickness, cv2.LINE_AA)
    return image


def _motion_blur(image: Any, length: int) -> Any:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    length = max(3, int(length) | 1)
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = 1.0 / length
    return cv2.filter2D(image, -1, kernel)


def _degrade(image: Any, severity: str, rng: random.Random, np_rng: Any) -> tuple[Any, list[str]]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    scale = {"easy": 0.15, "medium": 0.35, "hard": 0.65, "extreme": 1.0}[severity]
    applied: list[str] = []
    h, w = image.shape[:2]
    if rng.random() < 0.85:
        jitter = max(1, int(10 * scale))
        source = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
        target = source + np_rng.uniform(-jitter, jitter, source.shape).astype(np.float32)
        image = cv2.warpPerspective(image, cv2.getPerspectiveTransform(source, target), (w, h), borderMode=cv2.BORDER_REPLICATE)
        applied.append("perspective")
    if rng.random() < 0.7:
        angle = rng.uniform(-2.0, 2.0) * (0.5 + scale)
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        image = cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
        applied.append("rotation")
    if rng.random() < 0.55 * (0.5 + scale):
        image = _motion_blur(image, 3 + int(8 * scale))
        applied.append("motion_blur")
    if rng.random() < 0.5 * (0.5 + scale):
        k = max(3, (1 + int(5 * scale)) | 1)
        image = cv2.GaussianBlur(image, (k, k), 0)
        applied.append("defocus")
    if rng.random() < 0.7:
        factor = 1.0 - rng.uniform(0.0, 0.72) * scale
        small = cv2.resize(image, (max(12, int(w * factor)), max(12, int(h * factor))), interpolation=cv2.INTER_AREA)
        image = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        applied.append("downsample")
    if rng.random() < 0.8:
        noise = np_rng.normal(0, 3 + 20 * scale, image.shape).astype(np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        applied.append("sensor_noise")
    if rng.random() < 0.6:
        alpha = rng.uniform(0.65, 1.25) if severity != "easy" else rng.uniform(0.85, 1.1)
        beta = rng.uniform(-35, 30) * scale
        image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
        applied.append("exposure_contrast")
    if rng.random() < 0.35 * (0.5 + scale):
        overlay = np.zeros_like(image)
        cv2.ellipse(overlay, (rng.randrange(w), rng.randrange(h)), (max(8, w // 4), max(4, h // 3)), 0, 0, 360, (255, 255, 255), -1)
        image = cv2.addWeighted(image, 1.0, overlay, 0.12 + 0.23 * scale, 0)
        applied.append("glare")
    if rng.random() < 0.35 * (0.5 + scale):
        polygon = np.array([[0, rng.randrange(h)], [w, rng.randrange(h)], [w, h], [0, h]], dtype=np.int32)
        shadow = image.copy()
        cv2.fillPoly(shadow, [polygon], (20, 20, 20))
        image = cv2.addWeighted(image, 0.72, shadow, 0.28 + 0.28 * scale, 0)
        applied.append("shadow")
    if rng.random() < 0.25 * (0.5 + scale):
        for _ in range(1 + int(5 * scale)):
            x = rng.randrange(w)
            cv2.line(image, (x, rng.randrange(h)), (min(w - 1, x + rng.randrange(-8, 12)), min(h - 1, rng.randrange(h))), (150, 175, 195), 1)
        applied.append("rain")
    if rng.random() < 0.25 * (0.5 + scale):
        fog = np.full_like(image, 205)
        image = cv2.addWeighted(image, 1.0 - 0.25 * scale, fog, 0.25 * scale, 0)
        applied.append("fog")
    if rng.random() < 0.3 * (0.5 + scale):
        for _ in range(1 + int(4 * scale)):
            center = (rng.randrange(w), rng.randrange(h))
            radius = rng.randrange(2, max(3, min(w, h) // 8))
            cv2.circle(image, center, radius, (55, 65, 62), -1)
        applied.append("dirt")
    if rng.random() < 0.35:
        for x in (max(4, w // 7), min(w - 4, w - w // 7)):
            cv2.circle(image, (x, max(4, h // 7)), max(2, h // 18), (95, 95, 95), -1)
        applied.append("screws")
    if rng.random() < 0.18 * (0.5 + scale):
        x1 = rng.randrange(max(1, w // 2))
        y1 = rng.randrange(max(1, h - 4))
        cv2.rectangle(image, (x1, y1), (min(w - 1, x1 + max(4, int(w * 0.18 * scale))), min(h - 1, y1 + max(3, int(h * 0.4 * scale)))), (45, 45, 45), -1)
        applied.append("partial_occlusion")
    if rng.random() < 0.2 * (0.5 + scale):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        image[:, :, 1] = np.clip(image[:, :, 1].astype(np.int16) * (0.45 + rng.random() * 0.5), 0, 255).astype(np.uint8)
        image = cv2.cvtColor(image, cv2.COLOR_HSV2BGR)
        applied.append("color_shift")
    if severity in {"hard", "extreme"} and rng.random() < 0.45:
        encode_quality = max(12, int(92 - 70 * scale))
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, encode_quality])
        if ok:
            image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        applied.append("jpeg_video_compression")
    if severity == "extreme" and rng.random() < 0.65:
        image = cv2.convertScaleAbs(image, alpha=0.48, beta=-32)
        applied.append("night")
    return image, applied


def _draw_plate(text: str, style: str, difficulty: str, rng: random.Random, np_rng: Any) -> tuple[Any, list[float], dict[str, Any]]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    canvas_h, canvas_w = 384, 640
    two_line = "two_line" in style
    plate_w, plate_h = ((260, 145) if two_line else (480, 108))
    x1 = rng.randint(18, canvas_w - plate_w - 18)
    y1 = rng.randint(18, canvas_h - plate_h - 18)
    if "yellow" in style:
        fill = (25, 205, 235)
    elif "green" in style:
        fill = (80, 180, 100)
    else:
        fill = (242, 242, 242)
    plate = np.full((plate_h, plate_w, 3), fill, dtype=np.uint8)
    cv2.rectangle(plate, (1, 1), (plate_w - 2, plate_h - 2), (12, 12, 12), 3)
    fonts = _available_fonts()
    font_name, font_path = fonts[rng.randrange(len(fonts))] if fonts else ("OpenCV-Hershey", None)
    font_size = 43 if two_line else 54
    rendered = _font_image(text, plate_w - 12, plate_h - 12, font_path, font_size, two_line)
    plate[6:-6, 6:-6] = rendered
    plate, applied = _degrade(plate, difficulty, rng, np_rng)
    canvas = np.full((canvas_h, canvas_w, 3), (35, 38, 42), dtype=np.uint8)
    for row in range(canvas_h):
        canvas[row] = np.clip(canvas[row].astype(np.int16) + int(18 * row / canvas_h), 0, 255)
    canvas[y1:y1 + plate_h, x1:x1 + plate_w] = plate
    box = [x1 / canvas_w, y1 / canvas_h, (x1 + plate_w) / canvas_w, (y1 + plate_h) / canvas_h]
    return canvas, box, {"font": font_name, "two_line": two_line, "degradations": applied}


def generate_dataset(output_root: Path, count: int = 32, seed: int = 115, allow_existing: bool = False) -> dict[str, Any]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    if count < 1:
        raise ValueError("count must be positive")
    existing = [item for item in output_root.rglob("*")] if output_root.exists() else []
    if existing and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite non-empty synthetic output: {output_root}")
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    font_counts: Counter[str] = Counter()
    degradation_counts: Counter[str] = Counter()
    for index in range(count):
        split = "test" if index % 10 == 0 else ("val" if index % 5 == 0 else "train")
        severity = SEVERITIES[index % len(SEVERITIES)]
        style = STYLES[index % len(STYLES)]
        text, state_or_bh = _plate_text(index, rng)
        image, box, meta = _draw_plate(text, style, severity, rng, np_rng)
        stem = f"synthetic_{index:06d}"
        image_dir = output_root / "images" / split
        detection_dir = output_root / "detection_labels" / split
        ocr_dir = output_root / "ocr_labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        detection_dir.mkdir(parents=True, exist_ok=True)
        ocr_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{stem}.jpg"
        if not cv2.imwrite(str(image_path), image, [cv2.IMWRITE_JPEG_QUALITY, 88]):
            raise RuntimeError(f"OpenCV could not write {image_path}")
        center_x, center_y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        box_w, box_h = box[2] - box[0], box[3] - box[1]
        (detection_dir / f"{stem}.txt").write_text(f"0 {center_x:.8f} {center_y:.8f} {box_w:.8f} {box_h:.8f}\n", encoding="utf-8")
        (ocr_dir / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
        rows.append({
            "id": stem, "split": split, "style": style, "severity": severity,
            "state_or_series": state_or_bh, "plate_text": text, "font": meta["font"],
            "degradations": meta["degradations"], "seed": seed,
        })
        split_counts[split] += 1
        severity_counts[severity] += 1
        style_counts[style] += 1
        state_counts[state_or_bh] += 1
        font_counts[meta["font"]] += 1
        degradation_counts.update(meta["degradations"])
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 2,
        "status": "SYNTHETIC_GENERATED_NOT_AUTHORITATIVE_TEST",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed, "count": count,
        "split_counts": dict(sorted(split_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "style_counts": dict(sorted(style_counts.items())),
        "state_or_series_counts": dict(sorted(state_counts.items())),
        "font_counts": dict(sorted(font_counts.items())),
        "degradation_counts": dict(sorted(degradation_counts.items())),
        "target_corpus_size": 100000,
        "generator": "tools/p11_5/synthetic_plates.py",
        "rows": rows,
        "ablation_plan": ["real_only", "synthetic_to_real", "real_plus_synthetic_25pct", "real_plus_synthetic_50pct"],
        "legal_note": "System fonts are used locally and not redistributed; verify model/font licensing before publishing generated artifacts.",
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "rows"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=115)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    print(json.dumps(generate_dataset(args.output, args.count, args.seed, args.allow_existing), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
