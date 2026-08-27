import os
import csv
import json
import shutil
import hashlib
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
REAL_SRC_DIR = DATASET_DIR / 'sources' / 'real_public'


def clean_dataset():
    """Wipes previous train/val/test split directories completely."""
    for split in ['train', 'val', 'test']:
        img_dir = DATASET_DIR / 'images' / split
        lbl_dir = DATASET_DIR / 'labels' / split

        if img_dir.exists():
            shutil.rmtree(img_dir)
        if lbl_dir.exists():
            shutil.rmtree(lbl_dir)

        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def prepare_verified_dataset():
    print('[DATASET] Cleaning and preparing verified dataset splits...')
    clean_dataset()

    meta_path = REAL_SRC_DIR / 'metadata.json'
    if not meta_path.exists():
        import importlib
        import_mod = importlib.import_module('03_plate_detection.training.import_real_dataset')
        import_mod.ingest_quobotic_dataset()

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta_records = json.load(f)

    meta_by_name = {rec['image']: rec for rec in meta_records}
    assert len(meta_by_name) == 2531, f'Expected 2531 metadata entries, found {len(meta_by_name)}'

    sources_records = []
    seen_hashes_by_split = {'train': set(), 'val': set(), 'test': set()}
    prepared_counts = {'train': 0, 'val': 0, 'test': 0}

    for split in ['val', 'test', 'train']:
        src_split_dir = REAL_SRC_DIR / split
        dest_img_dir = DATASET_DIR / 'images' / split
        dest_lbl_dir = DATASET_DIR / 'labels' / split

        img_files = sorted(list(src_split_dir.glob('*.jpg')) + list(src_split_dir.glob('*.png')))
        assert len(img_files) > 0, f'No images found in real source for {split}!'

        print(f'[DATASET] Populating {split} split with {len(img_files)} genuine real Indian images...')

        for img_p in img_files:
            lbl_p = src_split_dir / img_p.with_suffix('.txt').name
            if not lbl_p.exists():
                raise FileNotFoundError(f'Missing label for {img_p.name}')

            # Strict assertion: Provenance record MUST exist in metadata.json
            assert img_p.name in meta_by_name, f'Missing metadata provenance record for {img_p.name}!'
            meta = meta_by_name[img_p.name]

            dest_img = dest_img_dir / img_p.name
            dest_lbl = dest_lbl_dir / lbl_p.name

            shutil.copy2(str(img_p), str(dest_img))
            shutil.copy2(str(lbl_p), str(dest_lbl))

            img_hash = compute_file_sha256(dest_img)
            seen_hashes_by_split[split].add(img_hash)

            sources_records.append({
                'image': img_p.name,
                'source_name': meta['source_name'],
                'source_url': meta['source_url'],
                'license': meta['license'],
                'download_date': meta['download_date'],
                'type': 'real',
                'split': split,
                'sha256': img_hash,
            })
            prepared_counts[split] += 1

    # Save sources.csv
    sources_csv = DATASET_DIR / 'sources.csv'
    with open(sources_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['image', 'source_name', 'source_url', 'license', 'download_date', 'type', 'split', 'sha256']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sources_records)

    actual_train = len(list((DATASET_DIR / 'images' / 'train').glob('*.*')))
    actual_val = len(list((DATASET_DIR / 'images' / 'val').glob('*.*')))
    actual_test = len(list((DATASET_DIR / 'images' / 'test').glob('*.*')))
    total_prepared = actual_train + actual_val + actual_test

    print(f'\n[DATASET VERIFIED] Prepared Clean Real Indian Plate Dataset:')
    print(f'  - Train: {actual_train} images (Pure Real Quobotic Dataset)')
    print(f'  - Val (100% REAL ONLY): {actual_val} images')
    print(f'  - Test (100% REAL ONLY): {actual_test} images')
    print(f'  - Total: {total_prepared} images')
    print(f'  - Total sources.csv records: {len(sources_records)}')

    # Assert exact counts
    assert actual_train == 2035, f'Expected 2035 train images, found {actual_train}'
    assert actual_val == 329, f'Expected 329 val images, found {actual_val}'
    assert actual_test == 167, f'Expected 167 test images, found {actual_test}'
    assert total_prepared == 2531, f'Expected 2531 total images, found {total_prepared}'
    assert len(sources_records) == 2531, f'Expected 2531 sources.csv rows, found {len(sources_records)}'

    # Assert 0 hash overlap across splits
    assert len(seen_hashes_by_split['train'].intersection(seen_hashes_by_split['val'])) == 0, 'Train and Val contain duplicate image hashes!'
    assert len(seen_hashes_by_split['train'].intersection(seen_hashes_by_split['test'])) == 0, 'Train and Test contain duplicate image hashes!'
    assert len(seen_hashes_by_split['val'].intersection(seen_hashes_by_split['test'])) == 0, 'Val and Test contain duplicate image hashes!'

    print(f'  - Zero Hash Leakage Check: PASSED')
    print(f'  - Provenance File: {sources_csv}')
    return total_prepared


if __name__ == '__main__':
    prepare_verified_dataset()
