import os
import csv
import shutil
import cv2
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'


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


def generate_synthetic_plate_crop(img_id: int, split: str) -> tuple[np.ndarray, list[float]]:
    """
    Generates a realistic vehicle crop with Indian license plate layout.
    """
    # Base vehicle crop dimensions
    w = np.random.randint(400, 800)
    h = np.random.randint(300, 600)

    # 10% negative background samples (no plate)
    if img_id % 10 == 0:
        bg_color = np.random.randint(30, 220, size=3).tolist()
        crop = np.full((h, w, 3), bg_color, dtype=np.uint8)
        # Add road texture / bumper without plate
        cv2.rectangle(crop, (0, int(h * 0.6)), (w, h), (40, 40, 40), -1)
        return crop, []

    # Vehicle body color
    bg_color = np.random.randint(20, 240, size=3).tolist()
    crop = np.full((h, w, 3), bg_color, dtype=np.uint8)

    # Vehicle bumper and grille contours
    cv2.rectangle(crop, (int(w * 0.05), int(h * 0.5)), (int(w * 0.95), int(h * 0.95)),
                  (max(0, bg_color[0] - 40), max(0, bg_color[1] - 40), max(0, bg_color[2] - 40)), -1)

    # Plate dimensions (standard Indian car plate ~3.5:1 ratio, bike ~1.8:1)
    is_motorcycle = (img_id % 7 == 0)
    if is_motorcycle:
        pw = np.random.randint(int(w * 0.18), int(w * 0.28))
        ph = int(pw / np.random.uniform(1.4, 2.0))
    else:
        pw = np.random.randint(int(w * 0.25), int(w * 0.45))
        ph = int(pw / np.random.uniform(3.2, 4.0))

    # Plate placement (centered on bumper)
    px1 = int((w - pw) / 2 + np.random.randint(-20, 20))
    py1 = int(h * 0.65 + np.random.randint(-15, 15))
    px2 = px1 + pw
    py2 = py1 + ph

    # Clamp coordinates
    px1, py1 = max(0, px1), max(0, py1)
    px2, py2 = min(w, px2), min(h, py2)
    pw = px2 - px1
    ph = py2 - py1

    # Plate type: White (private), Yellow (commercial), Green (EV)
    mod = img_id % 5
    if mod == 0:
        plate_bg = (30, 215, 245)  # Yellow (BGR)
    elif mod == 1:
        plate_bg = (50, 160, 40)   # Green (EV)
    else:
        plate_bg = (245, 245, 245) # White

    cv2.rectangle(crop, (px1, py1), (px2, py2), plate_bg, -1)
    cv2.rectangle(crop, (px1, py1), (px2, py2), (10, 10, 10), 2)  # border

    # Blue HSRP strip on left edge
    strip_w = max(4, int(pw * 0.08))
    cv2.rectangle(crop, (px1, py1), (px1 + strip_w, py2), (180, 50, 0), -1)

    # Render license plate alphanumeric text
    state_codes = ['GJ', 'MH', 'DL', 'KA', 'HR', 'UP', 'RJ']
    state = state_codes[img_id % len(state_codes)]
    district = (img_id % 38) + 1
    series_chars = chr(65 + (img_id % 26)) + chr(65 + ((img_id * 3) % 26))
    num = (img_id * 73) % 9000 + 1000
    plate_text = f'{state}{district:02d}{series_chars}{num}'

    text_color = (0, 0, 0)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.35, min(0.9, pw / 300.0))
    cv2.putText(crop, plate_text, (px1 + strip_w + 4, py1 + int(ph * 0.72)),
                font, font_scale, text_color, 2)

    # Lighting condition simulation (night/low-light or headlight glare)
    if img_id % 4 == 0:
        # Night dimming
        crop = (crop.astype(np.float32) * 0.45).astype(np.uint8)

    # YOLO normalized coordinates: class x_c y_c w h
    x_center = (px1 + px2) / (2.0 * w)
    y_center = (py1 + py2) / (2.0 * h)
    norm_w = pw / float(w)
    norm_h = ph / float(h)

    return crop, [0, x_center, y_center, norm_w, norm_h]


def prepare_dataset(total_samples: int = 300):
    print(f'[DATASET] Cleaning and preparing {total_samples} plate detection samples with provenance...')
    clean_dataset()

    sources = []
    num_train = int(total_samples * 0.70)
    num_val = int(total_samples * 0.15)
    num_test = total_samples - num_train - num_val

    splits = (
        [('train', i) for i in range(num_train)] +
        [('val', i) for i in range(num_train, num_train + num_val)] +
        [('test', i) for i in range(num_train + num_val, total_samples)]
    )

    for split, idx in splits:
        img_name = f'plate_sample_{idx:05d}.jpg'
        label_name = f'plate_sample_{idx:05d}.txt'

        img_path = DATASET_DIR / 'images' / split / img_name
        label_path = DATASET_DIR / 'labels' / split / label_name

        img, bbox = generate_synthetic_plate_crop(idx, split)

        # Save image
        cv2.imwrite(str(img_path), img)

        # Save YOLO label (empty for negative samples)
        with open(label_path, 'w', encoding='utf-8') as f:
            if bbox:
                cls_id, xc, yc, nw, nh = bbox
                f.write(f'{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n')

        sources.append({
            'image': img_name,
            'source': 'sentineltrack_synthetic_generator',
            'license': 'team_generated',
            'split': split,
        })

    # Save provenance CSV
    sources_csv = DATASET_DIR / 'sources.csv'
    with open(sources_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['image', 'source', 'license', 'split'])
        writer.writeheader()
        writer.writerows(sources)

    train_count = len(list((DATASET_DIR / 'images' / 'train').glob('*.jpg')))
    val_count = len(list((DATASET_DIR / 'images' / 'val').glob('*.jpg')))
    test_count = len(list((DATASET_DIR / 'images' / 'test').glob('*.jpg')))

    assert train_count == num_train, f'Expected {num_train} train images, found {train_count}'
    assert val_count == num_val, f'Expected {num_val} val images, found {val_count}'
    assert test_count == num_test, f'Expected {num_test} test images, found {test_count}'

    print(f'[DATASET] Clean verification passed: {train_count} train, {val_count} val, {test_count} test images.')
    print(f'[DATASET] Provenance catalog written to {sources_csv}')


if __name__ == '__main__':
    prepare_dataset(300)


