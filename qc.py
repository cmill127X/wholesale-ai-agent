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
    """Run normalization/dedupe twice, then challenge scores with the wholesale strategy layer."""
    from app import quality_control
    from wholesale_strategy import apply_strategy

    first=quality_control(records)
    second_input=_flatten(first["leads"])
    second=quality_control(second_input)
    flattened=_flatten(second["leads"])

    # The second pass is intentionally adversarial: it re-scores from the
    # complete cross-source record and can downgrade a lead whose high score
    # was driven only by weak or redundant signals.
    challenged=apply_strategy(flattened)
    second["leads"]=challenged
    second["count"]=len(challenged)
    second["verified"]=sum(x.get("verification_status")=="verified" for x in challenged)
    second["needs_review"]=sum(x.get("verification_status")=="needs_review" for x in challenged)
    second["qc"]={
        "passes":2,
        "stable_count":first["count"]==second["count"],
        "new_duplicates_removed":second["duplicates_removed"],
        "ready_for_delivery":not second["flags"],
        "strategy_challenge":True,
        "strategy_model":"public-record wholesale prioritization v1",
    }
    return second
