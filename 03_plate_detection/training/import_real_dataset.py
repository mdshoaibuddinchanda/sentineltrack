import os
import json
import shutil
import hashlib
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
REAL_SRC_DIR = DATASET_DIR / 'sources' / 'real_public'
ROBOFLOW_SRC_DIR = ROOT_DIR / 'datasets' / 'Indian plates'


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def ingest_downloaded_indian_plates():
    print('[INGEST] Importing real Indian license plate dataset from local Roboflow export...')
    if not ROBOFLOW_SRC_DIR.exists():
        raise FileNotFoundError(f'Directory {ROBOFLOW_SRC_DIR} not found.')

    for split in ['train', 'val', 'test']:
        (REAL_SRC_DIR / split).mkdir(parents=True, exist_ok=True)

    meta_records = []
    split_map = {'train': 'train', 'valid': 'val', 'test': 'test'}

    total_copied = 0
    for rf_split, canon_split in split_map.items():
        src_img_dir = ROBOFLOW_SRC_DIR / rf_split / 'images'
        src_lbl_dir = ROBOFLOW_SRC_DIR / rf_split / 'labels'
        dest_split_dir = REAL_SRC_DIR / canon_split

        img_files = sorted(list(src_img_dir.glob('*.jpg')) + list(src_img_dir.glob('*.png')))
        print(f'[INGEST] Processing {len(img_files)} images from {rf_split} -> {canon_split}...')

        for img_p in img_files:
            lbl_p = src_lbl_dir / img_p.with_suffix('.txt').name
            if not lbl_p.exists():
                continue

            dest_img = dest_split_dir / img_p.name
            dest_lbl = dest_split_dir / lbl_p.name

            shutil.copy2(str(img_p), str(dest_img))
            shutil.copy2(str(lbl_p), str(dest_lbl))

            img_hash = compute_sha256(dest_img)

            meta_records.append({
                'image': img_p.name,
                'source_name': 'roboflow_quobotic_indian_number_plate_v3',
                'source_url': 'https://universe.roboflow.com/quobotic/indian-number-plate/dataset/3',
                'license': 'CC-BY-4.0',
                'download_date': '2024-11-25',
                'type': 'real',
                'split': canon_split,
                'sha256': img_hash,
            })
            total_copied += 1

    metadata_path = REAL_SRC_DIR / 'metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(meta_records, f, indent=2)

    print(f'[SUCCESS] Ingested {total_copied} genuine real Indian license plate images into {REAL_SRC_DIR}')
    print(f'[PROVENANCE] Written metadata to {metadata_path}')
    return total_copied


if __name__ == '__main__':
    ingest_downloaded_indian_plates()
