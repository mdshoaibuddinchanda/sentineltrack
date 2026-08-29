"""Mark the measured P11.5 candidate runs selected by the final reports."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments" / "p11_5" / "registry.csv"
DECISIONS = {
    "p3-yolo11s-v2-e20-b4-640-r3-clean": ("SELECTED", "13cdc1f68224fad1fb87fa764f0229b615fc702fe134df8ad73d3cce1196a47b"),
    "obb-yolo11s-v2-e20-b4-640-r3-clean": ("SELECTED", "5fe9aa43204c1eda3351803859a84811bed37d63abfdb6299019bc9c3a20ac4f"),
}


def main() -> int:
    with REGISTRY.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    for row in rows:
        decision = DECISIONS.get(row.get("run_id", ""))
        if decision:
            row["decision"], row["dataset_sha256"] = decision
            marker = "finalized_against_authoritative_clean_test_evaluation"
            if marker not in row.get("notes", ""):
                row["notes"] = (row.get("notes", "") + ";" + marker).lstrip(";")
    temporary = REGISTRY.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(REGISTRY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
