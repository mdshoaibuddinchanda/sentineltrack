import os
import csv
import json
import shutil
import cv2
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
PUBLIC_DIR = DATASET_DIR / 'sources' / 'public_indian'
SYNTH_DIR = DATASET_DIR / 'sources' / 'synthetic'


def clean_dataset():
    """Wipes all previous images and labels across train/val/test splits to avoid dataset contamination."""
    for split in ['train', 'val', 'test']:
        img_dir = DATASET_DIR / 'images' / split
        lbl_dir = DATASET_DIR / 'labels' / split

        if img_dir.exists():
            shutil.rmtree(img_dir)
        if lbl_dir.exists():
            shutil.rmtree(lbl_dir)

        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)


def generate_synthetic_plate_crop(img_id: int) -> tuple[np.ndarray, list[float]]:
    """Generates an augmented synthetic vehicle crop for training data augmentation."""
    w = np.random.randint(450, 850)
    h = np.random.randint(300, 600)

    # 10% negative background samples
    if img_id % 10 == 0:
        bg = np.full((h, w, 3), np.random.randint(30, 200, size=3).tolist(), dtype=np.uint8)
        cv2.rectangle(bg, (0, int(h * 0.6)), (w, h), (40, 40, 40), -1)
        return bg, []

    bg_color = np.random.randint(20, 230, size=3).tolist()
    crop = np.full((h, w, 3), bg_color, dtype=np.uint8)
    cv2.rectangle(crop, (int(w * 0.05), int(h * 0.45)), (int(w * 0.95), int(h * 0.9)), (max(0, bg_color[0] - 40), max(0, bg_color[1] - 40), max(0, bg_color[2] - 40)), -1)

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


def prepare_production_dataset(
    num_real_val: int = 35,
    num_real_test: int = 35,
    num_synthetic_train: int = 200,
):
    """
    Constructs the production dataset:
    - Validation: REAL ONLY (num_real_val)
    - Test: REAL ONLY (num_real_test)
    - Train: Remaining Real + Synthetic Augmentation
    """
    print('[DATASET] Cleaning previous dataset splits...')
    clean_dataset()

    # 1. Check if real Indian dataset exists in sources/public_indian
    import importlib
    if not PUBLIC_DIR.exists() or len(list(PUBLIC_DIR.glob('*.jpg'))) == 0:
        import_mod = importlib.import_module('03_plate_detection.training.import_real_dataset')
        import_mod.acquire_real_indian_dataset()

    real_images = sorted(list(PUBLIC_DIR.glob('*.jpg')))
    total_real = len(real_images)
    print(f'[DATASET] Found {total_real} real Indian vehicle plate images.')

    assert total_real >= (num_real_val + num_real_test + 10), f'Insufficient real images ({total_real}) for clean real val/test split!'

    # Split real images strictly with 0 overlap:
    # 0 to num_real_val -> val
    # num_real_val to (num_real_val + num_real_test) -> test
    # remainder -> train
    real_val_imgs = real_images[:num_real_val]
    real_test_imgs = real_images[num_real_val : num_real_val + num_real_test]
    real_train_imgs = real_images[num_real_val + num_real_test:]

    sources_records = []

    # Copy real validation images (REAL ONLY)
    for img_p in real_val_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'val' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'val' / lbl_p.name
        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))
        sources_records.append({
            'image': img_p.name,
            'source': 'public_indian_open_anpr',
            'license': 'CC-BY-SA-4.0',
            'type': 'real',
            'split': 'val',
        })

    # Copy real test images (REAL ONLY)
    for img_p in real_test_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'test' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'test' / lbl_p.name
        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))

        sources_records.append({
            'image': img_p.name,
            'source': 'public_indian_open_anpr',
            'license': 'CC-BY-SA-4.0',
            'type': 'real',
            'split': 'test',
        })

    # Copy real train images
    for img_p in real_train_imgs:
        lbl_p = img_p.with_suffix('.txt')
        dest_img = DATASET_DIR / 'images' / 'train' / img_p.name
        dest_lbl = DATASET_DIR / 'labels' / 'train' / lbl_p.name
        shutil.copy2(str(img_p), str(dest_img))
        if lbl_p.exists():
            shutil.copy2(str(lbl_p), str(dest_lbl))
        sources_records.append({
            'image': img_p.name,
            'source': 'public_indian_open_anpr',
            'license': 'CC-BY-SA-4.0',
            'type': 'real',
            'split': 'train',
        })

    # Generate synthetic training augmentation
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(num_synthetic_train):
        img_name = f'synth_train_{i:04d}.jpg'
        lbl_name = f'synth_train_{i:04d}.txt'
        dest_img = DATASET_DIR / 'images' / 'train' / img_name
        dest_lbl = DATASET_DIR / 'labels' / 'train' / lbl_name

        crop, bbox = generate_synthetic_plate_crop(i)
        cv2.imwrite(str(dest_img), crop)
        with open(dest_lbl, 'w', encoding='utf-8') as f:
            if bbox:
                c, xc, yc, nw, nh = bbox
                f.write(f'{c} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n')

        sources_records.append({
            'image': img_name,
            'source': 'sentineltrack_synthetic_generator',
            'license': 'team_generated',
            'type': 'synthetic',
            'split': 'train',
        })

    # Write sources.csv
    sources_csv = DATASET_DIR / 'sources.csv'
    with open(sources_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['image', 'source', 'license', 'type', 'split'])
        writer.writeheader()
        writer.writerows(sources_records)

    # Verification assertions
    actual_train = len(list((DATASET_DIR / 'images' / 'train').glob('*.jpg')))
    actual_val = len(list((DATASET_DIR / 'images' / 'val').glob('*.jpg')))
    actual_test = len(list((DATASET_DIR / 'images' / 'test').glob('*.jpg')))

    expected_train = len(real_train_imgs) + num_synthetic_train
    assert actual_train == expected_train, f'Expected {expected_train} train images, found {actual_train}'
    assert actual_val == num_real_val, f'Expected {num_real_val} val images, found {actual_val}'
    assert actual_test == num_real_test, f'Expected {num_real_test} test images, found {actual_test}'

    print(f'[DATASET] Clean production split created:')
    print(f'  - Train: {actual_train} images ({len(real_train_imgs)} real + {num_synthetic_train} synthetic)')
    print(f'  - Val (REAL ONLY): {actual_val} images')
    print(f'  - Test (REAL ONLY): {actual_test} images')
    print(f'  - Provenance: {sources_csv}')


if __name__ == '__main__':
    prepare_production_dataset()
