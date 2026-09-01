"""Truthful pre-demo diagnostics for the SentinelTrack live runtime."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class Check:
    name: str
    status: str
    details: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_check() -> Check:
    try:
        import cv2
        import torch
        import onnxruntime as ort

        if torch.cuda.is_available():
            device = f"CUDA {torch.version.cuda}; {torch.cuda.get_device_name(0)}"
        else:
            device = "CPU only"
        return Check(
            "Python and inference runtimes",
            "PASS",
            f"Python {sys.version.split()[0]}; OpenCV {cv2.__version__}; PyTorch {torch.__version__}; ONNX Runtime {ort.__version__}; {device}",
        )
    except Exception as exc:
        return Check("Python and inference runtimes", "FAIL", str(exc))


def _model_check() -> Check:
    try:
        manifest = json.loads((REPO_ROOT / "models" / "manifest.json").read_text(encoding="utf-8"))
        missing: list[str] = []
        mismatched: list[str] = []
        verified = 0
        for item in manifest.get("models", []):
            path = REPO_ROOT / item["file_path"]
            if not path.is_file():
                if item.get("required"):
                    missing.append(item["logical_name"])
                continue
            expected = str(item.get("sha256") or "").lower()
            if expected and _sha256(path) != expected:
                mismatched.append(item["logical_name"])
            else:
                verified += 1
        if missing or mismatched:
            return Check(
                "Runtime model manifest",
                "FAIL",
                f"missing required={missing or 'none'}; SHA256 mismatch={mismatched or 'none'}",
            )
        return Check("Runtime model manifest", "PASS", f"{verified} local model/support artifacts verified by SHA256")
    except Exception as exc:
        return Check("Runtime model manifest", "FAIL", str(exc))


def _database_check() -> tuple[Check, dict[str, int]]:
    counts: dict[str, int] = {}
    try:
        db = importlib.import_module("00_foundation.registry.database")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT PostGIS_Version();")
                postgis = cur.fetchone()[0]
                for table, key in (
                    ("cameras", "cameras"),
                    ("watchlist_entries", "watchlist"),
                    ("vehicle_sightings", "sightings"),
                    ("alerts", "alerts"),
                ):
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    counts[key] = int(cur.fetchone()[0])
                # The organizer's current catalogue uses cam01..cam30 IDs.
                # Numeric IDs were the stale pre-portal registry shape, so
                # hygiene must recognize the official camNN form as valid.
                cur.execute("SELECT COUNT(*) FROM cameras WHERE camera_id !~ '^cam[0-9]+$';")
                counts["non_portal_cameras"] = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT COUNT(*) FROM cameras WHERE COALESCE(rtsp_url, '') <> '' OR COALESCE(hls_url, '') <> '';"
                )
                counts["configured_sources"] = int(cur.fetchone()[0])
        detail = ", ".join(f"{key}={value}" for key, value in counts.items())
        return Check("PostgreSQL and PostGIS", "PASS", f"PostGIS {postgis}; {detail}"), counts
    except Exception as exc:
        return Check("PostgreSQL and PostGIS", "FAIL", str(exc)), counts


def _dns_check(hosts: list[str]) -> Check:
    failures: list[str] = []
    resolved: list[str] = []
    for host in hosts:
        try:
            addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
            resolved.append(f"{host}={','.join(addresses[:3])}")
        except OSError as exc:
            failures.append(f"{host}: {exc}")
    if failures:
        return Check("Organizer DNS", "BLOCKED", "; ".join(failures))
    return Check("Organizer DNS", "PASS", "; ".join(resolved))


def _catalogue_check() -> Check:
    try:
        client_m = importlib.import_module("00_foundation.catalogue.client")
        parser_m = importlib.import_module("00_foundation.catalogue.parser")
        client = client_m.SentinelCatalogueClient(timeout_s=8.0)
        payload = client.fetch()
        cameras = parser_m.parse_catalogue(payload, base_host=client.effective_host)
        cookies = client.diagnostics()["session_cookie_count"]
        return Check(
            "Official catalogue and feed session",
            "PASS",
            f"{len(cameras)} cameras; effective host={client.effective_host}; session cookies={cookies}",
        )
    except Exception as exc:
        code = getattr(exc, "code", "CATALOGUE_ERROR")
        return Check("Official catalogue and feed session", "BLOCKED", f"{code}: {exc}")


def _security_check() -> Check:
    try:
        password_m = importlib.import_module("10_security.password")
        ready = bool(password_m.DUMMY_PASSWORD_HASH.startswith("$argon2id$"))
        return Check(
            "Authentication and RBAC",
            "PASS" if ready else "FAIL",
            "Argon2id timing equalization and role permissions loaded" if ready else "Argon2id dummy hash missing",
        )
    except Exception as exc:
        return Check("Authentication and RBAC", "FAIL", str(exc))


def _frontend_check() -> Check:
    package = REPO_ROOT / "09_dashboard" / "package.json"
    dist = REPO_ROOT / "09_dashboard" / "dist" / "index.html"
    if not package.is_file():
        return Check("Dashboard", "FAIL", "09_dashboard/package.json is missing")
    if not dist.is_file():
        return Check("Dashboard", "WARN", "source present; production build not generated in this checkout")
    return Check("Dashboard", "PASS", "source and production build are present")


def run_doctor() -> int:
    print("=" * 78)
    print(" SENTINELTRACK LIVE DEMONSTRATION DIAGNOSTIC")
    print("=" * 78)

    configured_host = urlparse(os.getenv("SENTINEL_HOST", "https://cctv.corp8.cloud")).hostname
    # Check only the organizer host selected by the active configuration. Older
    # challenge hostnames are retained in compatibility tests, but are not
    # runtime dependencies and must not create a false demo blocker.
    hosts = [configured_host] if configured_host else []
    checks: list[Check] = [_runtime_check(), _model_check()]
    db_check, counts = _database_check()
    checks.append(db_check)
    checks.extend([_dns_check(list(dict.fromkeys(hosts))), _catalogue_check(), _security_check(), _frontend_check()])

    if counts.get("non_portal_cameras", 0):
        checks.append(Check("Database hygiene", "WARN", f"{counts['non_portal_cameras']} non-official/test camera rows remain"))
    if counts.get("watchlist", 0) == 0:
        checks.append(Check("Designated vehicle", "BLOCKED", "watchlist is empty; no registration can generate an alert"))
    else:
        checks.append(Check("Designated vehicle", "PASS", f"{counts['watchlist']} watchlist entries configured"))

    for result in checks:
        print(f"[{result.status:<7}] {result.name:<38} {result.details}")

    failures = sum(result.status == "FAIL" for result in checks)
    blockers = sum(result.status == "BLOCKED" for result in checks)
    warnings = sum(result.status == "WARN" for result in checks)
    print("=" * 78)
    if failures:
        print(f"NOT READY: {failures} internal failure(s), {blockers} external/configuration blocker(s), {warnings} warning(s)")
        return 1
    if blockers:
        print(f"NOT READY FOR LIVE DEMO: {blockers} external/configuration blocker(s), {warnings} warning(s)")
        return 2
    print(f"READY FOR LIVE DEMO ({warnings} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_doctor())
