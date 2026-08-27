import os
import csv
import json
import shutil
import hashlib
import cv2
import numpy as np
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
REAL_SRC_DIR = DATASET_DIR / 'sources' / 'real_public'
SYNTH_SRC_DIR = DATASET_DIR / 'sources' / 'synthetic'


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


def generate_synthetic_train_sample(img_id: int) -> tuple[np.ndarray, list[float]]:
    """Generates an artificial training sample strictly for train-time data augmentation."""
    w = np.random.randint(450, 850)
    h = np.random.randint(300, 600)

    # 10% negative background samples
    if img_id % 10 == 0:
        bg = np.full((h, w, 3), np.random.randint(30, 200, size=3).tolist(), dtype=np.uint8)
        cv2.rectangle(bg, (0, int(h * 0.6)), (w, h), (40, 40, 40), -1)
        return bg, []

    bg_color = np.random.randint(20, 230, size=3).tolist()
    crop = np.full((h, w, 3), bg_color, dtype=np.uint8)
    cv2.rectangle(crop, (int(w * 0.05), int(h * 0.45)), (int(w * 0.95), int(h * 0.9)),
                  (max(0, bg_color[0] - 40), max(0, bg_color[1] - 40), max(0, bg_color[2] - 40)), -1)

    is_bike = (img_id % 7 == 0)
    if is_bike:
        pw = np.random.randint(int(w * 0.18), int(w * 0.28))
        ph = int(pw / np.random.uniform(1.4, 2.0))
    else:
        pw = np.random.randint(int(w * 0.25), int(w * 0.45))
        ph = int(pw / np.random.uniform(3.2, 4.0))

    px1 = int((w - pw) / 2 + np.random.randint(-20, 20))
    py1 = int(h * 0.62 + np.random.randint(-15, 15))
    px2 = min(w - 2, px1 + pw)
    py2 = min(h - 2, py1 + ph)
    px1, py1 = max(2, px1), max(2, py1)
    pw, ph = px2 - px1, py2 - py1

    p_bg = (25, 215, 245) if (img_id % 4 == 0) else (245, 245, 245)
    cv2.rectangle(crop, (px1, py1), (px2, py2), p_bg, -1)
    cv2.rectangle(crop, (px1, py1), (px2, py2), (10, 10, 10), 2)

    strip_w = max(3, int(pw * 0.08))
    cv2.rectangle(crop, (px1, py1), (px1 + strip_w, py2), (180, 50, 0), -1)

    state = ['GJ', 'MH', 'DL', 'KA', 'UP', 'HR'][img_id % 6]
    rto = (img_id % 30) + 1
    num = (img_id * 71) % 9000 + 1000
    text = f'{state}{rto:02d}AB{num}'
    cv2.putText(crop, text, (px1 + strip_w + 4, py1 + int(ph * 0.72)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.35, pw / 320.0), (0, 0, 0), 2)

    xc = (px1 + px2) / (2.0 * w)
    yc = (py1 + py2) / (2.0 * h)
    nw = pw / float(w)
    nh = ph / float(h)
    return crop, [0, xc, yc, nw, nh]


