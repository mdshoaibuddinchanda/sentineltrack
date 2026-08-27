import os
import sys
import hashlib
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / 'models' / 'ocr'

# Official model definitions and URLs
MODEL_RESOURCES = [
    {
        'name': 'PP-OCRv5 Mobile Recognizer ONNX',
        'url': 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/english/rec.onnx',
        'dest': MODELS_DIR / 'PP-OCRv5_mobile_rec_infer.onnx',
        'min_size_bytes': 5 * 1024 * 1024,
    },
    {
        'name': 'PP-OCRv5 Mobile Dictionary',
        'url': 'https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/english/dict.txt',
        'dest': MODELS_DIR / 'ppocr_mobile_dict.txt',
        'min_size_bytes': 100,
    },
    {
        'name': 'PP-OCRv5 Server Recognizer ONNX',
        'url': 'https://huggingface.co/bluecopa/paddleocr-v5-onnx/resolve/main/PP-OCRv5_server_rec_infer.onnx',
        'dest': MODELS_DIR / 'PP-OCRv5_server_rec_infer.onnx',
        'min_size_bytes': 50 * 1024 * 1024,
    },
    {
        'name': 'PP-OCRv5 Server Dictionary',
        'url': 'https://huggingface.co/bluecopa/paddleocr-v5-onnx/resolve/main/ppocrv5_dict.txt',
        'dest': MODELS_DIR / 'ppocrv5_dict.txt',
        'min_size_bytes': 1000,
    }
]


def compute_file_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def setup_ocr_models(force: bool = False) -> bool:
    """
    Downloads and verifies all Priority 4 OCR recognition models and dictionaries.
    Returns True if all models are present and valid.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print('================ SENTINELTRACK OCR MODEL SETUP ================')
    print(f'Destination Directory: {MODELS_DIR}')

    all_ok = True
    for item in MODEL_RESOURCES:
        dest_path = item['dest']
        name = item['name']
        url = item['url']
        min_sz = item['min_size_bytes']

        if dest_path.exists() and not force:
            sz = dest_path.stat().st_size
            if sz >= min_sz:
                sha = compute_file_sha256(dest_path)
                print(f'  [EXISTS] {name:<32} | Size: {sz / 1024 / 1024:>6.2f} MB | SHA-256: {sha[:12]}...')
                continue

        print(f'  [DOWNLOADING] {name} from {url}...')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, 'wb') as out_f:
                while chunk := resp.read(65536):
                    out_f.write(chunk)

            sz = dest_path.stat().st_size
            sha = compute_file_sha256(dest_path)
            print(f'  [SUCCESS] {name:<32} | Size: {sz / 1024 / 1024:>6.2f} MB | SHA-256: {sha[:12]}...')

        except Exception as e:
            print(f'  [FAILED] Could not download {name}: {e}')
            all_ok = False

    print('===============================================================')
    return all_ok


if __name__ == '__main__':
    force_download = '--force' in sys.argv
    success = setup_ocr_models(force=force_download)
    if not success:
        sys.exit(1)
