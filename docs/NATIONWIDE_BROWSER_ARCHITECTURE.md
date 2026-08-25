# Nationwide Browser Architecture

The wholesale agent is designed as a source-agnostic research system. LowTaxInfo, GIS, MyCase, assessor portals, recorder systems, sheriff-sale sites, and other sources are connectors—not hard-coded limits.

## Browser layers

1. **Direct source adapters** — fastest and most reliable when a structured public endpoint exists.
2. **Self-hosted browser worker** — Playwright + Chromium, running outside Vercel. Normal browser execution uses no Browser Use Cloud credits.
3. **Browser Use Cloud fallback** — retained for tasks where the self-hosted worker is unavailable or a future browser-agent capability is useful.

## Production flow

`Research request -> source discovery -> direct adapters -> self-hosted browser -> extraction -> cross-source QC -> lead scoring`

The browser worker accepts structured, auditable actions and an optional domain allow-list. It can navigate public websites, fill forms, click controls, select options, paginate/scroll, extract text/attributes, and capture screenshots.

## Why the browser is separate from Vercel

Vercel serverless functions are not the right place to keep a full Chromium runtime alive. The worker is therefore a separate process that can run on a Windows PC, Linux machine, VM, or small always-on server. The Vercel API talks to it through `BROWSER_WORKER_URL`.

## Local setup

```bash
pip install -r requirements-browser.txt
playwright install chromium
uvicorn browser_worker:app --host 0.0.0.0 --port 8787
```

Set the API environment variable:

`BROWSER_WORKER_URL=http://<browser-worker-host>:8787`

For a same-machine development setup, use `http://127.0.0.1:8787`.

## Safety

The worker does not execute arbitrary code supplied by a web page or user. Navigation can be restricted with `allowed_domains`. CAPTCHA, login, or other access-control pages should be surfaced for human handling rather than bypassed.

## Nationwide expansion

New counties/states should add source adapters and source manifests as they are discovered. The browser layer remains generic, so the core agent does not need to be rewritten for every county portal.
