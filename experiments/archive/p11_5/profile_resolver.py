"""Resolve only measured P11.5 model profiles.

This module is intentionally separate from production imports. It does not
load detector or OCR models; it only selects a validated declarative profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PROFILE_CONFIG = ROOT / "experiments" / "archive" / "configs" / "p11_5" / "profiles.yaml"


def detect_hardware() -> dict[str, Any]:
    result: dict[str, Any] = {"gpu_count": 0, "gpu_name": "CPU", "vram_mb": 0, "cuda": False}
    try:
        import torch  # type: ignore

        result["cuda"] = bool(torch.cuda.is_available())
        result["gpu_count"] = int(torch.cuda.device_count())
        if result["cuda"] and result["gpu_count"]:
            result["gpu_name"] = torch.cuda.get_device_name(0)
            result["vram_mb"] = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
    except Exception as exc:
        result["probe_error"] = f"{type(exc).__name__}: {exc}"
    return result


def load_profiles(path: Path = PROFILE_CONFIG) -> dict[str, dict[str, Any]]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to resolve P11.5 profiles") from exc
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return document.get("profiles", {})


def artifacts_exist(profile: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = []
    for key in ("p1", "p3", "ocr"):
        value = profile.get(key)
        if value and not (ROOT / value).exists():
            missing.append(value)
    return not missing and all(profile.get(key) for key in ("p1", "p3", "ocr")), missing


def resolve_profile(requested: str = "auto", hardware: dict[str, Any] | None = None) -> dict[str, Any]:
    profiles = load_profiles()
    hardware = hardware or detect_hardware()
    if requested not in profiles:
        raise ValueError(f"Unknown P11.5 profile: {requested}")
    order = [requested]
    if requested == "auto":
        order = profiles["auto"].get("fallback_order", [])
    failures: list[dict[str, Any]] = []
    for name in order:
        profile = profiles.get(name, {})
        status = str(profile.get("status", ""))
        if status.startswith("unavailable") or status == "resolver_only":
            failures.append({"profile": name, "reason": status or "no_status"})
            continue
        minimum = profile.get("minimum_vram_mb")
        if minimum is not None and int(hardware.get("vram_mb", 0)) < int(minimum):
            failures.append({"profile": name, "reason": "insufficient_vram", "required_mb": minimum})
            continue
        exists, missing = artifacts_exist(profile)
        if not exists:
            failures.append({"profile": name, "reason": "missing_artifact", "paths": missing})
            continue
        return {"requested": requested, "selected": name, "profile": profile, "hardware": hardware, "fallbacks_considered": failures}
    return {"requested": requested, "selected": None, "profile": None, "hardware": hardware, "fallbacks_considered": failures, "error": "No validated profile fits the current hardware/artifacts"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="auto", choices=["baseline", "development", "cloud_balanced", "cloud_accuracy", "auto"])
    args = parser.parse_args()
    print(json.dumps(resolve_profile(args.profile), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
