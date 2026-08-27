import csv
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / 'datasets' / 'plate_ocr'
SOURCES_CSV = DATASET_DIR / 'sources.csv'


def generate_manifest_summary() -> dict:
    if not SOURCES_CSV.exists():
        raise FileNotFoundError(f'Missing sources manifest at: {SOURCES_CSV}')

    stats = {
        'total_images': 0,
        'unique_identities': set(),
        'by_split': {'train': 0, 'val': 0, 'test': 0},
        'by_type': {'real': 0, 'synthetic': 0},
        'sources': set(),
        'licenses': set()
    }

    with open(SOURCES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            stats['total_images'] += 1
            stats['unique_identities'].add(r['parent_identity'])
            stats['by_split'][r['split']] = stats['by_split'].get(r['split'], 0) + 1
            stats['by_type'][r['type']] = stats['by_type'].get(r['type'], 0) + 1
            stats['sources'].add(r['source_name'])
            stats['licenses'].add(r['license'])

    summary = {
        'total_images': stats['total_images'],
        'unique_physical_identities': len(stats['unique_identities']),
        'splits': stats['by_split'],
        'types': stats['by_type'],
        'sources': list(stats['sources']),
        'licenses': list(stats['licenses']),
    }

    print('================ DATASET OCR MANIFEST SUMMARY ================')
    print(f"Total Images:               {summary['total_images']}")
    print(f"Unique Physical Plates:     {summary['unique_physical_identities']}")
    print(f"Splits (Train/Val/Test):    {summary['splits']['train']} / {summary['splits']['val']} / {summary['splits']['test']}")
    print(f"Data Types:                 {summary['types']}")
    print(f"Sources & Licenses:         {summary['sources']} ({summary['licenses']})")
    print('==============================================================')


    return summary


if __name__ == '__main__':
    generate_manifest_summary()
