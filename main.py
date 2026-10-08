"""SentinelTrack root launcher.

The default mode is the normal configured SentinelTrack runtime:
- uses the configured PostgreSQL/PostGIS database and account
- starts the analytics worker and persisted camera sources
- starts the Vite dashboard and opens the browser automatically

Use --frontend-only when the API is already running.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import TextIO


ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "09_dashboard"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_UI_URL = "http://127.0.0.1:5173"
LOG_DIR = ROOT / "logs"
_LOG_HANDLES: list[TextIO] = []


def load_project_environment() -> None:
    """Load the repository .env before child processes are created."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        # The backend also loads dotenv when available; the launcher should
        # remain usable for frontend-only review if the optional helper is absent.
        pass


def open_log(name: str) -> TextIO:
    """Open an append-only launcher log under the repository logs directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOG_DIR / name, "a", encoding="utf-8", buffering=1)
    _LOG_HANDLES.append(handle)
    return handle


def close_logs() -> None:
    for handle in _LOG_HANDLES:
        try:
            handle.close()
        except Exception:
            pass
    _LOG_HANDLES.clear()


def configure_backend_logging() -> None:
    """Write backend and model diagnostics to the repository logs directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_DIR / "sentineltrack.log", encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[file_handler, stream_handler],
        force=True,
    )


def command(name: str) -> str:
    """Resolve Windows/POSIX executable names consistently."""
    if os.name == "nt" and name == "npm":
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which(name) or name


def wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def assert_port_available(host: str, port: int, label: str) -> None:
    """Fail early instead of accidentally attaching the UI to a stale service."""
    try:
        with socket.create_connection((host, port), timeout=0.25):
            raise RuntimeError(
                f"{label} port {port} is already in use. Stop the existing service or choose another port."
            )
    except RuntimeError:
        raise
    except OSError:
        return


def wait_for_http(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            time.sleep(0.35)
    return False


def startup_timeout_seconds() -> float:
    """Allow bounded catalogue retries without the parent killing a healthy startup."""
    try:
        configured = float(os.getenv("SENTINEL_STARTUP_TIMEOUT", "90"))
    except ValueError:
        configured = 90.0
    return min(180.0, max(35.0, configured))


def ensure_frontend_dependencies() -> None:
    if not DASHBOARD.is_dir():
        raise RuntimeError(f"Dashboard directory missing: {DASHBOARD}")
    if (DASHBOARD / "node_modules").is_dir():
        return
    print("[setup] Installing dashboard dependencies with npm ci...")
    subprocess.run([command("npm"), "ci"], cwd=DASHBOARD, check=True)


def configure_frontend_origin(ui_port: int, *, preserve_existing: bool) -> None:
    """Make the child API accept the exact origin served by Vite."""
    required = [f"http://localhost:{ui_port}", f"http://127.0.0.1:{ui_port}"]
    if preserve_existing:
        origins = [
            origin.strip()
            for origin in os.getenv("SENTINEL_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]
        for origin in required:
            if origin not in origins:
                origins.append(origin)
    else:
        origins = required
    os.environ["SENTINEL_ALLOWED_ORIGINS"] = ",".join(origins)


def run_backend_child(args: argparse.Namespace) -> int:
    os.chdir(ROOT)
    configure_backend_logging()

    os.environ.setdefault("SENTINEL_ENV", "development")
    os.environ["SENTINEL_PROCESS_ROLE"] = "all"
    os.environ["SENTINEL_SECURITY_USE_SQLITE"] = "false"
    configure_frontend_origin(args.ui_port, preserve_existing=True)

    import uvicorn

    app = importlib.import_module("08_backend.app").app
    uvicorn.run(
        app,
        host=args.host,
        port=args.api_port,
        log_level="info",
        log_config=None,
        reload=False,
    )
    return 0


def start_frontend(*, ui_port: int, api_port: int) -> subprocess.Popen:
    ensure_frontend_dependencies()
    env = os.environ.copy()
    # These must follow the launcher CLI port, otherwise a custom API port
    # silently leaves the browser pointed at a different backend.
    env["VITE_SENTINEL_API_URL"] = f"http://127.0.0.1:{api_port}"
    env["VITE_SENTINEL_WS_URL"] = f"ws://127.0.0.1:{api_port}"

    print(f"[frontend] Starting Vite on http://127.0.0.1:{ui_port}")
    return subprocess.Popen(
        [
            command("npm"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(ui_port),
        ],
        cwd=DASHBOARD,
        env=env,
        stdout=open_log("launcher.frontend.stdout.log"),
        stderr=open_log("launcher.frontend.stderr.log"),
    )


def start_backend(
    *,
    host: str,
    api_port: int,
    ui_port: int,
) -> subprocess.Popen:
    cmd = [
        sys.executable,
        str(ROOT / "main.py"),
        "--backend-child",
        "--host",
        host,
        "--api-port",
        str(api_port),
        "--ui-port",
        str(ui_port),
    ]
    print(f"[backend] Starting API on http://127.0.0.1:{api_port}")
    return subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=open_log("launcher.backend.stdout.log"),
        stderr=open_log("launcher.backend.stderr.log"),
    )


def maybe_start_postgres() -> None:
    docker = shutil.which("docker")
    if not docker:
        print("[full] Docker not found; assuming PostgreSQL is already available.")
        return
    print("[full] Starting PostgreSQL/PostGIS with docker compose...")
    subprocess.run(
        [docker, "compose", "up", "-d", "postgres"],
        cwd=ROOT,
        check=False,
    )


def initialize_database_schema() -> None:
    """Apply idempotent production schemas; this never inserts sample data."""
    print("[full] Applying idempotent SentinelTrack database schemas...")
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "init_schema.py")],
        cwd=ROOT,
        env=os.environ.copy(),
        check=True,
    )


