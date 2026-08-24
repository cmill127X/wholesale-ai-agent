"""Wholesale AI Agent - zero-cost-first MVP.

This module implements a deterministic data-quality pipeline. External research
providers can be added later without changing the core normalization/QC flow.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List
import re


@dataclass
class Lead:
    property_address: str = ""
    owner_name: str = ""
    mailing_address: str = ""
    last_transfer_date: str = ""
    last_sale_price: str = ""
    source: str = ""
    notes: str = ""
    confidence: float = 0.0
    verification_status: str = "unverified"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_lead(raw: Dict[str, Any]) -> Lead:
    """Map inconsistent input keys into the canonical Lead schema."""
    aliases = {
        "property_address": ["property_address", "address", "property", "site_address"],
        "owner_name": ["owner_name", "owner", "seller", "name"],
        "mailing_address": ["mailing_address", "mail_address", "owner_address"],
        "last_transfer_date": ["last_transfer_date", "transfer_date", "sale_date", "last_sale_date"],
        "last_sale_price": ["last_sale_price", "sale_price", "price", "last_price"],
        "source": ["source", "url", "record_source"],
        "notes": ["notes", "note", "comments"],
    }
    clean: Dict[str, str] = {}
    for canonical, keys in aliases.items():
        clean[canonical] = next((normalize_text(raw.get(k)) for k in keys if normalize_text(raw.get(k))), "")
    return Lead(**clean)


def deduplicate(leads: Iterable[Lead]) -> List[Lead]:
    """Deduplicate by normalized property address, falling back to owner+mailing address."""
    seen = set()
    output: List[Lead] = []
    for lead in leads:
        key = normalize_text(lead.property_address).lower()
        if not key:
            key = (normalize_text(lead.owner_name) + "|" + normalize_text(lead.mailing_address)).lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(lead)
    return output


def score_lead(lead: Lead) -> Lead:
    """Assign a transparent confidence score based only on available evidence."""
    fields = [
        lead.property_address,
        lead.owner_name,
        lead.mailing_address,
        lead.last_transfer_date,
        lead.last_sale_price,
        lead.source,
    ]
    score = round(sum(bool(x) for x in fields) / len(fields), 2)
    lead.confidence = score
    lead.verification_status = "verified" if score >= 0.83 else "needs_review" if score >= 0.5 else "unverified"
    return lead


def quality_control(leads: Iterable[Lead]) -> Dict[str, Any]:
    """Second-pass QC: normalize, dedupe, rescore, and flag incomplete records."""
    first_pass = [normalize_lead(x if isinstance(x, dict) else asdict(x)) for x in leads]
    unique = deduplicate(first_pass)
    reviewed = [score_lead(x) for x in unique]
    flags = []
    for lead in reviewed:
        missing = [field for field in ("property_address", "owner_name", "source") if not getattr(lead, field)]
        if missing:
            flags.append({"property_address": lead.property_address, "missing": missing})
    return {
        "count": len(reviewed),
        "verified": sum(x.verification_status == "verified" for x in reviewed),
        "needs_review": sum(x.verification_status == "needs_review" for x in reviewed),
        "duplicates_removed": len(first_pass) - len(unique),
        "flags": flags,
        "leads": [asdict(x) for x in reviewed],
    }


if __name__ == "__main__":
    demo = [{"address": "123 Main St", "owner": "Jane Doe", "source": "demo"},
            {"property_address": "123 Main St", "owner_name": "Jane Doe", "source": "demo"}]
    print(quality_control(demo))
