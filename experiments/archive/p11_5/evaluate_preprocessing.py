"""Measure crop margins, rectification, enhancement, upscaling, and decoder."""

from __future__ import annotations

import csv
import importlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "datasets" / "experiments" / "plate_ocr_v2"
REPORT_DIR = ROOT / "reports" / "p11_5"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_rows(split: str, source_kind: str | None = None) -> list[dict[str, str]]:
    with (DATASET / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("split") == split and (source_kind is None or row.get("source_kind") == source_kind)]


def main() -> int:
    import cv2  # type: ignore
    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    recognizer = rec_mod.get_recognizer("ppocr_mobile", device="cpu")
    variants = ("raw", "clahe", "sharpen", "rectify", "sr_x2")
    rows_out: list[dict[str, Any]] = []
    for margin in (0, 2, 4, 6, 8):
        for variant in variants:
            for split_name, split_rows in (("legacy_val", load_rows("expanded_val", "legacy_frozen")), ("locked_test", load_rows("expanded_test", "legacy_frozen"))):
                predictions: list[str] = []
                truths: list[str] = []
                latencies: list[float] = []
                for row in split_rows:
                    image = cv2.imread(str(DATASET / row["output_image"]))
                    if image is None:
                        continue
                    if margin:
                        image = cv2.copyMakeBorder(image, margin, margin, margin, margin, cv2.BORDER_REPLICATE)
                    if variant == "sr_x2":
                        image = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LANCZOS4)
                        prepared, _ = eval_mod.preprocess_crop(image, variant="raw", target_height=48)
                    else:
                        prepared, _ = eval_mod.preprocess_crop(image, variant=variant, target_height=48)
                    started = time.perf_counter()
                    text, _, _ = recognizer.recognize(prepared)
                    latencies.append((time.perf_counter() - started) * 1000)
                    predictions.append(text or "")
                    truths.append(row.get("plate_text_normalized") or "")
                metrics = eval_mod.calculate_metrics(predictions, truths)
                rows_out.append({
                    "margin_px": margin, "variant": variant, "split": split_name,
                    **metrics,
                    "p50_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
                    "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3) if latencies else None,
                })
    output = {
        "status": "COMPLETE",
        "recognizer": "PP-OCRv5 mobile",
        "variants": list(variants),
        "margins_px": [0, 2, 4, 6, 8],
        "sr_note": "sr_x2 is a classical Lanczos x2 proxy; no learned SR checkpoint was available locally, so it is not called learned super-resolution.",
        "structural_decoder": "Existing position-aware Indian grammar alternative selection; postprocessed metrics report its effect and may include false corrections.",
        "results": rows_out,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "preprocessing_evaluation.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (REPORT_DIR / "preprocessing_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["margin_px", "variant", "split", "total_samples", "raw_exact_accuracy", "postprocessed_exact_accuracy", "raw_character_accuracy", "postprocessed_character_accuracy", "raw_cer", "postprocessed_cer", "p50_latency_ms", "p95_latency_ms"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)
    print(json.dumps({"result_count": len(rows_out), "best_legacy_val": max((row for row in rows_out if row["split"] == "legacy_val"), key=lambda row: row.get("postprocessed_exact_accuracy", 0.0))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
