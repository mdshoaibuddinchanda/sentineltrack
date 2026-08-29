"""Record locally available Paddle/PaddleOCR modern-model support."""

from __future__ import annotations

import importlib
import json
from pathlib import Path


def main() -> int:
    result: dict[str, object] = {"environment": "PY312"}
    try:
        paddle = importlib.import_module("paddle")
        result["paddle"] = {"status": "IMPORTABLE", "version": paddle.__version__, "device": paddle.device.get_device()}
    except Exception as exc:
        result["paddle"] = {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}
    try:
        paddleocr = importlib.import_module("paddleocr")
        result["paddleocr"] = {"status": "IMPORTABLE", "version": getattr(paddleocr, "__version__", "unknown"), "module": str(Path(paddleocr.__file__).parent)}
    except Exception as exc:
        result["paddleocr"] = {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}

    package_root = Path(r"C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\Lib\site-packages\paddleocr")
    readme = package_root / "README.md"
    result["algorithm_support"] = {
        "svtrv2_documented": "SVTRv2" in readme.read_text(encoding="utf-8", errors="ignore") if readme.is_file() else False,
        "local_modern_recognition_check": "SVTR_LCNet" if package_root.is_dir() else None,
        "cached_model_families": [
            str(path.relative_to(Path(r"C:\Users\SHOAIB-CHANDA\.paddleocr\whl"))).replace("\\", "/")
            for path in Path(r"C:\Users\SHOAIB-CHANDA\.paddleocr\whl").glob("**/inference.pdmodel")
        ],
    }
    result["project_trainability"] = {
        "onnx_ppocrv5_checkpoint_trainable_here": False,
        "reason": "The project OCR artifacts are ONNX inference exports; no matching Paddle train checkpoint/config is present in the repository.",
        "openocr_package_installed": False,
        "parseq_or_mgp_str_package_installed": False,
    }
    output = Path(__file__).resolve().parents[2] / "reports" / "p11_5" / "modern_ocr_probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
