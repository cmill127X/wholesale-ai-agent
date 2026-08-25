"""Browser Use Cloud fallback for web research.

The direct GIS/LowTaxInfo adapters remain the fast path. This module is used
only when a deterministic source fails or when a task explicitly needs a
browser-capable researcher.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from browser_use_sdk.v3 import AsyncBrowserUse


class TaxRecord(BaseModel):
    owner_of_record: str | None = None
    property_address: str | None = None
    property_city: str | None = None
    property_state: str | None = None
    property_zip: str | None = None
    parcel_id: str | None = None
    mailing_address: str | None = None
    current_account_balance: float | None = None
    fall_balance_due: float | None = None
    fall_tax: float | None = None
    spring_balance_due: float | None = None
    spring_tax: float | None = None
    pay_year: int | None = None
    status: str | None = None
    tax_type: str | None = None
    duplicate_number: int | None = None


class TaxSearchResult(BaseModel):
    records: List[TaxRecord] = Field(default_factory=list)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def search_lowtax_with_browser(owner_name: str, parcel_id: str | None = None) -> List[Dict[str, Any]]:
    """Use Browser Use Cloud to search LowTaxInfo when the direct API is unavailable."""
    if not os.getenv("BROWSER_USE_API_KEY"):
        return []

    parcel_hint = f" and parcel ID {parcel_id}" if parcel_id else ""
    task = f"""
Go to https://lowtaxinfo.com/ and use the public property/tax search.
Search for owner: {owner_name}{parcel_hint}.
Return the matching St. Joseph County, Indiana property tax record(s).
Use the site's own displayed data. Do not guess or invent values.
Return only records that you can verify from the page.
"""

    async def execute() -> List[Dict[str, Any]]:
        client = AsyncBrowserUse()
        result = await client.run(
            task,
            output_schema=TaxSearchResult,
            allowed_domains=["lowtaxinfo.com", "www.lowtaxinfo.com"],
            flash_mode=True,
        )
        return [r.model_dump() for r in result.output.records]

    try:
        return _run(execute())
    except Exception:
        return []
