"""Create an evidence matrix for the requested P11.5 follow-up work.

This report is deliberately fail-closed.  A model family is not marked as
completed merely because its name is recognized by a library: it needs a
reproducible checkpoint, training/evaluation evidence, and a comparable
locked-set result.  The script only inspects local files and existing reports;
it does not install packages, download weights, modify production artifacts,
or alter frozen datasets.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import platform
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "p11_5"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def import_status(module_name: str) -> dict[str, Any]:
    if importlib.util.find_spec(module_name) is None:
        return {"installed": False, "status": "MISSING"}
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # optional integrations must never abort the audit
        return {
            "installed": True,
            "status": "IMPORT_FAILED",
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }
    return {"installed": True, "status": "IMPORTABLE", "version": getattr(module, "__version__", "unknown")}


def ultralytics_status() -> dict[str, Any]:
    try:
        module = importlib.import_module("ultralytics")
        root = Path(module.__file__).resolve().parent
        config_dir = root / "cfg" / "models"
        return {
            "status": "IMPORTABLE",
            "version": getattr(module, "__version__", "unknown"),
            "model_families": {
                "11": (config_dir / "11").is_dir(),
                "26": (config_dir / "26").is_dir(),
            },
        }
    except Exception as exc:
        return {"status": "IMPORT_FAILED", "error": f"{type(exc).__name__}: {str(exc)[:500]}"}


def model_entry(name: str, family: str, local_paths: list[Path], package_ready: bool, run_fragment: str) -> dict[str, Any]:
    present = next((path for path in local_paths if path.is_file()), None)
    training_runs: list[dict[str, Any]] = []
    for run_root in sorted((ROOT / "runs" / "p11_5").glob(f"*{run_fragment}*")):
        result = read_json(run_root / "train_result.json")
        if result:
            training_runs.append({
                "run_id": result.get("run_id", run_root.name),
                "status": result.get("status"),
                "epochs": result.get("epochs"),
                "batch": result.get("batch"),
                "training_time_seconds": result.get("training_time_seconds"),
                "metrics": result.get("metrics", {}),
                "weight_path": result.get("weight_path"),
            })
    evaluation_runs: list[dict[str, Any]] = []
    eval_dir = REPORT_DIR / "detector_eval"
    if eval_dir.is_dir():
        for eval_path in sorted(eval_dir.glob(f"*{run_fragment}*.json")):
            result = read_json(eval_path)
            if result:
                evaluation_runs.append({
                    "run_id": result.get("run_id", eval_path.stem),
                    "split": result.get("split"),
                    "precision": result.get("precision"),
                    "recall": result.get("recall"),
                    "f1": result.get("f1"),
                    "map50": result.get("map50"),
                    "map50_95": result.get("map50_95"),
                    "latency": result.get("latency", {}),
                    "evidence_file": eval_path.relative_to(ROOT).as_posix(),
                })
    if evaluation_runs:
        status = "TRAINED_SMOKE_EVALUATED_NOT_FINAL"
    elif training_runs:
        status = "TRAINED_SMOKE_NOT_FINAL"
    elif present:
        status = "CHECKPOINT_PRESENT_NOT_TRAINED"
    elif package_ready:
        status = "READY_FOR_ISOLATED_TRAINING"
    else:
        status = "BLOCKED_PACKAGE"
    return {
        "candidate": name,
        "family": family,
        "local_checkpoint": present.relative_to(ROOT).as_posix() if present else None,
        "checkpoint_sha256": sha256(present) if present else None,
        "package_architecture_available": package_ready,
        "status": status,
        "training_runs": training_runs,
        "evaluation_runs": evaluation_runs,
    }


def build_report() -> dict[str, Any]:
    ultra = ultralytics_status()
    families = ultra.get("model_families", {}) if isinstance(ultra, dict) else {}
    models = [
        model_entry("YOLO11m plate", "YOLO11", [ROOT / "yolo11m.pt", ROOT / "models" / "vehicle" / "yolo11m.pt"], bool(families.get("11")), "yolo11m"),
        model_entry("YOLO11l plate", "YOLO11", [ROOT / "yolo11l.pt"], bool(families.get("11")), "yolo11l"),
        model_entry("YOLO11x plate", "YOLO11", [ROOT / "yolo11x.pt"], bool(families.get("11")), "yolo11x"),
        model_entry("YOLO26m plate", "YOLO26", [ROOT / "yolo26m.pt"], bool(families.get("26")), "yolo26m"),
        model_entry("YOLO26l plate", "YOLO26", [ROOT / "yolo26l.pt"], bool(families.get("26")), "yolo26l"),
        model_entry("YOLO26x plate", "YOLO26", [ROOT / "yolo26x.pt"], bool(families.get("26")), "yolo26x"),
    ]

    modern_packages = {
        name: import_status(name)
        for name in ("paddle", "paddleocr", "openocr", "parseq", "mgp_str")
    }
    ocr_weights = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "models" / "ocr").glob("*")
        if path.is_file()
    )
    training_checkpoints = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "models" / "ocr").rglob("*")
        if path.is_file() and path.suffix.lower() in {".pdparams", ".pth", ".pt", ".ckpt", ".safetensors"}
    )
    probe = read_json(REPORT_DIR / "modern_ocr_probe.json")
    synthetic_manifest = read_json(ROOT / "datasets" / "experiments" / "synthetic_indian_v2" / "manifest.json")
    synthetic_screen = read_json(REPORT_DIR / "synthetic_screening.json")

    return {
        "schema_version": 1,
        "environment": {
            "name": "PY312",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "ultralytics": ultra,
        },
        "detector_tournament": {
            "status": "INCOMPLETE_LOCAL_EVIDENCE",
            "rule": "A candidate requires a completed isolated training run plus locked plate validation before it can be ranked or promoted.",
            "candidates": models,
            "partial_runs": [
                {
                    "run_id": "p11-5-yolo11m-plate-e20",
                    "status": "INTERRUPTED_BEFORE_EPOCH_COMPLETION",
                    "reason": "20-epoch batch-1 run estimated several hours on the local 4 GB GPU; no checkpoint or metric was accepted.",
                },
            ],
            "existing_plate_winner": {
                "candidate": "YOLO11s custom plate detector",
                "exact_accuracy_end_to_end": 0.3427,
                "cer_end_to_end": 0.2669,
                "locked_detector_map50": 0.984996,
                "locked_detector_map50_95": 0.722429,
                "decision": "CURRENT_REFERENCE",
            },
        },
        "modern_ocr": {
            "status": "BLOCKED_LOCAL_RUNTIME_AND_CHECKPOINTS",
            "families": {
                "SVTRv2": {"status": "NOT_EVALUATED", "reason": "Paddle/PaddleOCR import fails in PY312; no compatible local SVTRv2 checkpoint is present."},
                "PARSeq": {"status": "NOT_EVALUATED", "reason": "No local PARSeq package or checkpoint is present."},
                "MGP-STR": {"status": "NOT_EVALUATED", "reason": "No local MGP-STR package or checkpoint is present."},
            },
            "package_probe": modern_packages,
            "probe_report": probe,
            "local_ocr_weights": ocr_weights,
        },
        "ocr_finetuning": {
            "status": "NOT_COMPLETED",
            "training_checkpoints": training_checkpoints,
            "reason": "Only ONNX PP-OCRv5 inference exports are available; no compatible train checkpoint/config/export toolchain is present.",
            "production_impact": "No production OCR model was replaced.",
        },
        "synthetic_curriculum": {
            "status": "CORPUS_COMPLETE_SCREENING_ONLY",
            "corpus_count": synthetic_manifest.get("count"),
            "train_count": synthetic_manifest.get("split_counts", {}).get("train"),
            "screening": synthetic_screen,
            "full_scale_training_completed": False,
            "reason": "The 100,000-image corpus exists, but authoritative full-scale curriculum training has not completed on this workstation.",
        },
        "production_crop": {
            "status": "EVALUATED_NO_PROMOTION",
            "production_code_changed": False,
            "selected_strategy": "predicted unpadded AABB crop",
            "predicted_aabb_exact_accuracy": 0.3427,
            "obb_perspective_warp_exact_accuracy": 0.3357,
            "gt_aabb_oracle_exact_accuracy": 0.4266,
            "decision": "Keep current AABB path; OBB would regress the measured end-to-end result and the GT oracle is not deployable.",
        },
        "overall": {
            "all_requested_items_completed": False,
            "safe_completed_items": ["local OCR tournament", "bounded synthetic screening", "crop strategy evaluation", "production preservation"],
            "remaining_blockers": ["full YOLO11m/l/x comparable training", "full YOLO26m/l/x comparable training", "SVTRv2/PARSeq/MGP-STR runtime and checkpoints", "OCR train checkpoint/toolchain", "full-scale synthetic curriculum run"],
        },
    }


def markdown(report: dict[str, Any]) -> str:
    detector = report["detector_tournament"]

    def table(headers: list[str], rows: list[list[Any]]) -> str:
        lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
        return "\n".join(lines)

    def display(value: Any) -> str:
        return f"{value:.4f}" if isinstance(value, (float, int)) else "-"

    candidate_rows = []
    for candidate in detector["candidates"]:
        training = candidate.get("training_runs", [])[-1] if candidate.get("training_runs") else {}
        evaluation = candidate.get("evaluation_runs", [])[-1] if candidate.get("evaluation_runs") else {}
        latency = evaluation.get("latency", {}).get("1", {}).get("latency_ms_per_image", {})
        candidate_rows.append([
            candidate.get("candidate"),
            candidate.get("status"),
            training.get("epochs", "-"),
            display(evaluation.get("map50")),
            display(evaluation.get("map50_95")),
            display(evaluation.get("f1")),
            display(latency.get("p50")),
        ])
    rows = [
        "# P11.5 Requested Completion Matrix",
        "",
        "Generated from local PY312 files and reports. A missing checkpoint or interrupted run is not reported as a model result.",
        "",
        "| Requested item | Status | Evidence / result |",
        "|---|---|---|",
        f"| YOLO11m/l/x plate tournament | {detector['status']} | No comparable completed m/l/x plate tournament; existing YOLO11s reference end-to-end exact {detector['existing_plate_winner']['exact_accuracy_end_to_end']:.4f}. |",
        f"| YOLO26 tournament | INCOMPLETE_LOCAL_EVIDENCE | Installed Ultralytics family support: {report['environment']['ultralytics'].get('model_families', {}).get('26', False)}; YOLO26m has smoke evidence, while l/x have no completed run. |",
        f"| SVTRv2 / PARSeq / MGP-STR | {report['modern_ocr']['status']} | No runnable local package/checkpoint for these requested candidates. |",
        f"| OCR fine-tuning | {report['ocr_finetuning']['status']} | {report['ocr_finetuning']['reason']} |",
        f"| Full-scale synthetic curriculum | {report['synthetic_curriculum']['status']} | {report['synthetic_curriculum']['corpus_count']} generated; bounded screens only, full-scale training pending. |",
        f"| Production crop modification | {report['production_crop']['status']} | AABB {report['production_crop']['predicted_aabb_exact_accuracy']:.4f}; OBB {report['production_crop']['obb_perspective_warp_exact_accuracy']:.4f}; production left unchanged. |",
        "",
        "## Detector candidate evidence",
        "",
        "Smoke rows are one-epoch diagnostics; they are not a fair ranking against the completed 20-epoch YOLO11s reference.",
        "",
        table(["candidate", "status", "epochs", "test mAP50", "test mAP50-95", "test F1", "test P50 ms"], candidate_rows),
        "",
        "## Interpretation",
        "",
        "The requested list was not previously completed in full. The existing work is a valid measured baseline and screening package, but it does not justify claiming a full model tournament, modern OCR integration, OCR fine-tuning, or full-scale synthetic training. The crop item is intentionally an evaluation/no-promotion decision because the measured alternative was worse.",
        "",
        "## Reproducibility",
        "",
        "Run `C:\\Users\\SHOAIB-CHANDA\\miniconda3\\envs\\py312\\python.exe tools\\p11_5\\requested_completion_matrix.py` from the repository root.",
    ]
    return "\n".join(rows) + "\n"


def main() -> int:
    report = build_report()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "requested_completion_matrix.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORT_DIR / "REQUESTED_COMPLETION_MATRIX.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
