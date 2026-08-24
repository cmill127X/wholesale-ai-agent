"""St. Joseph County parcel query configuration.

The county documents a Simple Query Builder over its Parcel Layer for property
analysis. This module keeps query definitions separate from transport so we can
plug in an approved export/API/browser adapter later.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class QueryPreset:
    name: str
    purpose: str
    fields: List[str]
    filters: Dict[str, str]


WHOLESALE_PRESETS = [
    QueryPreset(
        name="absentee_owner",
        purpose="Prioritize properties where mailing and property addresses differ.",
        fields=["parcel_id", "property_address", "owner_name", "mailing_address"],
        filters={"mailing_differs_from_property": "true"},
    ),
    QueryPreset(
        name="long_hold",
        purpose="Find properties suitable for equity/long-hold screening once transfer data is available.",
        fields=["parcel_id", "property_address", "owner_name", "last_transfer_date", "last_sale_price"],
        filters={"last_transfer_before_year": "2016"},
    ),
    QueryPreset(
        name="data_quality",
        purpose="Pull the minimum fields required for downstream verification.",
        fields=["parcel_id", "property_address", "owner_name", "mailing_address", "last_transfer_date", "last_sale_price"],
        filters={},
    ),
]


def build_query(preset: QueryPreset) -> Dict[str, object]:
    """Return a transport-neutral query description."""
    return {"layer": "Parcel", "fields": preset.fields, "filters": preset.filters}


def all_queries() -> List[Dict[str, object]]:
    return [build_query(p) for p in WHOLESALE_PRESETS]


if __name__ == "__main__":
    for query in all_queries():
        print(query)
