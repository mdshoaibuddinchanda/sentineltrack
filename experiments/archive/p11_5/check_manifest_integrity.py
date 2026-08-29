"""Check that a derived dataset still matches the hashes in its manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    args = parser.parse_args()
    data_root = (ROOT / args.data).resolve()
    manifest = data_root / "manifest.csv"
    checked = 0
    mismatches = []
    for row in csv.DictReader(manifest.open(encoding="utf-8", newline="")):
        expected = row.get("materialized_sha256") or row.get("image_sha256") or row.get("sha256") or ""
        path = data_root / (row.get("output_image") or row.get("image", ""))
        if not expected or not path.is_file():
            continue
        checked += 1
        actual = digest(path)
        if actual != expected:
            mismatches.append({"image": row.get("output_image", ""), "expected": expected, "actual": actual})
    result = {"data": str(data_root.relative_to(ROOT)).replace("\\", "/"), "checked": checked, "mismatches": len(mismatches), "details": mismatches[:100]}
    print(json.dumps(result, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
