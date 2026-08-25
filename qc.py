"""Second-pass quality-control loop."""
from __future__ import annotations
from typing import Any, Dict, List


def _flatten(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output=[]
    for lead in leads:
        record=dict(lead)
        metadata=record.pop("metadata",{}) or {}
        if isinstance(metadata,dict):
            record.update(metadata)
        output.append(record)
    return output


def second_pass(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-run normalization, dedupe and scoring while preserving enriched parcel metadata."""
    from app import quality_control

    first=quality_control(records)
    second_input=_flatten(first["leads"])
    second=quality_control(second_input)
    second["leads"]=_flatten(second["leads"])
    second["qc"]={
        "passes":2,
        "stable_count":first["count"]==second["count"],
        "new_duplicates_removed":second["duplicates_removed"],
        "ready_for_delivery":not second["flags"],
    }
    return second
