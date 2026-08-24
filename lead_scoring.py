"""Transparent wholesale lead scoring.

This is a screening score, not a claim that a property is a good investment.
It rewards observable, evidence-backed signals and penalizes missing data.
"""
from typing import Any, Dict


def score_wholesale_candidate(record: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    signals = []
    penalties = []

    if record.get("property_address"):
        score += 10
        signals.append("property address present")
    else:
        penalties.append("missing property address")

    if record.get("owner_name"):
        score += 10
        signals.append("owner identified")
    else:
        penalties.append("missing owner")

    if record.get("mailing_address"):
        score += 10
        signals.append("mailing address present")

    if record.get("mailing_differs_from_property") is True:
        score += 20
        signals.append("possible absentee owner")

    if record.get("long_hold") is True:
        score += 15
        signals.append("long hold")

    if record.get("equity_signal") is True:
        score += 15
        signals.append("equity signal")

    if record.get("distress_signal") is True:
        score += 15
        signals.append("distress signal")

    if record.get("source"):
        score += 5
    else:
        penalties.append("missing source")

    score = max(0, min(score, 100))
    tier = "A" if score >= 75 else "B" if score >= 55 else "C"
    return {"score": score, "tier": tier, "signals": signals, "penalties": penalties}
