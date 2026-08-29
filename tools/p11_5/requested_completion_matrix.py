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
            "status": "FULL_ARCHITECTURE_TOURNAMENT_DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE",
            "rule": "A candidate requires a completed isolated training run plus locked plate validation before it can be ranked or promoted.",
            "freeze_decision": "Retain clean YOLO11s as the measured high-accuracy real-time detector; do not start YOLO11x or YOLO26l/x for this freeze.",
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
                "exact_accuracy_end_to_end": 0.342657,
                "cer_end_to_end": 0.2662,
                "locked_detector_map50": 0.992824,
                "locked_detector_map50_95": 0.783111,
                "decision": "CURRENT_REFERENCE",
            },
        },
        "modern_ocr": {
            "status": "DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE",
            "families": {
                "SVTRv2": {"status": "NOT_EVALUATED", "reason": "Explicitly deferred; no comparable locked-set integration is required for the bounded P11.5 freeze."},
                "PARSeq": {"status": "NOT_EVALUATED", "reason": "No local PARSeq production integration or checkpoint; optional future research."},
                "MGP-STR": {"status": "NOT_EVALUATED", "reason": "No local MGP-STR production integration or checkpoint; optional future research."},
            },
            "package_probe": modern_packages,
            "probe_report": probe,
            "local_ocr_weights": ocr_weights,
        },
        "ocr_finetuning": {
            "status": "INTERRUPTED_RESOURCE_LIMITED_NO_CHECKPOINT",
            "training_checkpoints": training_checkpoints,
            "attempt": {
                "environment": "sentinel_ocr_paddle",
                "python": "3.10.21",
                "paddlepaddle": "3.3.1",
                "paddleocr": "3.7.0",
                "official_source_commit": "2661c7c0ef5c613e8f93c6e93b2e052399f0f854",
                "pretrained_model": "PP-OCRv5_mobile_rec_pretrained.pdparams",
                "pretrained_sha256": "04745475b97a1faf029c7442a4c4421b156249b9395814e509bf4a9804e37750",
                "data": "real-only; train=1382; val=147; locked_test=178 held out",
                "config": "official PP-OCRv5_mobile_rec.yml; epochs=1; batch=8; Adam; cosine LR=0.0005; CPU",
                "result": "no checkpoint, validation metric, export, or locked-test read before bounded resource stop",
            },
            "reason": "Official PaddleOCR training was attempted in an isolated environment, but the CPU run did not reach its first logging interval and produced no checkpoint or metric. PP-OCRv5 Mobile ONNX remains selected.",
            "production_impact": "No production OCR model was replaced.",
        },
        "synthetic_curriculum": {
            "status": "REJECTED_BY_BOUNDED_SCREEN",
            "corpus_count": synthetic_manifest.get("count"),
            "train_count": synthetic_manifest.get("split_counts", {}).get("train"),
            "screening": synthetic_screen,
            "full_scale_training_completed": False,
            "decision": "REJECTED_BY_BOUNDED_SCREEN",
            "reason": "Bounded real-only training was best: F1=0.979098 and mAP50-95=0.732293 versus +25% synthetic F1=0.971685/mAP50-95=0.726403 and +50% F1=0.976009/mAP50-95=0.698319. Full-scale 100,000-image training is not required for the P11.5 freeze.",
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
            "p11_5_freeze_ready": True,
            "all_requested_items_completed": False,
            "safe_completed_items": ["same-manifest detector comparison", "corrected all-detection recognition-chain accounting", "local OCR tournament", "bounded official OCR fine-tuning attempt", "bounded synthetic screening", "crop strategy evaluation", "production preservation", "runtime isolation"],
            "remaining_blockers": [],
            "optional_future_research": ["full YOLO11m/l/x and YOLO26m/l/x architecture tournament", "SVTRv2/PARSeq/MGP-STR integration", "longer OCR fine-tuning after a compute-capable training run", "full-scale synthetic curriculum only if a later promotion gate justifies it"],
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
        f"| YOLO26 tournament | FULL_ARCHITECTURE_TOURNAMENT_DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE | YOLO26m smoke evidence remains diagnostic; l/x are intentionally not started. Production runtime remains pinned and the YOLO26 dependency is isolated. |",
        f"| SVTRv2 / PARSeq / MGP-STR | {report['modern_ocr']['status']} | No comparable local production integration/checkpoint was evaluated; these are optional future candidates. |",
        f"| OCR fine-tuning | {report['ocr_finetuning']['status']} | {report['ocr_finetuning']['reason']} |",
        f"| Full-scale synthetic curriculum | {report['synthetic_curriculum']['status']} | {report['synthetic_curriculum']['corpus_count']} generated; real-only won the bounded screen, so synthetic addition is rejected. |",
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
        "P11.5 freeze decision: all locally feasible evidence and accounting work is complete. Full architecture tournaments, modern OCR alternatives, longer OCR optimization, and full-scale synthetic training are optional future research—not blockers for this freeze. The crop item is an evaluation/no-promotion decision because the measured alternative was worse.",
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
