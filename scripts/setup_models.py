import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MANIFEST_PATH = ROOT_DIR / "models" / "manifest.json"
VEHICLE_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Operational model manifest not found: {MANIFEST_PATH}")
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("manifest_type") != "operational_runtime_models":
        raise ValueError("models/manifest.json is not an operational runtime manifest")
    return manifest


def manifest_entry(manifest: dict, logical_name: str) -> dict:
    for item in manifest.get("models", []):
        if item.get("logical_name") == logical_name:
            return item
    raise KeyError(f"Manifest entry not found: {logical_name}")


def verify_entry(entry: dict, *, required_override: bool | None = None) -> bool:
    path = ROOT_DIR / entry["file_path"]
    required = entry.get("required", False) if required_override is None else required_override
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required runtime model is missing: {path}")
        print(f"[WARN] Optional model is missing: {path}")
        return False
    actual = sha256_file(path)
    expected = entry.get("sha256", "").lower()
    if expected and actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected}, got {actual}")
    expected_size = entry.get("size_bytes")
    if expected_size and path.stat().st_size != expected_size:
        raise ValueError(f"Size mismatch for {path}: expected {expected_size}, got {path.stat().st_size}")
    print(f"[OK] {entry['logical_name']}: {path} ({path.stat().st_size:,} bytes, {actual[:12]}...)")
    return True


def download_verified(url: str, destination: Path, entry: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    request = urllib.request.Request(url, headers={"User-Agent": "SentinelTrack model setup"})
    print(f"[SETUP] Downloading {entry['logical_name']} from {url}")
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = sha256_file(temporary)
        expected = entry.get("sha256", "").lower()
        if expected and actual != expected:
            raise ValueError(f"SHA-256 mismatch for downloaded {entry['logical_name']}: expected {expected}, got {actual}")
        expected_size = entry.get("size_bytes")
        if expected_size and temporary.stat().st_size != expected_size:
            raise ValueError(f"Size mismatch for downloaded {entry['logical_name']}: expected {expected_size}, got {temporary.stat().st_size}")
        temporary.replace(destination)
        verify_entry(entry, required_override=True)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_ocr_models(*, include_server: bool = False) -> bool:
    """Use the P4 setup helper while keeping server OCR explicitly optional."""
    ocr_setup = ROOT_DIR / "04_plate_ocr" / "scripts" / "setup_ocr_models.py"
    if not ocr_setup.exists():
        raise FileNotFoundError(f"OCR setup helper not found: {ocr_setup}")
    import importlib.util

    spec = importlib.util.spec_from_file_location("sentineltrack_ocr_setup", ocr_setup)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load OCR setup helper: {ocr_setup}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return bool(module.setup_ocr_models(include_server=include_server))


def setup_models(*, verify_only: bool = False, include_server_ocr: bool = False) -> bool:
    print("[SETUP] Setting up canonical SentinelTrack runtime models...")
    manifest = load_manifest()
    for directory in (ROOT_DIR / "models" / "vehicle", ROOT_DIR / "models" / "plate", ROOT_DIR / "models" / "ocr", ROOT_DIR / "models" / "reid"):
        directory.mkdir(parents=True, exist_ok=True)

    vehicle = manifest_entry(manifest, "vehicle_detector")
    vehicle_path = ROOT_DIR / vehicle["file_path"]
    if not vehicle_path.exists():
        if verify_only:
            raise FileNotFoundError(f"Required runtime model is missing: {vehicle_path}")
        download_verified(VEHICLE_MODEL_URL, vehicle_path, vehicle)
    verify_entry(vehicle, required_override=True)

    if not verify_only:
        verify_ocr_models(include_server=include_server_ocr)
    verify_entry(manifest_entry(manifest, "ocr_recognizer_mobile"), required_override=True)
    verify_entry(manifest_entry(manifest, "ocr_mobile_dictionary"), required_override=True)

    # Project-trained artifacts cannot be downloaded from a public URL. Report
    # them explicitly so setup never silently falls back to a different model.
    plate = manifest_entry(manifest, "plate_detector")
    verify_entry(plate, required_override=True)
    reid = manifest_entry(manifest, "vehicle_appearance_reid_fallback")
    verify_entry(reid, required_override=False)

    if include_server_ocr:
        print("[INFO] Server OCR remains optional; run the P4 helper with --include-server if needed.")
    print("[SUCCESS] Canonical model verification completed.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install or verify SentinelTrack canonical runtime models")
    parser.add_argument("--verify-only", action="store_true", help="Do not download public models")
    parser.add_argument("--include-server-ocr", action="store_true", help="Document optional server OCR without making it required")
    args = parser.parse_args()
    try:
        setup_models(verify_only=args.verify_only, include_server_ocr=args.include_server_ocr)
    except Exception as exc:
        print(f"[ERROR] Model setup failed: {exc}", file=sys.stderr)
        sys.exit(1)

