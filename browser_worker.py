"""Self-hosted Chromium worker.

Run this on a Windows/Linux machine, VM, or small always-on server. It uses
Playwright/Chromium directly, so browser sessions do not consume Browser Use
Cloud credits.
"""
from __future__ import annotations

import base64
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright

app = FastAPI(title="Wholesale AI Browser Worker", version="0.1.0")


class Action(BaseModel):
    type: str
    selector: str | None = None
    value: str | None = None
    key: str | None = None
    milliseconds: int = 500
    attribute: str | None = None


class BrowseRequest(BaseModel):
    url: str
    actions: list[Action] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    wait_ms: int = 1000


def domain_allowed(url: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed)


def check_url(url: str, allowed: list[str]) -> None:
    if urlparse(url).scheme not in {"http", "https"}:
        raise HTTPException(400, "Only HTTP(S) URLs are allowed")
    if not domain_allowed(url, allowed):
        raise HTTPException(403, "Domain is not allowed")


def require_token(token: str | None) -> None:
    expected = os.getenv("BROWSER_WORKER_TOKEN")
    if not expected or not token or token != expected:
        raise HTTPException(401, "Invalid browser worker token")


@app.get("/health")
def health():
    return {"ok": True, "engine": "playwright-chromium", "self_hosted": True}


@app.post("/browse")
def browse(req: BrowseRequest, x_browser_token: str | None = Header(default=None)):
    require_token(x_browser_token)
    check_url(req.url, req.allowed_domains)
    results: list[dict] = []
    headless = os.getenv("BROWSER_HEADLESS", "1") != "0"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(req.url, wait_until="domcontentloaded", timeout=45000)
        if req.wait_ms:
            page.wait_for_timeout(min(req.wait_ms, 10000))

        for action in req.actions:
            typ = action.type.lower()
            if typ == "goto":
                check_url(action.value or "", req.allowed_domains)
                page.goto(action.value or "", wait_until="domcontentloaded", timeout=45000)
            elif typ == "click":
                page.locator(action.selector or "").first.click(timeout=15000)
            elif typ == "fill":
                page.locator(action.selector or "").first.fill(action.value or "")
            elif typ == "select":
                page.locator(action.selector or "").first.select_option(action.value or "")
            elif typ == "press":
                page.locator(action.selector or "").first.press(action.key or "Enter")
            elif typ == "scroll":
                page.mouse.wheel(0, 900)
            elif typ == "wait":
                page.wait_for_timeout(min(max(action.milliseconds, 0), 10000))
            elif typ == "extract_text":
                loc = page.locator(action.selector or "body").first
                results.append({"type": "text", "selector": action.selector or "body", "text": loc.inner_text(timeout=15000)})
            elif typ == "extract_attribute":
                loc = page.locator(action.selector or "").first
                results.append({"type": "attribute", "selector": action.selector, "attribute": action.attribute, "value": loc.get_attribute(action.attribute or "")})
            elif typ == "screenshot":
                raw = page.screenshot(full_page=True)
                results.append({"type": "screenshot", "base64": base64.b64encode(raw).decode("ascii")})
            else:
                raise HTTPException(400, f"Unsupported browser action: {action.type}")

        body = page.locator("body").inner_text(timeout=15000)
        current_url = page.url
        title = page.title()
        browser.close()

    return {"ok": True, "url": current_url, "title": title, "text": body, "results": results}
