"""Research orchestration layer.

MVP behavior: accept evidence gathered by a source connector, normalize it,
then run it through the existing QC pipeline. Network access is intentionally
kept outside this module so source-specific rules remain auditable.
"""
from typing import Any, Dict, Iterable, List

from app import quality_control


def build_research_request(target: str, criteria: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "target": target,
        "criteria": criteria or {},
        "required_evidence": ["property_address", "owner_name", "source"],
        "verification_policy": "two_pass",
    }


def process_evidence(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn collected source records into a clean, scored dataset."""
    return quality_control(list(records))


def research_status(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    result = process_evidence(records)
    return {
        "records_received": len(list(records)) if not isinstance(records, list) else len(records),
        "records_after_qc": result["count"],
        "verified": result["verified"],
        "needs_review": result["needs_review"],
        "duplicates_removed": result["duplicates_removed"],
        "flags": result["flags"],
    }
