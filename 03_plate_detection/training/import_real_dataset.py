import os
import io
import csv
import json
import hashlib
import urllib.request
from datetime import date
from pathlib import Path
import pandas as pd
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
REAL_SRC_DIR = DATASET_DIR / 'sources' / 'real_public'


def setup_directories():
    for split in ['train', 'val', 'test']:
        (REAL_SRC_DIR / split).mkdir(parents=True, exist_ok=True)


def compute_sha256(data_bytes: bytes) -> str:
    return hashlib.sha256(data_bytes).hexdigest()


def ingest_split(parquet_url: str, split_name: str, max_samples: int = 150) -> list[dict]:
    print(f'[INGEST] Downloading real {split_name} split from {parquet_url}...')
    try:
        req = urllib.request.Request(parquet_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
        df = pd.read_parquet(io.BytesIO(data))
    except Exception as e:
        print(f'[ERROR] Failed downloading {split_name} parquet: {e}')
        return []

    print(f'[INFO] {split_name} dataset contains {len(df)} records. Ingesting up to {max_samples}...')
    records = []
    dest_dir = REAL_SRC_DIR / split_name

    for idx, row in df.iterrows():
        if len(records) >= max_samples:
            break

        img_data = row.get('image')
        if not isinstance(img_data, dict) or 'bytes' not in img_data or not img_data['bytes']:
            continue

        raw_bytes = img_data['bytes']
        img_hash = compute_sha256(raw_bytes)

        objects = row.get('objects')
        if not isinstance(objects, dict) or 'bbox' not in objects or len(objects['bbox']) == 0:
            continue

        try:
            pil_img = Image.open(io.BytesIO(raw_bytes))
            w, h = pil_img.size
            if w < 100 or h < 80:
                continue

            # Ingest bboxes: [x_min, y_min, box_w, box_h]
            boxes_yolo = []
            orig_boxes = []

            for b in objects['bbox']:
                if len(b) < 4:
                    continue
                xmin, ymin, bw, bh = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                xmax = xmin + bw
                ymax = ymin + bh

                # Clamp
                xmin = max(0.0, min(float(w - 1), xmin))
                ymin = max(0.0, min(float(h - 1), ymin))
                xmax = max(0.0, min(float(w), xmax))
                ymax = max(0.0, min(float(h), ymax))

                bw = xmax - xmin
                bh = ymax - ymin
                if bw < 10 or bh < 5:
                    continue

                xc = (xmin + xmax) / (2.0 * w)
                yc = (ymin + ymax) / (2.0 * h)
                nw = bw / float(w)
                nh = bh / float(h)
                boxes_yolo.append(f'0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}')
                orig_boxes.append([round(xmin, 1), round(ymin, 1), round(xmax, 1), round(ymax, 1)])

            if not boxes_yolo:
                continue

            img_filename = f'real_{split_name}_{len(records):04d}.jpg'
            lbl_filename = f'real_{split_name}_{len(records):04d}.txt'

            pil_img.convert('RGB').save(str(dest_dir / img_filename), quality=95)
            with open(dest_dir / lbl_filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(boxes_yolo) + '\n')

            records.append({
                'image': img_filename,
                'source_name': 'justjuu_license_plate_detection',
                'source_url': 'https://huggingface.co/datasets/justjuu/license-plate-detection',
                'license': 'CC-BY-4.0',
                'download_date': str(date.today()),
                'original_index': idx,
                'type': 'real',
                'split': split_name,
                'sha256': img_hash,
                'width': w,
                'height': h,
                'num_plates': len(boxes_yolo),
                'boxes': orig_boxes,
            })

        except Exception as e:
            continue

    print(f'[SUCCESS] Ingested {len(records)} verified real {split_name} images into {dest_dir}')
    return records


def acquire_verified_real_dataset():
    setup_directories()
    
    # 1. Train split
    train_url = 'https://huggingface.co/datasets/justjuu/license-plate-detection/resolve/main/data/train-00000-of-00001.parquet'
    train_records = ingest_split(train_url, 'train', max_samples=250)

    # 2. Validation split (REAL ONLY)
    val_url = 'https://huggingface.co/datasets/justjuu/license-plate-detection/resolve/main/data/validation-00000-of-00001.parquet'
    val_records = ingest_split(val_url, 'val', max_samples=60)

    # 3. Test split (REAL ONLY)
    test_url = 'https://huggingface.co/datasets/justjuu/license-plate-detection/resolve/main/data/test-00000-of-00001.parquet'
    test_records = ingest_split(test_url, 'test', max_samples=60)

    all_records = train_records + val_records + test_records
    metadata_path = REAL_SRC_DIR / 'metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=2)

    print(f'\n[PROVENANCE] Saved verified metadata for {len(all_records)} real images to {metadata_path}')
    return len(all_records)


if __name__ == '__main__':
    acquire_verified_real_dataset()
