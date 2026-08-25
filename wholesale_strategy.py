"""Transparent wholesale lead strategy layer.

This is a prioritization model using public-record signals. It is deliberately
not a claim that an owner is distressed or will sell.
"""
from __future__ import annotations
from datetime import date
from typing import Any, Dict, List


def _num(value: Any) -> float:
    try:
        return float(str(value).replace("$", "").replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def _year(value: Any) -> int | None:
    text = str(value or "")[:4]
    try:
        year = int(text)
        return year if 1800 <= year <= date.today().year else None
    except Exception:
        return None


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().replace(",", " ").split())


def _same_address(property_address: Any, mailing_address: Any) -> bool:
    """Treat a mailing string that starts with the property address as the same address."""
    prop = _norm(property_address)
    mail = _norm(mailing_address)
    if not prop or not mail:
        return False
    return prop == mail or mail.startswith(prop + " ") or prop.startswith(mail + " ")


def strategy_score(record: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate a capped, explainable wholesale-priority score."""
    score = 0
    strong: List[str] = []
    supporting: List[str] = []
    risks: List[str] = []

    property_address = record.get("property_address")
    mailing = record.get("lowtax_mailing_address") or record.get("mailing_address")
    owner = _norm(record.get("lowtax_owner_of_record") or record.get("owner_name"))

    # 1. Tax-balance signal: one of the strongest observable public-record signals.
    tax_balance = _num(record.get("lowtax_current_account_balance"))
    fall_due = _num(record.get("lowtax_fall_balance_due"))
    spring_due = _num(record.get("lowtax_spring_balance_due"))
    if tax_balance > 0 or fall_due > 0 or spring_due > 0:
        score += 22
        strong.append("active public tax balance/delinquency signal")
    else:
        supporting.append("no current LowTaxInfo balance due")

    # 2. Absentee ownership, confirmed by the tax-record mailing location.
    mail_text = _norm(mailing)
    prop_text = _norm(property_address)
    if mail_text and prop_text and not _same_address(prop_text, mail_text):
        score += 18
        strong.append("mailing address differs from property address")

    # 3. Long hold.
    transfer_year = _year(record.get("last_transfer_date"))
    if transfer_year:
        years = max(0, date.today().year - transfer_year)
        if years >= 20:
            score += 15
            strong.append(f"{years}+ year ownership hold")
        elif years >= 15:
            score += 12
            strong.append(f"{years}+ year ownership hold")
        elif years >= 10:
            score += 7
            supporting.append(f"{years}+ year ownership hold")

    # 4. Low basis / equity proxy. Assessment is not market value, so language is explicit.
    sale = _num(record.get("last_sale_price"))
    land = _num(record.get("assessed_land_value"))
    improvement = _num(record.get("assessed_improvement_value"))
    assessed = land + improvement
    if sale > 0:
        if sale <= 75000:
            score += 9
            supporting.append("low recorded purchase basis")
        elif sale <= 125000:
            score += 5
            supporting.append("moderate recorded purchase basis")
        if assessed > sale * 2:
            score += 13
            strong.append("assessed value is >2x recorded sale price (equity proxy)")
        elif assessed > sale * 1.5:
            score += 8
            supporting.append("assessed value materially exceeds recorded sale price")
        elif assessed > sale:
            score += 4
            supporting.append("assessed value exceeds recorded sale price")

    # 5. Property-type fit.
    ptype = _norm(record.get("property_type"))
    if any(x in ptype for x in ("residential", "single family", "dwelling", "house")):
        score += 8
        supporting.append("residential property-type fit")

    # 6. Cross-source verification.
    if _norm(record.get("lowtax_match_status")) == "matched":
        score += 7
        supporting.append("GIS parcel matched to LowTaxInfo by parcel key")
    else:
        risks.append("LowTaxInfo parcel match not confirmed")

    # 7. Ownership structures can be useful research signals, but never treated as proof.
    if any(x in owner for x in ("trust", "estate", "llc", "inc", "corp")):
        score += 3
        supporting.append("non-simple individual ownership structure")

    # Challenge weak scores: do not let a pile of minor signals masquerade as a strong lead.
    strong_count = len(strong)
    if score >= 70 and strong_count < 2:
        score -= 12
        risks.append("high initial score lacked two strong independent signals; downgraded")
    if tax_balance <= 0 and not (mail_text and prop_text and not _same_address(prop_text, mail_text)) and transfer_year and date.today().year - transfer_year < 10:
        score -= 8
        risks.append("few strong motivation signals")

    score = max(0, min(100, int(score)))
    tier = "A" if score >= 75 else "B" if score >= 55 else "C"
    if score >= 75:
        action = "Priority research: verify ownership, taxes, liens, condition and contact path."
    elif score >= 55:
        action = "Secondary research: verify the strongest signal before outreach."
    else:
        action = "Low priority unless another source reveals a new motivation signal."

    return {
        "lead_score": score,
        "lead_tier": tier,
        "strategy_reasons": strong + supporting,
        "strategy_strong_signals": strong_count,
        "strategy_risk_flags": risks,
        "strategy_recommended_action": action,
        "strategy_model": "public-record wholesale prioritization v1",
    }


def apply_strategy(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for record in records:
        row = dict(record)
        row.update(strategy_score(row))
        output.append(row)
    output.sort(key=lambda x: (-_num(x.get("lead_score")), -_num(x.get("confidence")), str(x.get("property_address", ""))))
    return output
