"""Measured P11.5 hardware probes with explicit unavailable states.

This tool is deliberately separate from the API and does not run during an
API import.  It measures an existing detector artifact only when requested;
cloud profiles without artifacts remain unavailable rather than estimated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def _hardware() -> dict[str, Any]:
    data: dict[str, Any] = {"os": platform.platform(), "cpu": platform.processor() or platform.machine(), "logical_cpus": None, "ram_bytes": None}
    try:
        import psutil  # type: ignore

        data["logical_cpus"] = psutil.cpu_count(logical=True)
        data["ram_bytes"] = int(psutil.virtual_memory().total)
    except Exception as exc:
        data["probe_warning"] = f"psutil unavailable: {type(exc).__name__}"
    try:
        import torch  # type: ignore

        data["cuda_available"] = bool(torch.cuda.is_available())
        data["gpu_count"] = int(torch.cuda.device_count())
        if data["cuda_available"] and data["gpu_count"]:
            data["gpu_name"] = torch.cuda.get_device_name(0)
            data["vram_bytes"] = int(torch.cuda.get_device_properties(0).total_memory)
            data["compute_capability"] = list(torch.cuda.get_device_capability(0))
        else:
            data["gpu_name"] = "CPU"
            data["vram_bytes"] = 0
    except Exception as exc:
        data["cuda_available"] = False
        data["gpu_count"] = 0
        data["gpu_name"] = "CPU"
        data["vram_bytes"] = 0
        data["probe_warning"] = f"torch probe failed: {type(exc).__name__}: {exc}"
    fingerprint = json.dumps({"cpu": data.get("cpu"), "gpu": data.get("gpu_name"), "vram": data.get("vram_bytes")}, sort_keys=True)
    data["hardware_id"] = "local-" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _measure_detector(model_path: Path, repeats: int, warmups: int, image_size: int) -> dict[str, Any]:
    import numpy as np  # type: ignore
    import torch  # type: ignore

    from ultralytics import YOLO  # type: ignore

    device: Any = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(str(model_path))
    frame = np.zeros((image_size, image_size, 3), dtype=np.uint8)
    for _ in range(max(0, warmups)):
        model.predict(frame, imgsz=image_size, device=device, verbose=False)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    durations: list[float] = []
    for _ in range(max(1, repeats)):
        start = time.perf_counter()
        model.predict(frame, imgsz=image_size, device=device, verbose=False)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        durations.append((time.perf_counter() - start) * 1000.0)
    return {
        "status": "MEASURED",
        "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        "model_sha256": _sha256(model_path),
        "precision": "fp32",
        "batch": 1,
        "image_size": image_size,
        "device": "cuda:0" if torch.cuda.is_available() else "cpu",
        "repeats": len(durations),
        "warmups": max(0, warmups),
        "latency_p50_ms": round(statistics.median(durations), 3),
        "latency_p95_ms": round(sorted(durations)[max(0, min(len(durations) - 1, math.ceil(len(durations) * 0.95) - 1))], 3),
        "throughput_fps": round(1000.0 / statistics.mean(durations), 3),
        "safe_camera_capacity": None,
        "safe_camera_capacity_reason": "Not inferred from a synthetic single-frame probe; validate with the intended stream mix.",
    }


def benchmark_profile(profile_name: str, repeats: int, warmups: int, image_size: int) -> dict[str, Any]:
    from profile_resolver import load_profiles, resolve_profile  # type: ignore

    hardware = _hardware()
    resolved = resolve_profile(profile_name, hardware)
    result: dict[str, Any] = {"profile_requested": profile_name, "hardware": hardware, "resolved": resolved}
    selected = resolved.get("selected")
    if not selected:
        result.update({"status": "UNAVAILABLE", "reason": resolved.get("error", "No validated profile")})
        return result
    profile = load_profiles().get(selected, {})
    model_value = profile.get("p3")
    if not model_value:
        result.update({"status": "UNAVAILABLE", "reason": "Profile has no detector artifact"})
        return result
    model_path = ROOT / model_value
    try:
        result.update(_measure_detector(model_path, repeats, warmups, image_size))
    except Exception as exc:
        result.update({"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "model": model_value})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="baseline")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    records = [benchmark_profile(item.strip(), args.repeats, args.warmups, args.image_size) for item in args.profiles.split(",") if item.strip()]
    report = {"schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "records": records}
    output = args.output or (ROOT / "reports" / "p11_5" / "profiles" / f"hardware_benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output.relative_to(ROOT)).replace("\\", "/"), "record_statuses": [item.get("status") for item in records]}, indent=2))
    return 0 if all(item.get("status") in {"MEASURED", "UNAVAILABLE"} for item in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
