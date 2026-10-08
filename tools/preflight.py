"""Validate the packaged SentinelTrack runtime before starting services.

The operational source of truth is ``models/manifest.json``. Missing optional
models produce warnings; missing or corrupted required models fail the check.
Database connectivity is bounded so a stopped local database cannot hang the
preflight command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "models" / "manifest.json"
REQUIRED_DIRECTORIES = ("configs", "models", "reports", "scripts", "tools")

# Preflight must inspect the same local configuration used by the launcher.
# Without this, a shell that has not exported DATABASE_PASSWORD would probe
# with the fallback password and report a misleading authentication warning.
load_dotenv(ROOT_DIR / ".env")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_database(timeout_seconds: float = 2.0) -> tuple[bool, str]:
    host = os.getenv("DATABASE_HOST", "localhost")
    port = int(os.getenv("DATABASE_PORT", "5432"))
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            pass
    except OSError as exc:
        return False, f"database socket unavailable: {exc}"

    try:
        import psycopg

        password = os.getenv("DATABASE_PASSWORD", "sentinel_password")
        with psycopg.connect(
            host=host,
            port=port,
            dbname=os.getenv("DATABASE_NAME", "sentinel"),
            user=os.getenv("DATABASE_USER", "sentinel"),
            password=password,
            connect_timeout=max(1, int(timeout_seconds)),
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True, "PostgreSQL query succeeded"
    except Exception as exc:  # pragma: no cover - depends on local service
        return False, f"database authentication/query failed: {exc}"


def run_preflight(*, strict_database: bool = False) -> int:
    print("=== SentinelTrack Runtime Preflight ===")
    failed = False
    warnings = False

    version = sys.version_info
    print(f"Python: {version.major}.{version.minor}.{version.micro}")
    if version < (3, 10):
        print("[FAIL] Python 3.10+ is required")
        failed = True
    else:
        print("[PASS] Python version compatible")

    for directory in REQUIRED_DIRECTORIES:
        path = ROOT_DIR / directory
        if path.is_dir():
            print(f"[PASS] Required directory: {directory}/")
        else:
            print(f"[FAIL] Required directory missing: {directory}/")
            failed = True

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        entries = manifest.get("models", [])
        if manifest.get("manifest_type") != "operational_runtime_models":
            print("[FAIL] models/manifest.json is not the operational runtime manifest")
            failed = True
        for entry in entries:
            path = ROOT_DIR / entry["file_path"]
            label = entry.get("logical_name", entry["file_path"])
            required = bool(entry.get("required", True))
            if not path.is_file():
                prefix = "FAIL" if required else "WARN"
                print(f"[{prefix}] {label}: missing at {entry['file_path']}")
                failed |= required
                warnings |= not required
                continue
            actual_size = path.stat().st_size
            actual_hash = sha256_file(path)
            expected_size = entry.get("size_bytes")
            expected_hash = str(entry.get("sha256", "")).lower()
            if expected_size and actual_size != expected_size:
                print(f"[FAIL] {label}: size mismatch ({actual_size} != {expected_size})")
                failed = True
                continue
            if expected_hash and actual_hash != expected_hash:
                print(f"[FAIL] {label}: SHA256 mismatch ({actual_hash})")
                failed = True
                continue
            print(f"[PASS] {label}: present and SHA256 verified")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"[FAIL] Operational model manifest invalid: {exc}")
        failed = True

    try:
        import torch

        if torch.cuda.is_available():
            print(f"[PASS] CUDA: {torch.cuda.get_device_name(0)}")
        else:
            print("[WARN] CUDA unavailable; CPU inference only")
            warnings = True
    except Exception as exc:  # pragma: no cover - import depends on environment
        print(f"[WARN] CUDA check unavailable: {exc}")
        warnings = True

    db_ok, db_message = check_database()
    if db_ok:
        print(f"[PASS] Database: {db_message}")
    else:
        print(f"[WARN] Database: {db_message}")
        warnings = True
        if strict_database:
            failed = True

    print("==========================================")
    if failed:
        print("PREFLIGHT STATUS: FAILED")
        return 1
    if warnings:
        print("PREFLIGHT STATUS: PASS WITH WARNINGS")
    else:
        print("PREFLIGHT STATUS: ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-database",
        action="store_true",
        help="Treat unavailable PostgreSQL as a failure instead of a warning.",
    )
    args = parser.parse_args(argv)
    return run_preflight(strict_database=args.strict_database)


if __name__ == "__main__":
    raise SystemExit(main())
