import csv
import hashlib
import pytest
from pathlib import Path
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
SOURCES_CSV = DATASET_DIR / 'sources.csv'


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def test_dataset_structure_and_sources_provenance():
    """Verifies that sources.csv exists and specifies valid provenance and real-only val/test."""
    if not SOURCES_CSV.exists():
        pytest.skip('sources.csv not yet generated')

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    assert len(reader) > 0, 'sources.csv is empty'

    val_records = [r for r in reader if r['split'] == 'val']
    test_records = [r for r in reader if r['split'] == 'test']
    train_records = [r for r in reader if r['split'] == 'train']

    assert len(val_records) > 0, 'No validation records'
    assert len(test_records) > 0, 'No test records'
    assert len(train_records) > 0, 'No train records'

    # Strict Rule: Validation and Test must be real only with verified URLs and licenses
    for r in val_records:
        assert r.get('type') == 'real', f"Validation record {r['image']} is not real!"
        assert r.get('source_url', '').startswith('https://'), f"Missing source URL in {r['image']}"
        assert r.get('license') in ('CC-BY-4.0', 'CC0', 'MIT', 'Public Domain'), f"Invalid license in {r['image']}"

    for r in test_records:
        assert r.get('type') == 'real', f"Test record {r['image']} is not real!"
        assert r.get('source_url', '').startswith('https://'), f"Missing source URL in {r['image']}"
        assert r.get('license') in ('CC-BY-4.0', 'CC0', 'MIT', 'Public Domain'), f"Invalid license in {r['image']}"


def test_synthetic_forbidden_in_val_and_test():
    """Ensures synthetic images or sources never enter val or test."""
    if not SOURCES_CSV.exists():
        pytest.skip('sources.csv not yet generated')

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        if r['split'] in ('val', 'test'):
            assert r['type'] != 'synthetic', f"Synthetic image {r['image']} found in {r['split']}!"
            assert 'synthetic' not in r['source_name'].lower(), f"Synthetic source {r['source_name']} in {r['split']}!"


def test_no_fake_sources():
    """Ensures old fake source names are not present."""
    if not SOURCES_CSV.exists():
        pytest.skip('sources.csv not yet generated')

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        assert r['source_name'] != 'public_indian_open_anpr', f"Found prohibited fake source name in {r['image']}!"


def test_dataset_no_hash_leakage_between_splits():
    """Ensures zero SHA-256 hash overlap across train, val, and test splits."""
    train_imgs = list((DATASET_DIR / 'images' / 'train').glob('*.jpg'))
    val_imgs = list((DATASET_DIR / 'images' / 'val').glob('*.jpg'))
    test_imgs = list((DATASET_DIR / 'images' / 'test').glob('*.jpg'))

    if not train_imgs or not val_imgs or not test_imgs:
        pytest.skip('Dataset splits not populated')

    train_hashes = {compute_file_sha256(p) for p in train_imgs}
    val_hashes = {compute_file_sha256(p) for p in val_imgs}
    test_hashes = {compute_file_sha256(p) for p in test_imgs}

    assert len(train_hashes.intersection(val_hashes)) == 0, 'Train and Val split have duplicate image hashes!'
    assert len(train_hashes.intersection(test_hashes)) == 0, 'Train and Test split have duplicate image hashes!'
    assert len(val_hashes.intersection(test_hashes)) == 0, 'Val and Test split have duplicate image hashes!'


def test_production_plate_model_contract():
    """Verifies that the production plate detector satisfies the single-class contract."""
    prod_model_path = ROOT_DIR / 'models' / 'plate' / 'production' / 'best.pt'
    if not prod_model_path.exists():
        pytest.skip('Production model not yet built')

    model = YOLO(str(prod_model_path))
    assert len(model.names) == 1, f"Expected 1 class, got {len(model.names)}"
    assert 0 in model.names, "Class 0 missing in plate model"
    assert model.names[0] == 'license_plate', f"Expected 'license_plate', got '{model.names[0]}'"
