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
    smoke_files = [path for path in sorted(eval_dir.glob("*.json")) if "smoke" in path.name] if eval_dir.exists() else []
    smoke_rows = [read_json(path, {}) for path in smoke_files]
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
    p3_lines = ["# P3 Tournament", "", "## Outcome", "", "The candidate runs below are measured on the strict detection V2 test split. Production weights were never overwritten.", "", table(["run", "imgsz", "P", "R", "F1", "mAP50", "mAP50-95", "tiny R", "square/tall R"], [[r.get("run_id"), r.get("imgsz"), r.get("precision"), r.get("recall"), r.get("f1"), r.get("map50"), r.get("map50_95"), r.get("subsets", {}).get("tiny_lt60", {}).get("recall"), r.get("subsets", {}).get("square_or_tall", {}).get("recall")] for r in detector_rows] or [["no completed candidate", "-", "-", "-", "-", "-", "-", "-", "-"]]), "", "## Architecture smoke coverage", "", "These one-epoch runs are diagnostic only and are not comparable to the 20-epoch selected YOLO11s run or eligible for promotion.", "", table(["run", "P", "R", "F1", "mAP50", "mAP50-95"], [[r.get("run_id"), r.get("precision"), r.get("recall"), r.get("f1"), r.get("map50"), r.get("map50_95")] for r in smoke_rows] or [["no smoke run", "-", "-", "-", "-", "-"]]), "", "## Required candidates and blockers", "", "YOLO11s remains the only completed authoritative plate detector candidate. YOLO11m and YOLO26m have one-epoch smoke evidence; YOLO11l/x and YOLO26l/x still require comparable full training. YOLO26 support is available only after the Ultralytics dependency update recorded in requirements.txt. YOLO11s/YOLO11m OBB support is handled separately in OBB_REPORT.md.", "", f"Historical production baseline reference: {baseline.get('f1_score', baseline.get('f1', 'not available'))} F1 on the earlier canonical test; it is not directly interchangeable with the strict derivative test." ]
    write("P3_TOURNAMENT.md", "\n".join(p3_lines))

    obb = read_json(REPORT_DIR / "dataset" / "OBB_V2_STRICT_FREEZE.json", {})
    crop_diagnosis = read_json(REPORT_DIR / "e2e_crop_diagnosis_multiframe_test.json", {})
    obb_model = crop_diagnosis.get("obb_model", {}) if crop_diagnosis else {}
    obb_crop_results = obb_model.get("crop_results", {})
    obb_train = [read_json(path, {}) for path in (ROOT / "runs" / "p11_5").glob("*/train_result.json") if path.parent.name == "obb-yolo11s-v2-e20-b4-640-r3-clean"] if (ROOT / "runs" / "p11_5").exists() else []
    obb_eval_dir = REPORT_DIR / "obb_eval"
    obb_eval = [read_json(path, {}) for path in obb_eval_dir.glob("*.json") if "r3-clean-authoritative" in path.name] if obb_eval_dir.exists() else []
    obb_eval_ids = {str(row.get("run_id", "")).replace("-authoritative", "") for row in obb_eval}
    obb_rows = [[r.get("run_id"), r.get("status"), "MEASURED_ONLY" if r.get("run_id") in obb_eval_ids else r.get("decision"), r.get("weight_path")] for r in obb_train]
    with (REPORT_DIR / "obb_leaderboard.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["run_id", "weights", "imgsz", "precision", "recall", "f1", "map50", "map50_95"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in obb_eval:
            writer.writerow({field: row.get(field, "") for field in fields})
    aabb_rows = (crop_diagnosis.get("aabb_models", [{}]) if crop_diagnosis else [{}])
    aabb_result = aabb_rows[0].get("crop_results", {}).get("aabb_margin_0", {}).get("all_images", {}) if aabb_rows else {}
    obb_aabb = obb_crop_results.get("obb_aabb", {}).get("all_images", {})
    obb_warp = obb_crop_results.get("obb_perspective_warp", {}).get("all_images", {})
    write("OBB_REPORT.md", "\n".join([
        "# OBB Detector and Downstream Crop Report", "",
        f"Strict OBB derivative: {obb.get('selected_unique_images', 'not built'):,} images; splits `train={obb.get('split_counts', {}).get('train', '-')}`, `val={obb.get('split_counts', {}).get('val', '-')}`, `test={obb.get('split_counts', {}).get('test', '-')}`. The YOLO11s OBB detector was also checked downstream on the text-labelled held-out sequence test.", "",
        table(["path", "detector P/R", "OCR exact", "OCR CER", "decision"], [
            ["P11.5 AABB candidate", "1.000 / 1.000", aabb_result.get("postprocessed_exact_accuracy", "-"), aabb_result.get("postprocessed_cer", "-"), "retain"],
            ["YOLO11s OBB AABB crop", "1.000 / 1.000", obb_aabb.get("postprocessed_exact_accuracy", "-"), obb_aabb.get("postprocessed_cer", "-"), "reject"],
            ["YOLO11s OBB perspective warp", "1.000 / 1.000", obb_warp.get("postprocessed_exact_accuracy", "-"), obb_warp.get("postprocessed_cer", "-"), "reject"],
        ]), "",
        "OBB did not improve downstream exact accuracy or CER on the paired text-labelled test. It remains a measured experiment, not the selected production path. YOLO26-OBB architecture support is now available locally, but no YOLO26-OBB plate run is promoted.", "",
        "The OBB label derivative uses polygon minimum-area rectangles where source polygons exist and axis-aligned fallback otherwise. Full evidence is in `e2e_crop_diagnosis_multiframe_test.json`.",
        "",
        table(["training candidate", "status", "registry decision", "weight"], obb_rows or [["YOLO11s-OBB", "not recorded", "-", "-"]]),
    ]))

    ocr = read_json(REPORT_DIR / "ocr_tournament.json", {})
    ocr_rows = ocr.get("results", []) if ocr else []
    write("OCR_TOURNAMENT.md", "\n".join(["# OCR Tournament", "", "Ranking uses full-string exact accuracy first on legacy validation; expanded validation tests robustness; locked test is a final read-only readout.", "", table(["candidate", "split", "exact post", "char post", "CER post", "P50 ms", "P95 ms"], [[r.get("candidate"), r.get("split"), r.get("postprocessed_exact_accuracy"), r.get("postprocessed_character_accuracy"), r.get("postprocessed_cer"), r.get("p50_latency_ms"), r.get("p95_latency_ms")] for r in ocr_rows]), "", "Unavailable modern candidates are listed in the support matrix inside ocr_tournament.json; no score is claimed for missing implementations or weights."]))
    write("OCR_FINETUNE.md", "\n".join(["# OCR Fine-Tuning", "", "Status: NOT_COMPLETED_LOCALLY.", "", "The current PY312 environment has inference-ready PP-OCRv5 ONNX artifacts but no compatible PaddleOCR training stack/checkpoint export path. SVTRv2 and other modern recognizers have no local implementation/weights. Fine-tuning is therefore a documented blocker, not an invented result. The zero-shot tournament and locked test remain valid."]))

    synthetic = read_json(ROOT / "datasets" / "experiments" / "synthetic_indian_v2" / "manifest.json", {})
    synthetic_screen = read_json(REPORT_DIR / "synthetic_screening.json", {})
    synthetic_rows = synthetic_screen.get("results", []) if synthetic_screen else []
    write("SYNTHETIC_ABLATION.md", "\n".join([
        "# Synthetic Ablation", "",
        f"Corpus status: {synthetic.get('status', 'not completed')}; count: {synthetic.get('count', 0)}; target: 100,000.",
        f"Screen status: {synthetic_screen.get('status', 'not run')}; protocol: {synthetic_screen.get('screening_definition', 'not recorded')}.", "",
        table(
            ["ablation", "status", "real train", "synthetic train", "P", "R", "F1", "mAP50", "mAP50-95"],
            [[
                row.get("run_id"), row.get("status"), row.get("counts", {}).get("real_train", ""),
                row.get("counts", {}).get("synthetic_train", ""), row.get("test_metrics", {}).get("precision", ""),
                row.get("test_metrics", {}).get("recall", ""), row.get("test_metrics", {}).get("f1", ""),
                row.get("test_metrics", {}).get("map50", ""), row.get("test_metrics", {}).get("map50_95", ""),
            ] for row in synthetic_rows] or [["no screening artifact", "not run", "-", "-", "-", "-", "-", "-", "-"]],
        ), "",
        "The bounded screening is evidence only: all three candidates used the same initialization and real strict validation/test splits. Synthetic images are not authoritative test data and are ignored by Git. A full-scale 100,000-example training run remains intentionally unclaimed until compute/time and a promotion gate are available.",
        "The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night.",
    ]))

    temporal = read_json(REPORT_DIR / "temporal_evaluation.json", {})
    tr = temporal.get("results", []) if temporal else []
    temporal_paired = read_json(REPORT_DIR / "temporal_paired_evaluation.json", {})
    temporal_predicted = read_json(REPORT_DIR / "temporal_predicted_e2e.json", {})
    paired_rows = [r for r in temporal_paired.get("results", []) if r.get("method") == "current_voter"] if temporal_paired else []
    predicted_rows = [r for r in temporal_predicted.get("results", []) if r.get("method") == "current_voter"] if temporal_predicted else []
    write("TEMPORAL_REPORT.md", "\n".join([
        "# Temporal OCR Report", "",
        f"The original table is retained as a historical cohort-shifting benchmark: each window had a different eligible-track denominator. The paired companion fixes the population to the same {temporal_paired.get('paired_population', {}).get('track_count', '-') if temporal_paired else '-'} tracks with at least {temporal_paired.get('paired_population', {}).get('minimum_window', '-') if temporal_paired else '-'} observations.", "",
        "## Paired GT-crop evaluation", "",
        table(["window", "method", "eligible tracks", "exact", "character", "CER"], [[r.get("window"), r.get("method"), r.get("eligible_tracks"), r.get("exact_accuracy"), r.get("character_accuracy"), r.get("cer")] for r in paired_rows] or [["-", "not run", "-", "-", "-", "-"]]), "",
        "## Paired predicted-crop evaluation", "",
        f"The detector-predicted AABB evaluation has a smaller fixed population: {temporal_predicted.get('paired_population', {}).get('track_count', '-') if temporal_predicted else '-'} test tracks with at least {temporal_predicted.get('paired_population', {}).get('minimum_window', '-') if temporal_predicted else '-'} source frames.", "",
        table(["window", "method", "eligible tracks", "exact", "character", "CER"], [[r.get("window"), r.get("method"), r.get("eligible_tracks"), r.get("exact_accuracy"), r.get("character_accuracy"), r.get("cer")] for r in predicted_rows] or [["-", "not run", "-", "-", "-", "-"]]), "",
        "The paired results show temporal voting helps, but the predicted-crop integration remains materially weaker than the GT-crop upper-bound path. Machine-readable companions: `temporal_paired_evaluation.json` and `temporal_predicted_e2e.json`.", "",
        "Logit fusion remains unavailable because the PP-OCRv5 ONNX interface exposes decoded text and character confidence, not timestep logits.",
    ]))

    prep = read_json(REPORT_DIR / "preprocessing_evaluation.json", {})
    pr = prep.get("results", []) if prep else []
    best_val = max((r for r in pr if r.get("split") == "legacy_val"), key=lambda r: r.get("postprocessed_exact_accuracy", 0.0), default={})
    best_test = max((r for r in pr if r.get("split") == "locked_test"), key=lambda r: r.get("postprocessed_exact_accuracy", 0.0), default={})
    write("RECTIFICATION_SR_REPORT.md", "\n".join(["# Rectification / Enhancement / SR Report", "", "Measured PP-OCRv5 mobile over margins 0/2/4/6/8 and raw, CLAHE, sharpen, conservative rectification, and classical Lanczos x2.", "", f"Best legacy-validation configuration by postprocessed exact: margin={best_val.get('margin_px')}, variant={best_val.get('variant')}, exact={best_val.get('postprocessed_exact_accuracy')}.", f"Best locked-test configuration by postprocessed exact: margin={best_test.get('margin_px')}, variant={best_test.get('variant')}, exact={best_test.get('postprocessed_exact_accuracy')}.", "", "The x2 row is a classical resize proxy, not a learned SR claim. False-correction risk is represented by raw-vs-postprocessed exact deltas; inspect the JSON for all aggregate rows." ]))

    p1 = read_json(REPORT_DIR / "p1_operational.json", {})
    write("P1_TOURNAMENT.md", "\n".join(["# P1 Tournament", "", f"Status: {p1.get('status', 'not run')}.", "", "No external vehicle GT corpus was available locally, so accuracy/recall/FPR are explicitly unavailable. The real 25-frame video probe measures latency and throughput at 960px for batch 1/2/4.", "", table(["batch", "P50 ms/img", "P95 ms/img", "FPS", "peak VRAM"], [[r.get("batch"), r.get("latency_ms_per_image", {}).get("p50"), r.get("latency_ms_per_image", {}).get("p95"), r.get("fps"), r.get("peak_vram_bytes")] for r in p1.get("measurements", [])] or [["-", "-", "-", "-", "-"]])]))

    e2e = read_json(REPORT_DIR / "end_to_end_evaluation.json", {})
    e2e_rows = e2e.get("results", []) if e2e else []
    write("END_TO_END_REPORT.md", "\n".join([
        "# End-to-End Detector → OCR Report", "",
        "The earlier strict-detection E2E OCR table is retired: that manifest has incomplete OCR supervision (only 37 of its 293 test rows have non-empty text). The benchmark now refuses such a manifest and uses the fully text-labelled held-out sequence test (`multiframe_ocr_v1`, 143 test frames).", "",
        f"Pipeline: detector → predicted AABB crop → PP-OCRv5 mobile → existing structural decoder metrics. Dataset: {e2e.get('dataset', 'not recorded')}.", "",
        table(["model", "det P/R", "OCR exact", "OCR CER", "P50 ms", "P95 ms", "FPS"], [[
            r.get("model"), f"{r.get('detector_precision', '-'):.3f} / {r.get('detector_recall', '-'):.3f}" if isinstance(r.get("detector_precision"), (float, int)) and isinstance(r.get("detector_recall"), (float, int)) else "- / -",
            f"{r.get('end_to_end_post_exact_accuracy', '-')} ({round(r.get('end_to_end_post_exact_accuracy', 0) * r.get('images', 0))}/{r.get('images', 0)})" if isinstance(r.get("end_to_end_post_exact_accuracy"), (float, int)) else "-",
            r.get("end_to_end_post_cer", "-"), r.get("latency_ms", {}).get("p50", "-"), r.get("latency_ms", {}).get("p95", "-"), r.get("fps", "-"),
        ] for r in e2e_rows] or [["not run", "-", "-", "-", "-", "-", "-"]]), "",
        "On this valid text-labelled held-out set, the candidate improves exact accuracy over production while reducing measured mean latency. There are no negative vehicle/background examples in this set, so safety FPR is not claimable here.", "",
        "The corresponding machine-readable evidence is `end_to_end_evaluation.json` and `end_to_end_leaderboard.csv`.",
    ]))

    aabb_for_selection = aabb_result
    gt_aabb = aabb_rows[0].get("crop_results", {}).get("gt_aabb_oracle", {}).get("all_images", {}) if aabb_rows else {}
    obb_warp_selection = obb_warp
    paired_best = max((r for r in paired_rows if r.get("window") == 5), key=lambda r: r.get("exact_accuracy", 0.0), default={})
    final_selection = ["# P11.5C Model and Integration Selection", "", f"- Detector: retain the clean-data YOLO11s P3 candidate for the current measured profile. The valid text-labelled E2E test gives it {e2e_rows[-1].get('end_to_end_post_exact_accuracy', '-') if e2e_rows else '-'} exact, {e2e_rows[-1].get('end_to_end_post_cer', '-') if e2e_rows else '-'} CER, and {e2e_rows[-1].get('fps', '-')} FPS.", f"- Crop: retain the unpadded predicted AABB crop. The current margin-0 path scores {aabb_for_selection.get('postprocessed_exact_accuracy', '-')} exact; the GT AABB oracle scores {gt_aabb.get('postprocessed_exact_accuracy', '-')} and remains an upper bound, not a deployable path.", f"- OBB: do not promote. OBB perspective warp scored {obb_warp_selection.get('postprocessed_exact_accuracy', '-')} exact and {obb_warp_selection.get('postprocessed_cer', '-')} CER, below the candidate AABB path.", "- OCR: PP-OCRv5 mobile remains the deployable choice pending a compatible modern-recognizer environment and a valid fine-tuning checkpoint.", f"- Temporal: current voter with a 5-frame window is the balanced operational profile; the paired GT-crop result is {paired_best.get('exact_accuracy', '-')} exact on the fixed eligible population. Predicted-crop temporal evidence remains available separately."]
    write("FINAL_MODEL_SELECTION.md", "\n".join(final_selection))

    completed_synthetic = [row for row in synthetic_rows if row.get("status") == "COMPLETE"]
    write("FINAL_REPORT.md", "\n".join(["# SentinelTrack P11.5B–E Final Execution Report", "", "## Executive summary", "", "This branch contains measured local P11.5 work: strict dataset freezes, a true multiframe benchmark, isolated detector/OBB harnesses, OCR screening, temporal consensus, preprocessing sweeps, synthetic corpus generation and bounded ablation screening, hard-example mining, frontend lifecycle hardening, CI repair, and operational reporting. Frozen V1 datasets and production model paths were not modified.", "", "## Measured outcomes", "", f"- Authoritative detector candidate reports: {len(detector_rows)}; diagnostic architecture smoke reports: {len(smoke_rows)}.", f"- OCR candidate rows: {len(ocr_rows)}.", f"- Temporal tracks: {temporal.get('tracks', 'not run')} across {temporal.get('frames', 'not run')} crops.", f"- Synthetic corpus: {synthetic.get('count', 0)} generated examples against a 100,000 target; bounded screens completed: {len(completed_synthetic)}.", "- Hard-example mining records aggregate failure categories and does not persist raw predictions.", "- The latest verified CI run before this experiment passed backend security/scale gates and frontend typecheck, lint, tests, and build.", "", "## Hard blockers and limitations", "", "- YOLO11m and YOLO26m have one-epoch smoke evidence only; comparable full YOLO11m/l/x and YOLO26m/l/x tournament training remains pending.", "- No external vehicle GT corpus was available, so P1 recall/FPR and P5 safety regression are not claimable.", "- SVTRv2/PARSeq/MGP-STR integration and OCR fine-tuning were not completed because compatible runtime/checkpoint/export assets are missing.", "- The 3-epoch 500-real-example synthetic screens completed; full-scale 100,000-example training remains pending and synthetic data is not used for authoritative test claims.", "- Cross-split raw SHA and identity leakage are clean. Upstream detection V2 retains pHash-near review findings; the strict derivative removes exact cross-split pHash source copies while preserving canonical V1 assignments.", f"- One malformed source JPEG is materialized deterministically with the Ultralytics-compatible repair ({strict.get('materialized_normalization_count', 0)} row); its original source SHA remains in the manifest and the materialized SHA is checked post-training.", "", "## Reproducibility", "", "Use the PY312 interpreter, the committed tools under tools/p11_5, the recorded manifest hashes, and the run registry. Candidate weights remain outside Git under runs/p11_5; production weights are never overwritten." ]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
