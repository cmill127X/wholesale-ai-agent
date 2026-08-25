"""St. Joseph County LowTaxInfo public API adapter.

The endpoint returns paginated JSON records from LowTaxInfo. We use the
owner-name search as the discovery mechanism and join records back to GIS
parcels using StateKey/UnformattedStateKey when possible.

The adapter keeps a small process-local cache so repeated research runs do
not re-query the same owner names during a warm server instance.
"""
from __future__ import annotations
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Dict, List, Optional

from sources.browser_agent import search_lowtax_with_browser

BASE_URL = "https://lowtaxinfo.com/lti-api/LowMobileTaxData.svc/api/PropertySearch"
CORP_CODE = "SJC"
CACHE_TTL_SECONDS = 15 * 60
_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _get(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"User-Agent": "wholesale-ai-agent/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("LowTaxInfo returned a non-object response")
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload


def _browser_payload(name: str, page_number: int) -> Dict[str, Any]:
    """Fallback to Browser Use when the deterministic LowTaxInfo request fails."""
    if page_number != 0:
        return {"CurrentPage": 0, "MaxPage": 0, "RecordCount": 0, "Results": []}
    records = search_lowtax_with_browser(name)
    results: List[Dict[str, Any]] = []
    for r in records:
        results.append({
            "OwnerOfRecord": r.get("owner_of_record"),
            "PropertyAddress1": r.get("property_address"),
            "PropertyCity": r.get("property_city"),
            "PropertyState": r.get("property_state"),
            "PropertyZipCode": r.get("property_zip"),
            "MailingAddress1": r.get("mailing_address"),
            "CurrentAccountBalance": r.get("current_account_balance"),
            "FallBalanceDue": r.get("fall_balance_due"),
            "FallTax": r.get("fall_tax"),
            "SpringBalanceDue": r.get("spring_balance_due"),
            "SpringTax": r.get("spring_tax"),
            "PayYear": r.get("pay_year"),
            "Status": r.get("status"),
            "TaxType": r.get("tax_type"),
            "DuplicateNumber": r.get("duplicate_number"),
            "StateKey": r.get("parcel_id"),
            "UnformattedStateKey": _norm_key(r.get("parcel_id")),
        })
    return {"CurrentPage": 0, "MaxPage": 0, "RecordCount": len(results), "Results": results}


def search_owner(name: str, page_number: int = 0) -> Dict[str, Any]:
    """Search LowTaxInfo by owner-name text with a short-lived warm cache.

    Direct HTTP is the fast path. Browser Use Cloud is used only if that
    deterministic request fails, so normal research stays fast and cheap.
    """
    key = f"{name.strip().lower()}|{page_number}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    params = {"CorpCode": CORP_CODE, "name": name, "page_number": page_number}
    try:
        payload = _get(BASE_URL + "?" + urlencode(params))
    except Exception:
        payload = _browser_payload(name, page_number)
    _CACHE[key] = (now, payload)
    # Bound memory while retaining the most useful recent lookups.
    if len(_CACHE) > 250:
        oldest = sorted(_CACHE.items(), key=lambda item: item[1][0])[:50]
        for old_key, _ in oldest:
            _CACHE.pop(old_key, None)
    return payload


def search_owner_all_pages(name: str, max_pages: int = 90) -> List[Dict[str, Any]]:
    """Return all available records for an owner-name search, bounded by max_pages."""
    first = search_owner(name, 0)
    results = list(first.get("Results") or [])
    max_page = int(first.get("MaxPage") or 0)
    for page in range(1, min(max_page, max_pages - 1) + 1):
        payload = search_owner(name, page)
        batch = list(payload.get("Results") or [])
        results.extend(batch)
        if not batch:
            break
    return results


def _norm_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isalnum()).upper()


def find_matching_record(records: List[Dict[str, Any]], parcel_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Prefer exact parcel-key matches, then exact unformatted key matches."""
    target = _norm_key(parcel_id)
    if not target:
        return None
    for row in records:
        if _norm_key(row.get("StateKey")) == target or _norm_key(row.get("UnformattedStateKey")) == target:
            return row
    return None


def to_enrichment(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map LowTaxInfo fields into the canonical enrichment namespace."""
    mailing = " ".join(filter(None, [
        row.get("MailingAddress1"), row.get("MailingCity"),
        row.get("MailingState"), row.get("MailingZipCode"),
    ]))
    return {
        "lowtax_owner_of_record": row.get("OwnerOfRecord"),
        "lowtax_mailing_address": mailing,
        "lowtax_current_account_balance": row.get("CurrentAccountBalance"),
        "lowtax_fall_balance_due": row.get("FallBalanceDue"),
        "lowtax_fall_tax": row.get("FallTax"),
        "lowtax_spring_balance_due": row.get("SpringBalanceDue"),
        "lowtax_spring_tax": row.get("SpringTax"),
        "lowtax_pay_year": row.get("PayYear"),
        "lowtax_status": row.get("Status"),
        "lowtax_tax_type": row.get("TaxType"),
        "lowtax_duplicate_number": row.get("DuplicateNumber"),
        "lowtax_photo": row.get("Photo"),
        "lowtax_state_key": row.get("StateKey"),
        "lowtax_source": BASE_URL,
        "lowtax_match_status": "matched",
    }
