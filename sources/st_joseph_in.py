"""Source profile for St. Joseph County, Indiana public property research.

This module deliberately does not scrape a website by guessing undocumented
endpoints. It defines attributable source metadata and evidence requirements;
connectors can be added when an approved/public endpoint is identified.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SourceProfile:
    name: str
    url: str
    authority: str
    fields: List[str]


SOURCES = [
    SourceProfile(
        name="SJC Regional GIS / Parcel Layer",
        url="https://www.sjcindiana.gov/1443/Data-Extract-Search-Information",
        authority="St. Joseph County Assessor / GIS",
        fields=["parcel_id", "property_address", "parcel_attributes"],
    ),
    SourceProfile(
        name="SJC Assessment Neighborhood Map",
        url="https://www.sjcindiana.gov/1649/Assessment-Neighborhood-Map",
        authority="St. Joseph County Assessor",
        fields=["parcel_id", "property_address", "property_record_card"],
    ),
    SourceProfile(
        name="SJC Land Records Search",
        url="https://www.sjcindiana.gov/412/Land-Records-Search",
        authority="St. Joseph County Recorder",
        fields=["deed", "mortgage", "lien", "recorded_instrument"],
    ),
    SourceProfile(
        name="SJC Auditor",
        url="https://www.sjcindiana.gov/auditor",
        authority="St. Joseph County Auditor",
        fields=["owner_of_record", "transfer", "parcel_status"],
    ),
]


def source_catalog() -> List[Dict[str, object]]:
    return [
        {"name": s.name, "url": s.url, "authority": s.authority, "fields": s.fields}
        for s in SOURCES
    ]
