"""Run the safe, evidence-producing portion of the P11.5 suite.

The default command is read-only with respect to source data and existing
models.  Dataset rebuilding and hardware probing are explicit flags.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "p11_5"


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "MISSING", "path": str(path.relative_to(ROOT)).replace("\\", "/")}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {"status": "AVAILABLE", "path": str(path.relative_to(ROOT)).replace("\\", "/"), "value": value}
    except Exception as exc:
        return {"status": "INVALID", "path": str(path.relative_to(ROOT)).replace("\\", "/"), "reason": f"{type(exc).__name__}: {exc}"}


def collect_baselines() -> dict[str, Any]:
    return {
        "p1": _read_json(ROOT / "reports" / "p11_5" / "baseline" / "p1_baseline.json"),
        "p3": _read_json(ROOT / "reports" / "p11_5" / "baseline" / "p3_baseline.json"),
        "p4": _read_json(ROOT / "reports" / "p11_5" / "baseline" / "p4_baseline.json"),
    }


def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    actions: dict[str, Any] = {}
    audit_requested = args.dataset_audit
    build_requested = args.build_v2
    hardware_requested = args.hardware
    if not any((audit_requested, build_requested, hardware_requested, args.profile, args.baseline, args.temporal)):
        args.profile = True
        args.baseline = True

    if audit_requested:
        module = _load("p11_5_audit_dataset", "audit_dataset.py")
        actions["dataset_audit_exit_code"] = int(module.main())
        actions["dataset_audit"] = _read_json(ROOT / "reports" / "p11_5" / "dataset" / "audit_summary.json")
    elif (ROOT / "reports" / "p11_5" / "dataset" / "audit_summary.json").exists():
        actions["dataset_audit"] = _read_json(ROOT / "reports" / "p11_5" / "dataset" / "audit_summary.json")

    if build_requested:
        module = _load("p11_5_build_v2", "build_v2.py")
        actions["build_v2_exit_code"] = int(module.main())
        actions["v2_summary"] = _read_json(ROOT / "reports" / "p11_5" / "dataset" / "v2_build_summary.json")
    elif (ROOT / "reports" / "p11_5" / "dataset" / "v2_build_summary.json").exists():
        actions["v2_summary"] = _read_json(ROOT / "reports" / "p11_5" / "dataset" / "v2_build_summary.json")

    if args.profile:
        resolver = _load("p11_5_profile_resolver", "profile_resolver.py")
        actions["profile"] = resolver.resolve_profile(args.profile_name)

    if args.baseline:
        actions["baseline"] = collect_baselines()

    if args.temporal:
        actions["temporal"] = {
            "status": "NOT_EVALUATED",
            "reason": "No locked frame-level OCR ground-truth track is available in the frozen corpus.",
            "implementation": "tools/p11_5/temporal.py",
        }

    if hardware_requested:
        module = _load("p11_5_benchmark_hardware", "benchmark_hardware.py")
        profile_names = args.hardware_profiles
        records = [module.benchmark_profile(name.strip(), args.repeats, args.warmups, args.image_size) for name in profile_names.split(",") if name.strip()]
        actions["hardware"] = {"status": "MEASURED_OR_UNAVAILABLE", "records": records}

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "actions": actions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-audit", action="store_true")
    parser.add_argument("--build-v2", action="store_true", help="Explicitly build only empty derivative output directories")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-name", default="auto", choices=["baseline", "development", "cloud_balanced", "cloud_accuracy", "auto"])
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--temporal", action="store_true")
    parser.add_argument("--hardware", action="store_true")
    parser.add_argument("--hardware-profiles", default="baseline")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_suite(args)
    output = args.output or (ROOT / "reports" / "p11_5" / "suite" / f"suite_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output.relative_to(ROOT)).replace("\\", "/"), "actions": sorted(report["actions"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
