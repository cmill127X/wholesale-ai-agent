"""Browser engine abstraction for the nationwide research agent.

The production API can talk to a self-hosted browser worker through
BROWSER_WORKER_URL. If no worker is configured, callers can continue using
Browser Use Cloud as a fallback. This keeps browser execution independent of
Vercel/serverless limitations and avoids cloud browser credits for normal use.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class BrowserEngineError(RuntimeError):
    pass


def local_browser_available() -> bool:
    return bool(os.getenv("BROWSER_WORKER_URL"))


def browse(
    url: str,
    *,
    actions: Optional[List[Dict[str, Any]]] = None,
    allowed_domains: Optional[List[str]] = None,
    wait_ms: int = 1000,
    timeout_s: float = 45.0,
) -> Dict[str, Any]:
    """Run deterministic browser actions on the self-hosted browser worker.

    Actions are intentionally structured rather than arbitrary code. Supported
    actions are: click, fill, select, press, scroll, wait, extract_text,
    extract_attribute, screenshot, and goto.
    """
    worker = os.getenv("BROWSER_WORKER_URL")
    if not worker:
        raise BrowserEngineError("BROWSER_WORKER_URL is not configured")

    payload = {
        "url": url,
        "actions": actions or [],
        "allowed_domains": allowed_domains or [],
        "wait_ms": max(0, min(wait_ms, 10000)),
    }
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(worker.rstrip("/") + "/browse", json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        raise BrowserEngineError(str(exc)) from exc


def search_web(
    query: str,
    *,
    search_url: str | None = None,
    allowed_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Use the self-hosted browser to run a public web search.

    A configurable search URL keeps the browser engine provider-neutral.
    """
    url = search_url or os.getenv("BROWSER_SEARCH_URL", "https://www.google.com/search")
    sep = "&" if "?" in url else "?"
    return browse(
        f"{url}{sep}q={query.replace(' ', '+')}",
        allowed_domains=allowed_domains,
        actions=[{"type": "extract_text", "selector": "body"}],
    )
