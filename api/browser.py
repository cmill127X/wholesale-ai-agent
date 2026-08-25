"""Secure Vercel-side proxy to the self-hosted Chromium worker.

This keeps the worker token server-side. Set BROWSER_WORKER_URL and
BROWSER_WORKER_TOKEN in the Vercel project environment.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from browser_engine import browse, search_web

app = FastAPI(title="Wholesale AI Browser Proxy", version="1.0.0")


class BrowserRequest(BaseModel):
    url: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    wait_ms: int = 1000


class SearchRequest(BaseModel):
    query: str
    search_url: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)


def require_agent_key(x_agent_key: str | None) -> None:
    """Optional second layer for direct public calls to this proxy.

    If AGENT_BROWSER_API_KEY is configured, callers must supply it. The
    internal worker token remains separate and is never returned to callers.
    """
    import os

    expected = os.getenv("AGENT_BROWSER_API_KEY")
    if expected and x_agent_key != expected:
        raise HTTPException(401, "Invalid agent browser key")


@app.get("/health")
def health():
    return {"ok": True, "proxy": "self-hosted-browser"}


@app.post("/browse")
def run_browser(
    req: BrowserRequest,
    x_agent_key: str | None = Header(default=None),
):
    require_agent_key(x_agent_key)
    try:
        return browse(
            req.url,
            actions=req.actions,
            allowed_domains=req.allowed_domains,
            wait_ms=req.wait_ms,
        )
    except Exception as exc:
        raise HTTPException(502, f"Browser worker error: {exc}") from exc


@app.post("/search")
def search(
    req: SearchRequest,
    x_agent_key: str | None = Header(default=None),
):
    require_agent_key(x_agent_key)
    if not req.query.strip():
        raise HTTPException(400, "query is required")
    try:
        return search_web(
            req.query.strip(),
            search_url=req.search_url,
            allowed_domains=req.allowed_domains,
        )
    except Exception as exc:
        raise HTTPException(502, f"Browser worker error: {exc}") from exc
