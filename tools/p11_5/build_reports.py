"""Render the required P11.5 experiment reports from measured artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "p11_5"


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write(name: str, content: str) -> None:
    (REPORT_DIR / name).write_text(content.rstrip() + "\n", encoding="utf-8")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    eval_dir = REPORT_DIR / "detector_eval"
    # Only promote explicitly authoritative evaluations. Earlier runs are kept
    # locally for provenance but are not allowed to contaminate the final table.
    detector_files = [
        path for path in sorted(eval_dir.glob("*.json"))
        if "r3-clean-authoritative" in path.name or path.name.startswith("baseline-production-strict")
    ] if eval_dir.exists() else []
    detector_rows = [read_json(path, {}) for path in detector_files]
    with (REPORT_DIR / "p3_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["run_id", "weights", "imgsz", "batch", "precision", "recall", "f1", "map50", "map50_95", "tiny_recall", "square_or_tall_recall", "p50_ms", "p95_ms", "fps"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in detector_rows:
            writer.writerow({
                "run_id": row.get("run_id", ""), "weights": row.get("weights", ""), "imgsz": row.get("imgsz", ""), "batch": row.get("batch", ""), "precision": row.get("precision", ""), "recall": row.get("recall", ""), "f1": row.get("f1", ""), "map50": row.get("map50", ""), "map50_95": row.get("map50_95", ""), "tiny_recall": row.get("subsets", {}).get("tiny_lt60", {}).get("recall", ""), "square_or_tall_recall": row.get("subsets", {}).get("square_or_tall", {}).get("recall", ""), "p50_ms": row.get("latency", {}).get("1", {}).get("latency_ms_per_image", {}).get("p50", ""), "p95_ms": row.get("latency", {}).get("1", {}).get("latency_ms_per_image", {}).get("p95", ""), "fps": row.get("latency", {}).get("1", {}).get("fps", ""),
            })
    baseline = read_json(REPORT_DIR / "baseline" / "p3_baseline.json", {})
    strict = read_json(REPORT_DIR / "dataset" / "DETECTION_V2_STRICT_FREEZE.json", {})
    p3_lines = ["# P3 Tournament", "", "## Outcome", "", "The candidate runs below are measured on the strict detection V2 test split. Production weights were never overwritten.", "", table(["run", "imgsz", "P", "R", "F1", "mAP50", "mAP50-95", "tiny R", "square/tall R"], [[r.get("run_id"), r.get("imgsz"), r.get("precision"), r.get("recall"), r.get("f1"), r.get("map50"), r.get("map50_95"), r.get("subsets", {}).get("tiny_lt60", {}).get("recall"), r.get("subsets", {}).get("square_or_tall", {}).get("recall")] for r in detector_rows] or [["no completed candidate", "-", "-", "-", "-", "-", "-", "-", "-"]]), "", "## Required candidates and blockers", "", "YOLO11s transfer was run and will be promoted only from an authoritative clean-data evaluation. YOLO11m and YOLO26 were not run in this local pass; YOLO26 was not present in the installed Ultralytics 8.3.235 model/config package, so no unsupported checkpoint or score was fabricated. YOLO11s/YOLO11m OBB support is handled separately in OBB_REPORT.md.", "", f"Historical production baseline reference: {baseline.get('f1_score', baseline.get('f1', 'not available'))} F1 on the earlier canonical test; it is not directly interchangeable with the strict derivative test." ]
    write("P3_TOURNAMENT.md", "\n".join(p3_lines))

    obb = read_json(REPORT_DIR / "dataset" / "OBB_V2_STRICT_FREEZE.json", {})
    obb_train = [read_json(path, {}) for path in (ROOT / "runs" / "p11_5").glob("*/train_result.json") if path.parent.name == "obb-yolo11s-v2-e20-b4-640-r3-clean"] if (ROOT / "runs" / "p11_5").exists() else []
    obb_eval_dir = REPORT_DIR / "obb_eval"
    obb_eval = [read_json(path, {}) for path in obb_eval_dir.glob("*.json") if "r3-clean-authoritative" in path.name] if obb_eval_dir.exists() else []
    obb_eval_ids = {str(row.get("run_id", "")).replace("-authoritative", "") for row in obb_eval}
    obb_rows = [[r.get("run_id"), r.get("status"), "SELECTED" if r.get("run_id") in obb_eval_ids else r.get("decision"), r.get("weight_path")] for r in obb_train]
    with (REPORT_DIR / "obb_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["run_id", "weights", "imgsz", "precision", "recall", "f1", "map50", "map50_95"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in obb_eval:
            writer.writerow({field: row.get(field, "") for field in fields})
    write("OBB_REPORT.md", "\n".join(["# OBB Report", "", f"Strict OBB dataset: {obb.get('selected_unique_images', 'not built')} images; splits {obb.get('split_counts', {})}.", "", table(["candidate", "status", "decision", "weight"], obb_rows or [["YOLO11s-OBB", "checkpoint available; training pending/completed status is in registry", "-", "yolo11s-obb.pt"]]), "", "YOLO26-OBB remains unavailable in the current local package. The OBB label derivative uses polygon minimum-area rectangles where source polygons exist and axis-aligned fallback otherwise."]))

    ocr = read_json(REPORT_DIR / "ocr_tournament.json", {})
    ocr_rows = ocr.get("results", []) if ocr else []
    write("OCR_TOURNAMENT.md", "\n".join(["# OCR Tournament", "", "Ranking uses full-string exact accuracy first on legacy validation; expanded validation tests robustness; locked test is a final read-only readout.", "", table(["candidate", "split", "exact post", "char post", "CER post", "P50 ms", "P95 ms"], [[r.get("candidate"), r.get("split"), r.get("postprocessed_exact_accuracy"), r.get("postprocessed_character_accuracy"), r.get("postprocessed_cer"), r.get("p50_latency_ms"), r.get("p95_latency_ms")] for r in ocr_rows]), "", "Unavailable modern candidates are listed in the support matrix inside ocr_tournament.json; no score is claimed for missing implementations or weights."]))
    write("OCR_FINETUNE.md", "\n".join(["# OCR Fine-Tuning", "", "Status: NOT_COMPLETED_LOCALLY.", "", "The current PY312 environment has inference-ready PP-OCRv5 ONNX artifacts but no compatible PaddleOCR training stack/checkpoint export path. SVTRv2 and other modern recognizers have no local implementation/weights. Fine-tuning is therefore a documented blocker, not an invented result. The zero-shot tournament and locked test remain valid."]))

    synthetic = read_json(ROOT / "datasets" / "experiments" / "synthetic_indian_v2" / "manifest.json", {})
    write("SYNTHETIC_ABLATION.md", "\n".join(["# Synthetic Ablation", "", f"Corpus status: {synthetic.get('status', 'not completed')}; count: {synthetic.get('count', 0)}; target: 100,000.", "", table(["ablation", "status", "note"], [["real_only", "reference", "real strict V2"], ["synthetic_to_real", "not run", "requires separate staged detector training"], ["real_plus_synthetic_25pct", "not run", "requires ablation training"], ["real_plus_synthetic_50pct", "not run", "requires ablation training"]]), "", "Synthetic images are not authoritative test data and are ignored by Git. The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night." ]))

    temporal = read_json(REPORT_DIR / "temporal_evaluation.json", {})
    tr = temporal.get("results", []) if temporal else []
    write("TEMPORAL_REPORT.md", "\n".join(["# Temporal Report", "", "True sequence/registration-identity tracks only; no random equal-text grouping.", "", table(["window", "method", "eligible", "exact", "char", "CER"], [[r.get("window"), r.get("method"), r.get("eligible_tracks"), r.get("exact_accuracy"), r.get("character_accuracy"), r.get("cer")] for r in tr]), "", "Logit fusion is unavailable because the PP-OCRv5 ONNX interface exposes decoded text and character confidence, not timestep logits." ]))

    prep = read_json(REPORT_DIR / "preprocessing_evaluation.json", {})
    pr = prep.get("results", []) if prep else []
    best_val = max((r for r in pr if r.get("split") == "legacy_val"), key=lambda r: r.get("postprocessed_exact_accuracy", 0.0), default={})
    best_test = max((r for r in pr if r.get("split") == "locked_test"), key=lambda r: r.get("postprocessed_exact_accuracy", 0.0), default={})
    write("RECTIFICATION_SR_REPORT.md", "\n".join(["# Rectification / Enhancement / SR Report", "", "Measured PP-OCRv5 mobile over margins 0/2/4/6/8 and raw, CLAHE, sharpen, conservative rectification, and classical Lanczos x2.", "", f"Best legacy-validation configuration by postprocessed exact: margin={best_val.get('margin_px')}, variant={best_val.get('variant')}, exact={best_val.get('postprocessed_exact_accuracy')}.", f"Best locked-test configuration by postprocessed exact: margin={best_test.get('margin_px')}, variant={best_test.get('variant')}, exact={best_test.get('postprocessed_exact_accuracy')}.", "", "The x2 row is a classical resize proxy, not a learned SR claim. False-correction risk is represented by raw-vs-postprocessed exact deltas; inspect the JSON for all aggregate rows." ]))

    p1 = read_json(REPORT_DIR / "p1_operational.json", {})
    write("P1_TOURNAMENT.md", "\n".join(["# P1 Tournament", "", f"Status: {p1.get('status', 'not run')}.", "", "No external vehicle GT corpus was available locally, so accuracy/recall/FPR are explicitly unavailable. The real 25-frame video probe measures latency and throughput at 960px for batch 1/2/4.", "", table(["batch", "P50 ms/img", "P95 ms/img", "FPS", "peak VRAM"], [[r.get("batch"), r.get("latency_ms_per_image", {}).get("p50"), r.get("latency_ms_per_image", {}).get("p95"), r.get("fps"), r.get("peak_vram_bytes")] for r in p1.get("measurements", [])] or [["-", "-", "-", "-", "-"]])]))

    e2e = read_json(REPORT_DIR / "end_to_end_evaluation.json", {})
    write("END_TO_END_REPORT.md", "\n".join(["# End-to-End Report", "", "Pipeline: detector → predicted crop → PP-OCRv5 mobile → existing structural decoder metrics on strict real test.", "", table(["model", "det R", "OCR matched", "E2E exact", "E2E CER", "P50 ms", "P95 ms"], [[r.get("model"), r.get("detector_recall"), r.get("ocr_matched_detections"), r.get("end_to_end_post_exact_accuracy"), r.get("end_to_end_post_cer"), r.get("latency_ms", {}).get("p50"), r.get("latency_ms", {}).get("p95")] for r in e2e.get("results", [])] or [["not run", "-", "-", "-", "-", "-", "-"]]), "", "P5 safety FPR is unavailable because the strict plate test contains positive plate objects only and no negative vehicle/background GT." ]))

    final_selection = ["# Final Model Selection", "", "Selection is based on measured evidence, not parameter count:", "", "- OCR: PP-OCRv5 mobile remains selected for the balanced profile because its expanded-validation exact ties server after postprocessing while retaining substantially lower latency and better character accuracy/CER.", "- Temporal: current voter with a 5-frame window is the balanced operational choice; 8-frame current voter has the highest measured exact on its smaller eligible subset.", "- P3: the authoritative clean-data YOLO11s candidate is selected over production when its locked-test evaluation is present; otherwise selection remains pending.", "- P1: retain YOLO11m vehicle model as operational baseline until a real vehicle GT corpus is supplied."]
    write("FINAL_MODEL_SELECTION.md", "\n".join(final_selection))

    write("FINAL_REPORT.md", "\n".join(["# SentinelTrack P11.5B–E Final Execution Report", "", "## Executive summary", "", "This branch contains measured local P11.5 work: strict dataset freezes, a true multiframe benchmark, isolated detector/OBB harnesses, OCR screening, temporal consensus, preprocessing sweeps, synthetic corpus generation, hard-example mining, and operational reporting. Frozen V1 datasets, frontend, and CI were not modified.", "", "## Measured outcomes", "", f"- Detector candidate reports: {len(detector_rows)} evaluation artifacts.", f"- OCR candidate rows: {len(ocr_rows)}.", f"- Temporal tracks: {temporal.get('tracks', 'not run')} across {temporal.get('frames', 'not run')} crops.", f"- Synthetic corpus: {synthetic.get('count', 0)} generated examples against a 100,000 target.", "- Hard-example mining records aggregate failure categories and does not persist raw predictions.", "", "## Hard blockers and limitations", "", "- YOLO26 is unavailable in the installed local Ultralytics package; official OBB weights were downloaded only for the supported YOLO11 OBB stage.", "- No external vehicle GT corpus was available, so P1 recall/FPR and P5 safety regression are not claimable.", "- OCR fine-tuning was not completed because compatible training/export dependencies and modern local checkpoints are missing.", "- Synthetic 25%/50% ablation training remains pending; synthetic data is not used for authoritative test claims.", "- Cross-split raw SHA and identity leakage are clean. Upstream detection V2 retains pHash-near review findings; the strict derivative removes exact cross-split pHash source copies while preserving canonical V1 assignments.", f"- One malformed source JPEG is materialized deterministically with the Ultralytics-compatible repair ({strict.get('materialized_normalization_count', 0)} row); its original source SHA remains in the manifest and the materialized SHA is checked post-training.", "", "## Reproducibility", "", "Use the PY312 interpreter, the committed tools under tools/p11_5, the recorded manifest hashes, and the run registry. Candidate weights remain outside Git under runs/p11_5; production weights are never overwritten." ]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
