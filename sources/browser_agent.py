"""Browser research adapters.

The agent prefers the self-hosted Playwright browser worker when configured.
Browser Use Cloud remains an optional fallback for tasks that need it.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from browser_engine import BrowserEngineError, browse, local_browser_available


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


def _local_lowtax_search(owner_name: str, parcel_id: str | None = None) -> List[Dict[str, Any]]:
    """Run a LowTaxInfo browser visit through the self-hosted worker."""
    if not local_browser_available():
        return []
    data = browse(
        "https://lowtaxinfo.com/",
        allowed_domains=["lowtaxinfo.com", "www.lowtaxinfo.com"],
        actions=[{"type": "extract_text", "selector": "body"}],
    )
    # Keep raw browser evidence for a site-specific connector to parse. Never
    # fabricate a structured tax record from unverified text.
    if data.get("text"):
        return [{
            "browser_text": data["text"],
            "query_owner": owner_name,
            "query_parcel": parcel_id,
            "source": "self_hosted_browser",
        }]
    return []


def search_lowtax_with_browser(owner_name: str, parcel_id: str | None = None) -> List[Dict[str, Any]]:
    """Search LowTaxInfo using self-hosted browser first, cloud second."""
    if local_browser_available():
        try:
            result = _local_lowtax_search(owner_name, parcel_id)
            if result:
                return result
        except Exception:
            pass

    if not os.getenv("BROWSER_USE_API_KEY"):
        return []

    from browser_use_sdk.v3 import AsyncBrowserUse

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


def general_browser_research(
    url: str,
    *,
    actions: List[Dict[str, Any]] | None = None,
    allowed_domains: List[str] | None = None,
) -> Dict[str, Any]:
    """Generic browser entry point for nationwide source research."""
    if not local_browser_available():
        raise BrowserEngineError("Self-hosted browser worker is not configured")
    return browse(url, actions=actions, allowed_domains=allowed_domains)