def terminate(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch SentinelTrack backend and dashboard from the repository root."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="Start the normal backend analytics role plus frontend (default).")
    mode.add_argument(
        "--frontend-only",
        action="store_true",
        help="Start only the React/Vite dashboard.",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=5173)

    # Internal child-process flag retained for supervisor compatibility.
    parser.add_argument("--backend-child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_project_environment()
    args = parse_args(argv)

    if args.backend_child:
        return run_backend_child(args)

    os.chdir(ROOT)
    full = not args.frontend_only
    backend: subprocess.Popen | None = None
    frontend: subprocess.Popen | None = None
    feed_credentials_configured = False

    try:
        if not args.frontend_only:
            assert_port_available("127.0.0.1", args.api_port, "API")
        assert_port_available("127.0.0.1", args.ui_port, "dashboard")

        if full:
            maybe_start_postgres()
            initialize_database_schema()
            os.environ["SENTINEL_ENABLE_STREAM_INGESTION"] = "true"
            missing_feed_settings = [
                name
                for name in ("SENTINEL_ACCESS_EMAIL", "SENTINEL_ACCESS_PASSWORD")
                if not os.getenv(name, "").strip()
            ]
            feed_credentials_configured = not missing_feed_settings
            if missing_feed_settings:
                print(
                    "[attention] Required organizer setting(s) missing: "
                    + ", ".join(missing_feed_settings)
                    + ". "
                    "The protected official feeds will be shown as Access required."
                )

        if not args.frontend_only:
            backend = start_backend(
                host=args.host,
                api_port=args.api_port,
                ui_port=args.ui_port,
            )
            if not wait_for_http(
                f"http://127.0.0.1:{args.api_port}/health",
                timeout=startup_timeout_seconds(),
            ):
                raise RuntimeError("Backend did not become ready on time.")

        frontend = start_frontend(ui_port=args.ui_port, api_port=args.api_port)
        if not wait_for_port("127.0.0.1", args.ui_port, timeout=35.0):
            raise RuntimeError("Frontend did not become ready on time.")

        ui_url = f"http://127.0.0.1:{args.ui_port}"
        print()
        print("=" * 68)
        print(" SENTINELTRACK APPLICATION STARTED")
        print("=" * 68)
        print(f" Dashboard : {ui_url}")
        if not args.frontend_only:
            print(f" API       : http://127.0.0.1:{args.api_port}")
        if full:
            print(" Mode      : full analytics/backend runtime")
            print(" Login     : use your configured SentinelTrack operator/admin account")
            print(
                " Feed      : "
                + (
                    "credentials configured; verify decoded frames in Cameras/System status"
                    if feed_credentials_configured
                    else "BLOCKED - organizer email and password required"
                )
            )
        else:
            print(" Mode      : frontend only")
        print("=" * 68)
        print("Press Ctrl+C here to stop services.")
        print()

        if not args.no_browser:
            webbrowser.open(ui_url)

        while True:
            if frontend.poll() is not None:
                return int(frontend.returncode or 0)
            if backend is not None and backend.poll() is not None:
                return int(backend.returncode or 1)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[shutdown] Stopping SentinelTrack...")
        return 0
    except Exception as exc:
        print(f"\n[error] {exc}", file=sys.stderr)
        return 1
    finally:
        terminate(frontend)
        terminate(backend)
        close_logs()


if __name__ == "__main__":
    raise SystemExit(main())
