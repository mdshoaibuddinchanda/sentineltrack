import sys
import json
import socket
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def check_port(port: int, host: str = "127.0.0.1") -> bool:
    """Returns True if the port is available (not bound)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0

def run_preflight() -> int:
    print("=== SentinelTrack Priority 11 Pre-Flight Check ===")
    failed = False
    warnings = False

    # 1. Python Version Check
    py_ver = sys.version_info
    print(f"Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    if py_ver < (3, 10):
        print(" [FAIL] Python 3.10+ required.")
        failed = True
    else:
        print(" [PASS] Python version compatible.")

    # 2. Check Models
    manifest_path = REPO_ROOT / "models" / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            data = json.load(f)
        for m in data.get("models", []):
            m_path = REPO_ROOT / m["file_path"]
            if m_path.exists():
                print(f" [PASS] Model '{m['logical_name']}' present ({m['size_bytes'] / 1e6:.1f} MB)")
            else:
                if m.get("required", True):
                    print(f" [FAIL] Required model '{m['logical_name']}' missing at {m['file_path']}")
                    failed = True
                else:
                    print(f" [WARN] Optional model '{m['logical_name']}' missing at {m['file_path']}")
                    warnings = True
    else:
        print(" [WARN] models/manifest.json not found.")
        warnings = True

    # 3. Check GPU / CUDA
    try:
        import torch
        if torch.cuda.is_available():
            dev_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f" [PASS] CUDA GPU Available: {dev_name} ({vram_gb:.1f} GB VRAM)")
        else:
            print(" [WARN] CUDA not available; running in CPU inference mode.")
            warnings = True
    except Exception as e:
        print(f" [WARN] PyTorch check error: {e}")
        warnings = True

    # 4. Check Database
    try:
        import importlib
        db_m = importlib.import_module("00_foundation.registry.database")
        with db_m.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        print(" [PASS] PostgreSQL database connected successfully.")
    except Exception as e:
        print(f" [WARN] PostgreSQL database not reachable: {e}")
        warnings = True


    print("==================================================")
    if failed:
        print("PREFLIGHT STATUS: FAILED (Mandatory prerequisites missing)")
        return 1
    elif warnings:
        print("PREFLIGHT STATUS: PASS WITH WARNINGS")
        return 0
    else:
        print("PREFLIGHT STATUS: ALL PASS")
        return 0

if __name__ == "__main__":
    sys.exit(run_preflight())
