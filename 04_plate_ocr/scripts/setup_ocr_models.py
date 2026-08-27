import os
import sys
import hashlib
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / 'models' / 'ocr'

# Authoritative model resources with pinned expected SHA-256 checksums
MODEL_RESOURCES = [
    {
        'name': 'en_PP-OCRv5_mobile_rec (ONNX)',
        'identity': 'en_PP-OCRv5_mobile_rec',
        'url': 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/english/rec.onnx',
        'dest': MODELS_DIR / 'PP-OCRv5_mobile_rec_infer.onnx',
        'expected_sha256': '4e16deb22c4da6468bdca539b2cd3c8687825538b67109177c47d359ab994cd7',
        'min_size_bytes': 5 * 1024 * 1024,
    },
    {
        'name': 'en_PP-OCRv5_mobile Dictionary',
        'identity': 'en_ppocr_mobile_dict',
        'url': 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/english/dict.txt',
        'dest': MODELS_DIR / 'ppocr_mobile_dict.txt',
        'expected_sha256': 'e025a66d31f327ba0c232e03f407ae8d105e1e709e7ccb3f408aa778c24e70d6',
        'min_size_bytes': 50,
    },
    {
        'name': 'PP-OCRv5_server_rec (ONNX)',
        'identity': 'PP-OCRv5_server_rec',
        'url': 'https://huggingface.co/bluecopa/paddleocr-v5-onnx/resolve/main/PP-OCRv5_server_rec_infer.onnx',
        'dest': MODELS_DIR / 'PP-OCRv5_server_rec_infer.onnx',
        'expected_sha256': '13d0dda27d63dc0f4938af48df2c55b33f3c989a0bd5eacb8410e30f1735f644',
        'min_size_bytes': 50 * 1024 * 1024,
    },
    {
        'name': 'PP-OCRv5_server Dictionary',
        'identity': 'ppocrv5_dict',
        'url': 'https://huggingface.co/bluecopa/paddleocr-v5-onnx/resolve/main/ppocrv5_dict.txt',
        'dest': MODELS_DIR / 'ppocrv5_dict.txt',
        'expected_sha256': 'd1979e9f794c464c0d2e0b70a7fe14dd978e9dc644c0e71f14158cdf8342af1b',
        'min_size_bytes': 1000,
    }
]


def compute_file_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def verify_file_integrity(file_path: Path, expected_sha256: str) -> bool:
    """Verifies that a file exists and matches its expected SHA-256 hash."""
    if not file_path.exists():
        return False
    actual_sha = compute_file_sha256(file_path)
    if actual_sha != expected_sha256:
        raise ValueError(
            f'SHA-256 checksum mismatch for {file_path.name}!\n'
            f'  Expected: {expected_sha256}\n'
            f'  Actual:   {actual_sha}'
        )
    return True


def setup_ocr_models(force: bool = False) -> bool:
    """
    Downloads and verifies all Priority 4 OCR recognition models and dictionaries.
    Fails with ValueError if SHA-256 verification fails.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print('================ SENTINELTRACK OCR MODEL SETUP ================')
    print(f'Destination Directory: {MODELS_DIR}')

    for item in MODEL_RESOURCES:
        dest_path = item['dest']
        name = item['name']
        url = item['url']
        expected_sha = item['expected_sha256']

        if dest_path.exists() and not force:
            try:
                verify_file_integrity(dest_path, expected_sha)
                sz = dest_path.stat().st_size
                print(f'  [VERIFIED] {name:<35} | Size: {sz / 1024 / 1024:>6.2f} MB | SHA: {expected_sha[:12]}... (OK)')
                continue
            except ValueError as e:
                print(f'  [CORRUPTED] {e}. Re-downloading...')

        print(f'  [DOWNLOADING] {name} from {url}...')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, 'wb') as out_f:
            while chunk := resp.read(65536):
                out_f.write(chunk)

        verify_file_integrity(dest_path, expected_sha)
        sz = dest_path.stat().st_size
        print(f'  [SUCCESS]  {name:<35} | Size: {sz / 1024 / 1024:>6.2f} MB | SHA: {expected_sha[:12]}... (MATCH)')

    print('===============================================================')
    return True


if __name__ == '__main__':
    force_download = '--force' in sys.argv
    try:
        setup_ocr_models(force=force_download)
    except Exception as e:
        print(f'[ERROR] Model setup failed: {e}', file=sys.stderr)
        sys.exit(1)