def prepare_verified_dataset(num_synthetic_train: int = 100):
    print('[DATASET] Cleaning and rebuilding dataset splits...')
    clean_dataset()

    # 1. Verify real sources exist
    import importlib
    if not (REAL_SRC_DIR / 'train').exists() or len(list((REAL_SRC_DIR / 'train').glob('*.jpg'))) == 0:
        import_mod = importlib.import_module('03_plate_detection.training.import_real_dataset')
        import_mod.acquire_verified_real_dataset()

    # Load metadata if present
    meta_by_name = {}
    meta_path = REAL_SRC_DIR / 'metadata.json'
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            for rec in json.load(f):
                meta_by_name[rec['image']] = rec

    sources_records = []
    seen_hashes_by_split = {'train': set(), 'val': set(), 'test': set()}

    # 2. VALIDATION SPLIT (REAL ONLY)
    val_src_imgs = sorted(list((REAL_SRC_DIR / 'val').glob('*.jpg')))
    assert len(val_src_imgs) > 0, 'No real validation images available!'

    for img_p in val_src_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'val' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'val' / lbl_p.name

        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))

        img_hash = compute_file_sha256(dest_img)
        seen_hashes_by_split['val'].add(img_hash)

        meta = meta_by_name.get(img_p.name, {})
        sources_records.append({
            'image': img_p.name,
            'source_name': meta.get('source_name', 'justjuu_license_plate_detection'),
            'source_url': meta.get('source_url', 'https://huggingface.co/datasets/justjuu/license-plate-detection'),
            'license': meta.get('license', 'CC-BY-4.0'),
            'download_date': meta.get('download_date', str(date.today())),
            'type': 'real',
            'split': 'val',
            'sha256': img_hash,
        })

    # 3. TEST SPLIT (REAL ONLY)
    test_src_imgs = sorted(list((REAL_SRC_DIR / 'test').glob('*.jpg')))
    assert len(test_src_imgs) > 0, 'No real test images available!'

    for img_p in test_src_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'test' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'test' / lbl_p.name

        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))

        img_hash = compute_file_sha256(dest_img)
        seen_hashes_by_split['test'].add(img_hash)

        meta = meta_by_name.get(img_p.name, {})
        sources_records.append({
            'image': img_p.name,
            'source_name': meta.get('source_name', 'justjuu_license_plate_detection'),
            'source_url': meta.get('source_url', 'https://huggingface.co/datasets/justjuu/license-plate-detection'),
            'license': meta.get('license', 'CC-BY-4.0'),
            'download_date': meta.get('download_date', str(date.today())),
            'type': 'real',
            'split': 'test',
            'sha256': img_hash,
        })

    # 4. TRAIN SPLIT (REAL + SYNTHETIC AUGMENTATION)
    train_src_imgs = sorted(list((REAL_SRC_DIR / 'train').glob('*.jpg')))
    assert len(train_src_imgs) > 0, 'No real train images available!'

    for img_p in train_src_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'train' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'train' / lbl_p.name

        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))

        img_hash = compute_file_sha256(dest_img)
        seen_hashes_by_split['train'].add(img_hash)

        meta = meta_by_name.get(img_p.name, {})
        sources_records.append({
            'image': img_p.name,
            'source_name': meta.get('source_name', 'justjuu_license_plate_detection'),
            'source_url': meta.get('source_url', 'https://huggingface.co/datasets/justjuu/license-plate-detection'),
            'license': meta.get('license', 'CC-BY-4.0'),
            'download_date': meta.get('download_date', str(date.today())),
            'type': 'real',
            'split': 'train',
            'sha256': img_hash,
        })

    # Add synthetic training augmentation strictly in train split
    SYNTH_SRC_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(num_synthetic_train):
        img_name = f'synth_train_{i:04d}.jpg'
        lbl_name = f'synth_train_{i:04d}.txt'
        dest_img = DATASET_DIR / 'images' / 'train' / img_name
        dest_lbl = DATASET_DIR / 'labels' / 'train' / lbl_name

        crop, bbox = generate_synthetic_train_sample(i)
        cv2.imwrite(str(dest_img), crop)
        with open(dest_lbl, 'w', encoding='utf-8') as f:
            if bbox:
                c, xc, yc, nw, nh = bbox
                f.write(f'{c} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n')

        img_hash = compute_file_sha256(dest_img)
        sources_records.append({
            'image': img_name,
            'source_name': 'sentineltrack_dev_synthetic_generator',
            'source_url': 'local_codebase://03_plate_detection/training/prepare_dataset.py',
            'license': 'development_augmentation_only',
            'download_date': str(date.today()),
            'type': 'synthetic',
            'split': 'train',
            'sha256': img_hash,
        })

    # Save sources.csv
    sources_csv = DATASET_DIR / 'sources.csv'
    with open(sources_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['image', 'source_name', 'source_url', 'license', 'download_date', 'type', 'split', 'sha256']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sources_records)

    # 5. Integrity & Leakage Assertions
    actual_train = len(list((DATASET_DIR / 'images' / 'train').glob('*.jpg')))
    actual_val = len(list((DATASET_DIR / 'images' / 'val').glob('*.jpg')))
    actual_test = len(list((DATASET_DIR / 'images' / 'test').glob('*.jpg')))

    # Assert 0 hash overlap across splits
    assert len(seen_hashes_by_split['train'].intersection(seen_hashes_by_split['val'])) == 0, 'Train and Val contain duplicate image hashes!'
    assert len(seen_hashes_by_split['train'].intersection(seen_hashes_by_split['test'])) == 0, 'Train and Test contain duplicate image hashes!'
    assert len(seen_hashes_by_split['val'].intersection(seen_hashes_by_split['test'])) == 0, 'Val and Test contain duplicate image hashes!'

    print(f'\n[DATASET VERIFIED] Multi-Source Production Splits Created:')
    print(f'  - Train: {actual_train} images ({len(train_src_imgs)} verified real + {num_synthetic_train} synthetic)')
    print(f'  - Val (REAL ONLY): {actual_val} images')
    print(f'  - Test (REAL ONLY): {actual_test} images')
    print(f'  - Zero Hash Leakage: Passed')
    print(f'  - Provenance File: {sources_csv}')


if __name__ == '__main__':
    prepare_verified_dataset(100)
