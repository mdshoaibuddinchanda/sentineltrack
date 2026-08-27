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


def ingest_quobotic_dataset():
    print('[INGEST] Wiping stale datasets/plate_detection/sources/real_public directory...')
    if REAL_SRC_DIR.exists():
        shutil.rmtree(REAL_SRC_DIR)

    for split in ['train', 'val', 'test']:
        (REAL_SRC_DIR / split).mkdir(parents=True, exist_ok=True)

    if not ROBOFLOW_SRC_DIR.exists():
        raise FileNotFoundError(f'Quobotic source directory {ROBOFLOW_SRC_DIR} not found.')

    meta_records = []
    split_map = {'train': 'train', 'valid': 'val', 'test': 'test'}
    split_counts = {'train': 0, 'val': 0, 'test': 0}

    for rf_split, canon_split in split_map.items():
        src_img_dir = ROBOFLOW_SRC_DIR / rf_split / 'images'
        src_lbl_dir = ROBOFLOW_SRC_DIR / rf_split / 'labels'
        dest_split_dir = REAL_SRC_DIR / canon_split

        img_files = sorted(list(src_img_dir.glob('*.jpg')) + list(src_img_dir.glob('*.png')))
        print(f'[INGEST] Copying {len(img_files)} images from {rf_split} to {canon_split}...')

        for img_p in img_files:
            lbl_p = src_lbl_dir / img_p.with_suffix('.txt').name
            if not lbl_p.exists():
                raise FileNotFoundError(f'Missing label file for {img_p.name}')

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
            split_counts[canon_split] += 1

    metadata_path = REAL_SRC_DIR / 'metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(meta_records, f, indent=2)

    total_imported = sum(split_counts.values())
    print(f'\n[VERIFICATION] Source Ingestion Counts:')
    print(f"  - Train: {split_counts['train']} images")
    print(f"  - Val:   {split_counts['val']} images")
    print(f"  - Test:  {split_counts['test']} images")
    print(f'  - Total: {total_imported} images')

    assert split_counts['train'] == 2035, f"Expected 2035 train images, found {split_counts['train']}"
    assert split_counts['val'] == 329, f"Expected 329 val images, found {split_counts['val']}"
    assert split_counts['test'] == 167, f"Expected 167 test images, found {split_counts['test']}"
    assert total_imported == 2531, f'Expected 2531 total images, found {total_imported}'
    assert len(meta_records) == 2531, f'Expected 2531 metadata records, found {len(meta_records)}'


    print(f'[SUCCESS] Quobotic dataset cleanly imported with verified exact counts (2035/329/167 -> 2531).')
    return total_imported


if __name__ == '__main__':
    ingest_quobotic_dataset()
