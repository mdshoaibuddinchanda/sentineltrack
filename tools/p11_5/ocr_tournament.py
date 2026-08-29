"""Run the local zero-shot OCR screening tournament on OCR V2.

Ranking uses the legacy validation set and the expanded validation set only;
the historical locked test is measured once as a final, clearly labelled
readout.  No candidate is allowed to write into the frozen OCR dataset.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "experiments" / "plate_ocr_v2"
REPORT_DIR = ROOT / "reports" / "p11_5"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows() -> list[dict[str, str]]:
    with (DATASET / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate(recognizer: Any, rows: list[dict[str, str]], preprocess_crop: Any, calculate_metrics: Any, normalize: Any) -> dict[str, Any]:
    predictions: list[str] = []
    truths: list[str] = []
    latencies: list[float] = []
    for row in rows:
        import cv2  # type: ignore
        image = cv2.imread(str(DATASET / row["output_image"]))
        if image is None:
            continue
        image, _ = preprocess_crop(image, variant="raw", target_height=48)
        started = time.perf_counter()
        text, _, _ = recognizer.recognize(image)
        latencies.append((time.perf_counter() - started) * 1000)
        predictions.append(text or "")
        truths.append(row.get("plate_text_normalized") or row.get("plate_text_raw", ""))
    metrics = calculate_metrics(predictions, truths)
    metrics.update({
        "samples": len(truths),
        "p50_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
        "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3) if latencies else None,
        "throughput_crops_per_sec": round(len(latencies) / (sum(latencies) / 1000), 3) if latencies and sum(latencies) else 0.0,
    })
    # Keep the report compact and aggregate-only; predictions and plate strings
    # are intentionally not persisted.
    return metrics


def candidate_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "ppocr_mobile",
            "family": "PP-OCRv5",
            "variant": "mobile",
            "implementation": "04_plate_ocr.recognizers.paddle_rec",
            "weights": "models/ocr/PP-OCRv5_mobile_rec_infer.onnx",
            "license": "project-provided model; provenance recorded in existing model report",
        },
        {
            "id": "ppocr_server",
            "family": "PP-OCRv5",
            "variant": "server",
            "implementation": "04_plate_ocr.recognizers.paddle_rec",
            "weights": "models/ocr/PP-OCRv5_server_rec_infer.onnx",
            "license": "project-provided model; provenance recorded in existing model report",
        },
        {
            "id": "easyocr_rec_only",
            "family": "EasyOCR",
            "variant": "english recognition-only",
            "implementation": "04_plate_ocr.recognizers.easyocr_rec",
            "weights": "C:/Users/SHOAIB-CHANDA/.EasyOCR/english_g2.pth",
            "license": "package/model license must be verified before redistribution",
        },
        {
            "id": "svtrv2",
            "family": "SVTRv2",
            "variant": "candidate",
            "implementation": "not installed locally",
            "weights": "",
            "license": "not evaluated",
        },
        {
            "id": "parseq",
            "family": "PARSeq",
            "variant": "candidate",
            "implementation": "not installed locally",
            "weights": "",
            "license": "not evaluated",
        },
        {
            "id": "mgp_str",
            "family": "MGP-STR",
            "variant": "candidate",
            "implementation": "not installed locally",
            "weights": "",
            "license": "not evaluated",
        },
    ]


def main() -> int:
    eval_mod = importlib.import_module("04_plate_ocr.training.evaluate")
    rec_mod = importlib.import_module("04_plate_ocr.recognizers")
    rows = load_rows()
    legacy_val = [row for row in rows if row.get("split") == "expanded_val" and row.get("source_kind") == "legacy_frozen"]
    expanded_val = [row for row in rows if row.get("split") == "expanded_val"]
    locked_test = [row for row in rows if row.get("split") == "expanded_test" and row.get("source_kind") == "legacy_frozen"]
    results: list[dict[str, Any]] = []
    support: list[dict[str, Any]] = []
    for spec in candidate_specs():
        weight_path = ROOT / spec["weights"] if not spec["weights"].startswith("C:/") else Path(spec["weights"])
        base = {**spec, "weights_sha256": sha256(weight_path), "status": "UNAVAILABLE"}
        if spec["id"] not in {"ppocr_mobile", "ppocr_server", "easyocr_rec_only"}:
            base["reason"] = "No compatible local implementation and weights in PY312; not fabricated as a result."
            support.append(base)
            continue
        try:
            recognizer = rec_mod.get_recognizer(spec["id"], device="cpu")
            base["status"] = "AVAILABLE"
            base["runtime"] = getattr(recognizer, "active_provider", "CPU")
            support.append(base)
            for split_name, split_rows in (("legacy_val", legacy_val), ("expanded_val", expanded_val), ("locked_test", locked_test)):
                metrics = evaluate(recognizer, split_rows, eval_mod.preprocess_crop, eval_mod.calculate_metrics, eval_mod.normalize_plate_text)
                results.append({"candidate": spec["id"], "family": spec["family"], "split": split_name, **metrics})
        except Exception as exc:
            base["reason"] = f"local initialization/inference failed: {type(exc).__name__}: {str(exc)[:300]}"
            support.append(base)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "status": "COMPLETE_WITH_LOCAL_CANDIDATES",
        "dataset": str(DATASET.relative_to(ROOT)).replace("\\", "/"),
        "dataset_manifest_sha256": sha256(DATASET / "manifest.csv"),
        "ranking_policy": "legacy validation exact accuracy first; expanded validation is robustness evidence; locked test is read-only final readout",
        "support_matrix": support,
        "results": results,
        "ranking": sorted(
            [row for row in results if row["split"] in {"legacy_val", "expanded_val"}],
            key=lambda row: (row["split"] != "legacy_val", -row.get("postprocessed_exact_accuracy", 0.0), -row.get("raw_exact_accuracy", 0.0), row.get("p50_latency_ms") or 10**9),
        ),
    }
    (REPORT_DIR / "ocr_tournament.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (REPORT_DIR / "ocr_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["candidate", "family", "split", "samples", "raw_exact_accuracy", "postprocessed_exact_accuracy", "raw_character_accuracy", "postprocessed_character_accuracy", "raw_cer", "postprocessed_cer", "p50_latency_ms", "p95_latency_ms", "throughput_crops_per_sec"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"support": support, "result_count": len(results), "ranking": output["ranking"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
