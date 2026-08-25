"""Second-pass quality-control loop."""
from __future__ import annotations

from typing import Any, Dict, List
from app import quality_control


def second_pass(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-run normalization, dedupe and scoring while preserving parcel metadata."""
    first = quality_control(records)

    # quality_control stores extra parcel fields inside Lead.metadata.
    # Flatten that metadata back into the record before pass two so fields
    # such as property type, city, ZIP, parcel ID and assessed values survive
    # the second normalization/QC pass.
    second_input: List[Dict[str, Any]] = []
    for lead in first["leads"]:
        record = dict(lead)
        metadata = record.pop("metadata", {}) or {}
        if isinstance(metadata, dict):
            record.update(metadata)
        second_input.append(record)

    second = quality_control(second_input)
    second["qc"] = {
        "passes": 2,
        "stable_count": first["count"] == second["count"],
        "new_duplicates_removed": second["duplicates_removed"],
        "ready_for_delivery": not second["flags"],
    }
    return second
