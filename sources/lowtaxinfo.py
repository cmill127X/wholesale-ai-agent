"""LowTaxInfo St. Joseph County adapter using the public property-search response."""
from __future__ import annotations
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Dict, List, Optional

BASE_URL = "https://lowtaxinfo.com/lti-api/LowMobileTaxData.svc/api/PropertySearch"


def _clean_name(name: str) -> str:
    # LowTaxInfo's search is name-based. Use a compact owner-name query.
    value = re.sub(r"\s+", " ", str(name or "")).strip()
    return value[:120]


def search_owner(name: str, page_number: int = 0) -> Dict[str, Any]:
    query = _clean_name(name)
    params = {"CorpCode": "SJC", "name": query, "page_number": page_number}
    request = Request(
        BASE_URL + "?" + urlencode(params),
        headers={"User-Agent": "wholesale-ai-agent/1.0", "Accept": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected LowTaxInfo response")
    return payload


def _norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def _address(row: Dict[str, Any]) -> str:
    return " ".join(
        x for x in (
            row.get("PropertyAddress1"),
            row.get("PropertyCity"),
            row.get("PropertyState"),
            row.get("PropertyZipCode"),
        ) if x
    )


def find_match(payload: Dict[str, Any], parcel_id: str = "", property_address: str = "") -> Optional[Dict[str, Any]]:
    target_parcel = _norm(parcel_id)
    target_addr = _norm(property_address)
    rows = payload.get("Results") or []
    if target_parcel:
        for row in rows:
            if _norm(row.get("StateKey")) == target_parcel or _norm(row.get("UnformattedStateKey")) == target_parcel:
                return row
    if target_addr:
        for row in rows:
            if _norm(_address(row)).find(target_addr) >= 0 or target_addr.find(_norm(_address(row))) >= 0:
                return row
    return None


def to_canonical(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lowtax_owner_name": row.get("OwnerOfRecord", ""),
        "lowtax_mailing_address": " ".join(filter(None, [row.get("MailingAddress1"), row.get("MailingAddress2"), row.get("MailingCity"), row.get("MailingState"), row.get("MailingZipCode")])),
        "lowtax_property_address": _address(row),
        "lowtax_property_city": row.get("PropertyCity", ""),
        "lowtax_property_state": row.get("PropertyState", ""),
        "lowtax_property_zip": row.get("PropertyZipCode", ""),
        "lowtax_parcel_id": row.get("StateKey", "") or row.get("UnformattedStateKey", ""),
        "lowtax_current_account_balance": row.get("CurrentAccountBalance", 0),
        "lowtax_fall_balance_due": row.get("FallBalanceDue", 0),
        "lowtax_fall_tax": row.get("FallTax", 0),
        "lowtax_spring_balance_due": row.get("SpringBalanceDue", 0),
        "lowtax_spring_tax": row.get("SpringTax", 0),
        "lowtax_pay_year": row.get("PayYear", ""),
        "lowtax_duplicate_number": row.get("DuplicateNumber", ""),
        "lowtax_photo": row.get("Photo", ""),
        "lowtax_status": row.get("Status", ""),
        "lowtax_tax_type": row.get("TaxType", ""),
        "lowtax_source": "St. Joseph County LowTaxInfo",
    }


def enrich_property(record: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort enrichment of one GIS record from LowTaxInfo.

    Search is owner-name based, so exact parcel/address matching is required before
    merging data. Failures are intentionally non-fatal so GIS remains the baseline.
    """
    owner = str(record.get("owner_name") or "").strip()
    if not owner:
        return record
    try:
        # Query the most identifying first token(s). The API returns a paginated
        # result set; exact parcel matching prevents unrelated records from merging.
        parts = owner.split()
        query = " ".join(parts[:2]) if len(parts) > 1 else owner
        payload = search_owner(query, 0)
        match = find_match(payload, record.get("parcel_id", ""), record.get("property_address", ""))
        if match:
            record.update(to_canonical(match))
            record["lowtax_verified_match"] = True
            record["source"] = (record.get("source", "") + " + LowTaxInfo").strip(" +")
            if not record.get("owner_name") and match.get("OwnerOfRecord"):
                record["owner_name"] = match["OwnerOfRecord"]
        else:
            record["lowtax_verified_match"] = False
    except Exception as exc:
        record["lowtax_verified_match"] = False
        record["lowtax_error"] = str(exc)
    return record
