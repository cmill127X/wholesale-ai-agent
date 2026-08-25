"""Live St. Joseph County parcel reader using the public ArcGIS layer."""
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Dict, List

SERVICE_URL = "https://gis.southbendin.gov/arcgis/rest/services/LandRecords/Parcels/MapServer/1/query"
DEFAULT_FIELDS = [
    "OBJECTID", "PARCELID", "NAME_1", "MAILINGADD", "MAILINGCIT", "MAILINGSTA", "MAILINGZIP",
    "PROP_ADDR", "PROP_CITY", "PROP_STATE", "PROP_ZIP", "TRANSFERDA", "TRANSFERRE",
    "SALESDATE", "SALESPRICE", "ACREAGE", "PROPTYPE", "PARCELSTAT", "TAXTYPE",
    "TAXUNIT", "PAYYEAR", "REALLANDVA", "REALIMPROV", "TNETTAX", "PARCPRC",
    "TOWNSHIP", "TaxInfoURL", "PAYTAXURL"
]

def query_parcels(where: str = "1=1", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch one page of parcel attributes from the public county layer."""
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    params = {"where": where, "outFields": ",".join(DEFAULT_FIELDS), "returnGeometry": "false", "resultOffset": offset, "resultRecordCount": limit, "orderByFields": "OBJECTID ASC", "f": "json"}
    request = Request(SERVICE_URL + "?" + urlencode(params), headers={"User-Agent": "wholesale-ai-agent/1.0"})
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return [feature.get("attributes", {}) for feature in payload.get("features", [])]

def query_parcels_pool(where: str = "1=1", pages: int = 5, page_size: int = 200) -> List[Dict[str, Any]]:
    """Fetch a bounded pool using concurrent page requests to reduce wall-clock latency."""
    if pages < 1 or pages > 5 or page_size < 1 or page_size > 1000:
        raise ValueError("pages must be 1-5 and page_size must be 1-1000")
    offsets = [page * page_size for page in range(pages)]
    batches = []
    with ThreadPoolExecutor(max_workers=min(5, pages)) as pool:
        futures = {pool.submit(query_parcels, where, page_size, offset): offset for offset in offsets}
        for future in as_completed(futures):
            batches.append((futures[future], future.result()))
    rows: List[Dict[str, Any]] = []
    for _, batch in sorted(batches, key=lambda item: item[0]):
        rows.extend(batch)
        if len(batch) < page_size:
            break
    return rows

def to_canonical(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for row in rows:
        output.append({
            "property_address": row.get("PROP_ADDR", ""), "owner_name": row.get("NAME_1", ""),
            "mailing_address": " ".join(filter(None, [row.get("MAILINGADD", ""), row.get("MAILINGCIT", ""), row.get("MAILINGSTA", ""), row.get("MAILINGZIP", "")])),
            "last_transfer_date": row.get("TRANSFERDA", "") or row.get("SALESDATE", ""), "last_sale_price": row.get("SALESPRICE", ""),
            "source": "St. Joseph County / South Bend public parcel GIS", "parcel_id": row.get("PARCELID", ""), "property_type": row.get("PROPTYPE", ""),
            "property_city": row.get("PROP_CITY", ""), "property_state": row.get("PROP_STATE", ""), "property_zip": row.get("PROP_ZIP", ""),
            "mailing_city": row.get("MAILINGCIT", ""), "mailing_state": row.get("MAILINGSTA", ""), "mailing_zip": row.get("MAILINGZIP", ""),
            "acreage": row.get("ACREAGE", ""), "assessed_land_value": row.get("REALLANDVA", ""), "assessed_improvement_value": row.get("REALIMPROV", ""),
            "tax_type": row.get("TAXTYPE", ""), "tax_unit": row.get("TAXUNIT", ""), "parcel_status": row.get("PARCELSTAT", ""),
            "tax_info_url": row.get("TaxInfoURL", ""), "tax_payment_url": row.get("PAYTAXURL", ""),
        })
    return output

if __name__ == "__main__":
    print(json.dumps(to_canonical(query_parcels(limit=10)), indent=2, default=str))
