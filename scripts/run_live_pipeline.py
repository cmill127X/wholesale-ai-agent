"""Run the live county parcel source through the wholesale pipeline.

Usage:
    python scripts/run_live_pipeline.py --where "PROPTYPE = 'Residential'" --limit 100

The script intentionally defaults to a small page. Increase limits only when
needed and respect the source's public-service usage policies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sources.st_joseph_live import query_parcels, to_canonical
from app import quality_control


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--where", default="1=1")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", default="live_results.json")
    args = parser.parse_args()

    rows = query_parcels(where=args.where, limit=args.limit)
    leads = quality_control(to_canonical(rows))
    Path(args.output).write_text(json.dumps(leads, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in leads.items() if k != "leads"}, indent=2))
    print(f"Wrote {len(leads['leads'])} reviewed records to {args.output}")


if __name__ == "__main__":
    main()
