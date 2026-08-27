import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
SOURCES_CSV = DATASET_DIR / 'sources.csv'


def test_sources_csv_exists_and_valid():
    assert SOURCES_CSV.exists(), 'datasets/plate_ocr/sources.csv missing!'

    rows = []
    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    assert len(rows) >= 1000, f'Expected >= 1000 records in sources.csv, found {len(rows)}'
    for r in rows:
        assert r['source_name'] == 'zenitsu09_indian_number_plate'
        assert r['license'] == 'CC-BY-4.0'
        assert r['type'] == 'real'
        assert len(r['sha256']) == 64


def test_no_synthetic_in_val_or_test():
    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r['split'] in ('val', 'test'):
                assert r['type'] == 'real', f"Synthetic sample found in {r['split']}!"



def test_zero_hash_and_identity_leakage():
    hashes_by_split = {'train': set(), 'val': set(), 'test': set()}
    identities_by_split = {'train': set(), 'val': set(), 'test': set()}

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            split = r['split']
            hashes_by_split[split].add(r['sha256'])
            identities_by_split[split].add(r['parent_identity'])

    # Zero hash leakage
    assert len(hashes_by_split['train'].intersection(hashes_by_split['val'])) == 0
    assert len(hashes_by_split['train'].intersection(hashes_by_split['test'])) == 0
    assert len(hashes_by_split['val'].intersection(hashes_by_split['test'])) == 0

    # Zero identity leakage
    assert len(identities_by_split['train'].intersection(identities_by_split['val'])) == 0
    assert len(identities_by_split['train'].intersection(identities_by_split['test'])) == 0
    assert len(identities_by_split['val'].intersection(identities_by_split['test'])) == 0
