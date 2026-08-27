import csv
import importlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
SOURCES_CSV = DATASET_DIR / 'sources.csv'

eval_mod = importlib.import_module('04_plate_ocr.training.evaluate')
calculate_metrics = eval_mod.calculate_metrics


def test_sources_csv_exists_and_valid():
    assert SOURCES_CSV.exists(), 'sources.csv must exist in datasets/plate_ocr'
    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        assert len(reader) >= 1500, f'Expected >=1500 records, got {len(reader)}'

        sample = reader[0]
        required_keys = [
            'filename', 'split', 'type', 'plate_text', 'parent_identity',
            'original_image_sha256', 'crop_sha256', 'xmin', 'ymin', 'xmax', 'ymax',
            'crop_width', 'crop_height', 'source_name', 'source_url', 'license'
        ]
        for k in required_keys:
            assert k in sample, f'Missing required metadata key: {k}'


def test_no_synthetic_in_val_or_test():
    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        for r in reader:
            if r['split'] in ('val', 'test'):
                split_name = r['split']
                fn = r['filename']
                assert r['type'] == 'real', f"Synthetic data detected in split {split_name}: {fn}"


def test_zero_hash_and_identity_leakage():
    hashes = {'train': set(), 'val': set(), 'test': set()}
    identities = {'train': set(), 'val': set(), 'test': set()}

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['split']
            hashes[s].add(r['crop_sha256'])
            identities[s].add(r['parent_identity'])

    # Assert zero hash leakage
    assert len(hashes['train'].intersection(hashes['val'])) == 0, 'Hash leakage: train & val'
    assert len(hashes['train'].intersection(hashes['test'])) == 0, 'Hash leakage: train & test'
    assert len(hashes['val'].intersection(hashes['test'])) == 0, 'Hash leakage: val & test'

    # Assert zero identity leakage
    assert len(identities['train'].intersection(identities['val'])) == 0, 'Identity leakage: train & val'
    assert len(identities['train'].intersection(identities['test'])) == 0, 'Identity leakage: train & test'
    assert len(identities['val'].intersection(identities['test'])) == 0, 'Identity leakage: val & test'


def test_bbox_provenance_and_dimensions():
    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        for r in reader[:100]:
            cw = int(r['crop_width'])
            ch = int(r['crop_height'])
            assert cw >= 16, f'Crop width too small: {cw}'
            assert ch >= 8, f'Crop height too small: {ch}'
            assert int(r['xmax']) >= int(r['xmin']), 'Invalid x coordinates'
            assert int(r['ymax']) >= int(r['ymin']), 'Invalid y coordinates'


def test_raw_vs_postprocessed_metrics():
    # Sample where raw has O instead of 0 in numeric position
    preds = ['GJO1AB1234', 'MH12DE1432']
    gts = ['GJ01AB1234', 'MH12DE1432']

    metrics = calculate_metrics(preds, gts)

    # Raw matches 1/2 (50%) because GJO1 != GJ01
    assert metrics['raw_exact_matches'] == 1
    assert metrics['raw_exact_accuracy'] == 0.50

    # Postprocessed matches 2/2 (100%) because positional grammar alternative swaps O -> 0 in position 2
    assert metrics['postprocessed_exact_matches'] == 2
    assert metrics['postprocessed_exact_accuracy'] == 1.00
