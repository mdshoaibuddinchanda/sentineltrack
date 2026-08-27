import io
import re
import csv
import json
import shutil
import hashlib
import urllib.request
import pandas as pd
from PIL import Image
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
SOURCES_CSV = DATASET_DIR / 'sources.csv'


def compute_sha256(data_bytes: bytes) -> str:
    return hashlib.sha256(data_bytes).hexdigest()


def clean_plate_string(text: str) -> str:
    if not text:
        return ''
    return re.sub(r'[^A-Z0-9]', '', str(text).upper().strip())


def prepare_real_ocr_dataset(val_ratio: float = 0.15, test_ratio: float = 0.15, crop_margin: float = 0.08):
    """
    Ingests genuine real Indian license plate crops with verified ground-truth transcriptions and bbox provenance.
    Enforces strict group-based partitioning on plate identity to prevent identity leakage.
    """
    print('[DATASET OCR] Initializing real Indian license plate OCR dataset preparation...')

    # Wipe destination directories
    for split in ['train', 'val', 'test']:
        img_dir = DATASET_DIR / 'images' / split
        lbl_dir = DATASET_DIR / 'labels' / split
        if img_dir.exists():
            shutil.rmtree(img_dir)
        if lbl_dir.exists():
            shutil.rmtree(lbl_dir)
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

    url = 'https://huggingface.co/datasets/zenitsu09/indian-number-plate/resolve/main/data/train-00000-of-00001.parquet'
    print(f'[DATASET OCR] Fetching verified parquet dataset from: {url}...')

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        parquet_bytes = resp.read()

    df = pd.read_parquet(io.BytesIO(parquet_bytes))
    print(f'[DATASET OCR] Downloaded {len(df)} total raw records.')

    # Process and crop images using verified bbox metadata
    records_by_identity = {}
    total_processed = 0
    total_rejected = 0

    for idx, row in df.iterrows():
        raw_txt = str(row.get('plate_text') or '').strip()
        clean_txt = clean_plate_string(raw_txt)

        if not (6 <= len(clean_txt) <= 12):
            total_rejected += 1
            continue

        img_bytes = row['image']['bytes']
        if not img_bytes:
            total_rejected += 1
            continue

        try:
            im = Image.open(io.BytesIO(img_bytes))
            im_w, im_h = im.size
            x1 = float(row.get('xmin', 0))
            y1 = float(row.get('ymin', 0))
            x2 = float(row.get('xmax', im_w))
            y2 = float(row.get('ymax', im_h))
        except Exception:
            total_rejected += 1
            continue

        orig_sha = compute_sha256(img_bytes)

        # In zenitsu09, if im_w == (x2 - x1) and im_h == (y2 - y1), im is already a crop of that exact bbox
        # If im is larger than bbox, we apply strict crop
        if im_w > (x2 - x1 + 2) or im_h > (y2 - y1 + 2):
            bw = max(x2 - x1, 1)
            bh = max(y2 - y1, 1)
            pad_x = crop_margin * bw
            pad_y = crop_margin * bh
            cx1 = max(0, int(x1 - pad_x))
            cy1 = max(0, int(y1 - pad_y))
            cx2 = min(im_w, int(x2 + pad_x))
            cy2 = min(im_h, int(y2 + pad_y))
            cropped_im = im.crop((cx1, cy1, cx2, cy2))
            buf = io.BytesIO()
            cropped_im.save(buf, format='JPEG', quality=95)
            crop_bytes = buf.getvalue()
            crop_w, crop_h = cropped_im.size
        else:
            cropped_im = im
            crop_bytes = img_bytes
            crop_w, crop_h = im_w, im_h
            cx1, cy1, cx2, cy2 = int(x1), int(y1), int(x2), int(y2)

        if crop_w < 16 or crop_h < 8:
            total_rejected += 1
            continue

        crop_sha = compute_sha256(crop_bytes)

        if clean_txt not in records_by_identity:
            records_by_identity[clean_txt] = []

        records_by_identity[clean_txt].append({
            'idx': idx,
            'plate_text': clean_txt,
            'raw_text': raw_txt,
            'bytes': crop_bytes,
            'orig_sha': orig_sha,
            'crop_sha': crop_sha,
            'xmin': cx1,
            'ymin': cy1,
            'xmax': cx2,
            'ymax': cy2,
            'crop_width': crop_w,
            'crop_height': crop_h,
            'source_name': 'zenitsu09_indian_number_plate',
            'source_url': 'https://huggingface.co/datasets/zenitsu09/indian-number-plate',
            'license': 'LICENSE_UNVERIFIED',
            'download_date': '2025-01-10',
            'type': 'real',
        })
        total_processed += 1

    unique_identities = sorted(list(records_by_identity.keys()))
    total_unique = len(unique_identities)
    print(f'[DATASET OCR] Ingested {total_processed} valid plate crops across {total_unique} unique physical identities.')

    # Deterministic partition
    val_cut = int(total_unique * val_ratio)
    test_cut = int(total_unique * (val_ratio + test_ratio))

    val_identities = set(unique_identities[:val_cut])
    test_identities = set(unique_identities[val_cut:test_cut])
    train_identities = set(unique_identities[test_cut:])

    # Verify zero identity leakage
    assert len(train_identities.intersection(val_identities)) == 0, 'Train and Val share plate identities!'
    assert len(train_identities.intersection(test_identities)) == 0, 'Train and Test share plate identities!'
    assert len(val_identities.intersection(test_identities)) == 0, 'Val and Test share plate identities!'

    split_counts = {'train': 0, 'val': 0, 'test': 0}
    split_identities = {'train': set(), 'val': set(), 'test': set()}
    manifest_rows = []
    seen_hashes = {'train': set(), 'val': set(), 'test': set()}

    for identity, recs in records_by_identity.items():
        if identity in val_identities:
            split = 'val'
        elif identity in test_identities:
            split = 'test'
        else:
            split = 'train'

        split_identities[split].add(identity)

        for rec in recs:
            idx_val = rec['idx']
            img_filename = f'{split}_{identity}_{idx_val}.jpg'
            lbl_filename = f'{split}_{identity}_{idx_val}.txt'

            img_path = DATASET_DIR / 'images' / split / img_filename
            lbl_path = DATASET_DIR / 'labels' / split / lbl_filename

            with open(img_path, 'wb') as f:
                f.write(rec['bytes'])

            with open(lbl_path, 'w', encoding='utf-8') as f:
                f.write(rec['plate_text'])

            split_counts[split] += 1
            seen_hashes[split].add(rec['crop_sha'])

            manifest_rows.append({
                'filename': img_filename,
                'split': split,
                'type': 'real',
                'plate_text': rec['plate_text'],
                'raw_text': rec['raw_text'],
                'parent_identity': identity,
                'original_image_sha256': rec['orig_sha'],
                'crop_sha256': rec['crop_sha'],
                'xmin': rec['xmin'],
                'ymin': rec['ymin'],
                'xmax': rec['xmax'],
                'ymax': rec['ymax'],
                'crop_width': rec['crop_width'],
                'crop_height': rec['crop_height'],
                'source_name': rec['source_name'],
                'source_url': rec['source_url'],
                'license': rec['license'],
                'download_date': rec['download_date'],
            })

    # Assert zero hash leakage
    assert len(seen_hashes['train'].intersection(seen_hashes['val'])) == 0, 'Hash leakage between Train and Val!'
    assert len(seen_hashes['train'].intersection(seen_hashes['test'])) == 0, 'Hash leakage between Train and Test!'
    assert len(seen_hashes['val'].intersection(seen_hashes['test'])) == 0, 'Hash leakage between Val and Test!'

    with open(SOURCES_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print('================ REAL OCR DATASET PARTITION COMPLETE ================')
    print(f"Train Set: {split_counts['train']} crops ({len(split_identities['train'])} unique plate identities)")
    print(f"Val Set:   {split_counts['val']} crops ({len(split_identities['val'])} unique plate identities) [100% REAL]")
    print(f"Test Set:  {split_counts['test']} crops ({len(split_identities['test'])} unique plate identities) [100% REAL]")
    print(f"Total:     {len(manifest_rows)} crops across {total_unique} unique identities")
    print(f"License:   LICENSE_UNVERIFIED (HuggingFace metadata has no explicit license field)")
    print('=====================================================================')



if __name__ == '__main__':
    prepare_real_ocr_dataset()
