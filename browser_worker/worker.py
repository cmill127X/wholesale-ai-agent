from __future__ import annotations
import asyncio
import json
import os
from typing import Any

from browser_use import Agent, ChatBrowserUse

ALLOWED_SOURCES = {
    "lowtaxinfo": "https://www.lowtaxinfo.com/",
    "st_joseph_gis": "https://sjc-gis.stjosephcountyindiana.com/",
    "mycase": "https://mycase.in.gov/",
}

async def deep_research(task: dict[str, Any]) -> dict[str, Any]:
    parcel_id = str(task.get("parcel_id") or "")
    address = str(task.get("property_address") or "")
    owner = str(task.get("owner_name") or "")
    sources = [s for s in task.get("sources", ALLOWED_SOURCES) if s in ALLOWED_SOURCES]
    urls = [ALLOWED_SOURCES[s] for s in sources]
    prompt = f"""
Research this real-estate property using only the supplied public research sources.
Parcel ID: {parcel_id}
Property address: {address}
Owner: {owner}
Allowed source URLs: {', '.join(urls)}

For each source, collect only publicly displayed property/legal/tax facts relevant to the parcel.
Prefer exact parcel-ID matches. If a fact cannot be verified, return null rather than guessing.
Return JSON with: observations (list), source_evidence (list with source, url, fact, observed_at),
verification_warnings (list), and confidence (0-1).
Do not submit forms, contact anyone, create accounts, make payments, bypass authentication/CAPTCHAs,
or circumvent access controls.
"""
    llm = ChatBrowserUse(model=os.getenv("BROWSER_USE_MODEL", "openai/gpt-5.5"))
    agent = Agent(task=prompt, llm=llm)
    history = await agent.run()
    # Browser Use histories are intentionally kept as evidence for the caller;
    # the main pipeline still performs normalization and second-pass QC.
    return {"parcel_id": parcel_id, "address": address, "sources": sources, "history": history.model_dump() if hasattr(history, "model_dump") else str(history)}

if __name__ == "__main__":
    task = json.loads(os.environ.get("BROWSER_RESEARCH_TASK", "{}"))
    print(json.dumps(asyncio.run(deep_research(task)), default=str))
