"""Live St. Joseph County parcel reader.

Uses the public South Bend/St. Joseph County ArcGIS parcel layer. The service
supports query operations and exposes parcel, owner mailing, transfer, sale,
tax, property-type and acreage fields.

No API key is required by this adapter. It uses only Python's standard library.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Dict, List

SERVICE_URL = (
    "https://gis.southbendin.gov/arcgis/rest/services/"
    "LandRecords/Parcels/MapServer/1/query"
)

DEFAULT_FIELDS = [
    "PARCELID", "NAME_1", "MAILINGADD", "MAILINGCIT", "MAILINGSTA", "MAILINGZIP",
    "PROP_ADDR", "PROP_CITY", "PROP_STATE", "PROP_ZIP", "TRANSFERDA", "TRANSFERRE",
    "SALESDATE", "SALESPRICE", "ACREAGE", "PROPTYPE", "PARCELSTAT", "TAXTYPE",
    "TAXUNIT", "PAYYEAR", "REALLANDVA", "REALIMPROV", "TNETTAX", "PARCPRC",
    "TOWNSHIP", "TaxInfoURL", "PAYTAXURL"
]


def query_parcels(where: str = "1=1", limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch one page of parcel attributes from the public county layer."""
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    params = {
        "where": where,
        "outFields": ",".join(DEFAULT_FIELDS),
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": limit,
        "f": "json",
    }
    request = Request(
        SERVICE_URL + "?" + urlencode(params),
        headers={"User-Agent": "wholesale-ai-agent/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return [feature.get("attributes", {}) for feature in payload.get("features", [])]


def to_canonical(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map county fields into the agent's canonical lead schema."""
    output = []
    for row in rows:
        output.append({
            "property_address": row.get("PROP_ADDR", ""),
            "owner_name": row.get("NAME_1", ""),
            "mailing_address": " ".join(filter(None, [
                row.get("MAILINGADD", ""), row.get("MAILINGCIT", ""),
                row.get("MAILINGSTA", ""), row.get("MAILINGZIP", ""),
            ])),
            "last_transfer_date": row.get("TRANSFERDA", "") or row.get("SALESDATE", ""),
            "last_sale_price": row.get("SALESPRICE", ""),
            "source": "St. Joseph County / South Bend public parcel GIS",
            "parcel_id": row.get("PARCELID", ""),
            "property_type": row.get("PROPTYPE", ""),
            "acreage": row.get("ACREAGE", ""),
            "assessed_land_value": row.get("REALLANDVA", ""),
            "assessed_improvement_value": row.get("REALIMPROV", ""),
            "tax_type": row.get("TAXTYPE", ""),
            "tax_unit": row.get("TAXUNIT", ""),
            "tax_info_url": row.get("TaxInfoURL", ""),
            "tax_payment_url": row.get("PAYTAXURL", ""),
        })
    return output


if __name__ == "__main__":
    rows = query_parcels(limit=10)
    print(json.dumps(to_canonical(rows), indent=2, default=str))
