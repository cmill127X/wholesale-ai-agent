"""Second-pass quality-control loop."""
from __future__ import annotations

from typing import Any, Dict, List
from app import quality_control


def second_pass(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-run normalization, dedupe and scoring and return audit metadata."""
    first = quality_control(records)
    second = quality_control(first["leads"])
    second["qc"] = {
        "passes": 2,
        "stable_count": first["count"] == second["count"],
        "new_duplicates_removed": second["duplicates_removed"],
        "ready_for_delivery": not second["flags"],
    }
    return second
