import csv
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_detection'
SOURCES_CSV = DATASET_DIR / 'sources.csv'


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

    # Strict Rule: Validation and Test must be real only
    for r in val_records:
        assert r.get('type') == 'real', f"Validation record {r['image']} is not real!"
        assert r.get('source') == 'public_indian_open_anpr'

    for r in test_records:
        assert r.get('type') == 'real', f"Test record {r['image']} is not real!"
        assert r.get('source') == 'public_indian_open_anpr'


def test_dataset_no_leakage_between_splits():
    """Ensures that there is 0 image overlap across train, val, and test splits."""
    train_imgs = set((DATASET_DIR / 'images' / 'train').glob('*.jpg'))
    val_imgs = set((DATASET_DIR / 'images' / 'val').glob('*.jpg'))
    test_imgs = set((DATASET_DIR / 'images' / 'test').glob('*.jpg'))

    if not train_imgs or not val_imgs or not test_imgs:
        pytest.skip('Dataset splits not yet populated')

    train_names = {p.name for p in train_imgs}
    val_names = {p.name for p in val_imgs}
    test_names = {p.name for p in test_imgs}

    assert len(train_names.intersection(val_names)) == 0, 'Train and Val split have overlapping images!'
    assert len(train_names.intersection(test_names)) == 0, 'Train and Test split have overlapping images!'
    assert len(val_names.intersection(test_names)) == 0, 'Val and Test split have overlapping images!'
