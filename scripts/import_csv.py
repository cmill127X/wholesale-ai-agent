"""Import a public parcel CSV into the canonical lead schema.

Usage:
  python scripts/import_csv.py input.csv output.json

The importer is intentionally conservative: it maps common column aliases and
preserves unknown columns under `raw`. It does not invent missing values.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ALIASES = {
    "property_address": ["property_address", "site_address", "situs", "address", "property"],
    "owner_name": ["owner_name", "owner", "ownername", "taxpayer"],
    "mailing_address": ["mailing_address", "mail_address", "owner_address"],
    "parcel_id": ["parcel_id", "parcel", "parcel_number", "pin", "key_number"],
    "last_transfer_date": ["last_transfer_date", "transfer_date", "sale_date", "last_sale_date"],
    "last_sale_price": ["last_sale_price", "sale_price", "transfer_price", "price"],
}


def pick(row, names):
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def main(src: str, dst: str) -> None:
    records = []
    with Path(src).open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            record = {field: pick(row, aliases) for field, aliases in ALIASES.items()}
            record["raw"] = dict(row)
            records.append(record)
    Path(dst).write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Imported {len(records)} records -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/import_csv.py input.csv output.json")
    main(sys.argv[1], sys.argv[2])
