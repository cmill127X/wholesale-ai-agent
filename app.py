"""Wholesale AI Agent - zero-cost-first MVP.

Deterministic normalization, lead screening, deduplication and two-pass QC.
The screening model is a heuristic for prioritization, not a statement that a
property is distressed or that an owner is likely to sell.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
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
    metadata: Dict[str, Any] = field(default_factory=dict)
    lead_score: int = 0
    lead_tier: str = "C"
    screening_reasons: List[str] = field(default_factory=list)

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def _first(raw: Dict[str, Any], keys: List[str]) -> str:
    return next((normalize_text(raw.get(k)) for k in keys if normalize_text(raw.get(k))), "")

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
    clean = {k: _first(raw, v) for k, v in aliases.items()}
    canonical_keys = {x for values in aliases.values() for x in values}
    metadata = {k: v for k, v in raw.items() if k not in canonical_keys}
    return Lead(**clean, metadata=metadata)

def _money(value: Any) -> float | None:
    text = normalize_text(value).replace("$", "").replace(",", "")
    try:
        return float(text) if text else None
    except ValueError:
        return None

def _date(value: Any) -> date | None:
    text = normalize_text(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    return None

def screen_lead(lead: Lead) -> Lead:
    """Prioritize leads using transparent public-data signals only."""
    score = 0
    reasons: List[str] = []
    prop_city = normalize_text(lead.metadata.get("property_city")).lower()
    prop_state = normalize_text(lead.metadata.get("property_state")).lower()
    mail_city = normalize_text(lead.metadata.get("mailing_city")).lower()
    mail_state = normalize_text(lead.metadata.get("mailing_state")).lower()

    if prop_city and mail_city and (prop_city != mail_city or prop_state != mail_state):
        score += 25
        reasons.append("mailing address differs from property location (absentee-owner signal)")

    transfer = _date(lead.last_transfer_date)
    if transfer:
        years = (date.today() - transfer).days / 365.25
        if years >= 15:
            score += 20
            reasons.append("15+ year hold")
        elif years >= 10:
            score += 12
            reasons.append("10+ year hold")

    sale = _money(lead.last_sale_price)
    if sale is not None:
        if sale <= 100000:
            score += 15
            reasons.append("low recorded sale price")
        elif sale <= 175000:
            score += 8
            reasons.append("moderate recorded sale price")
        land = _money(lead.metadata.get("assessed_land_value")) or 0
        improvement = _money(lead.metadata.get("assessed_improvement_value")) or 0
        assessed = land + improvement
        if assessed > sale * 1.5:
            score += 20
            reasons.append("assessed value materially above last recorded sale price")
        elif assessed > sale:
            score += 10
            reasons.append("assessed value above last recorded sale price")

    prop_type = normalize_text(lead.metadata.get("property_type")).lower()
    if any(word in prop_type for word in ("residential", "single family", "dwelling", "house")):
        score += 10
        reasons.append("residential property-type signal")

    if lead.mailing_address and lead.property_address:
        score += 5
        reasons.append("complete address data")

    lead.lead_score = min(score, 100)
    lead.lead_tier = "A" if score >= 65 else "B" if score >= 40 else "C"
    lead.screening_reasons = reasons
    return lead

def deduplicate(leads: Iterable[Lead]) -> List[Lead]:
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
    fields = [lead.property_address, lead.owner_name, lead.mailing_address,
              lead.last_transfer_date, lead.last_sale_price, lead.source]
    score = round(sum(bool(x) for x in fields) / len(fields), 2)
    lead.confidence = score
    lead.verification_status = "verified" if score >= 0.83 else "needs_review" if score >= 0.5 else "unverified"
    return screen_lead(lead)

def quality_control(leads: Iterable[Lead]) -> Dict[str, Any]:
    """Normalize, dedupe, score and flag incomplete records."""
    first_pass = [normalize_lead(x if isinstance(x, dict) else asdict(x)) for x in leads]
    unique = deduplicate(first_pass)
    reviewed = [score_lead(x) for x in unique]
    flags = []
    for lead in reviewed:
        missing = [field for field in ("property_address", "owner_name", "source") if not getattr(lead, field)]
        if missing:
            flags.append({"property_address": lead.property_address, "missing": missing})
    reviewed.sort(key=lambda x: (-x.lead_score, -x.confidence, x.property_address))
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
