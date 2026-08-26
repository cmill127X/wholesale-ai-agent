# Browser Research Worker

This worker is the browser layer for the Wholesale AI Agent.

It is intentionally separate from the Vercel API because browser processes should not run inside the Vercel request handler.

## Purpose

Use Browser Use to perform deep research on sites such as LowTaxInfo, St. Joseph County GIS, and MyCase when direct API adapters are unavailable or insufficient.

## Setup

Python 3.11+ is required by Browser Use. Install:

```bash
pip install browser-use
```

Set an LLM/provider key and, if using Browser Use Cloud, `BROWSER_USE_API_KEY`.

## Contract

Input: a JSON research task containing property/parcel identifiers and allowed source URLs.

Output: normalized JSON with source observations, raw evidence snippets, timestamps, and confidence. The main agent should never treat browser observations as verified until they pass the same second-pass QC used by API data.

## Guardrails

- Only browse the explicitly configured property-research sources.
- Do not submit forms, make payments, create accounts, or contact owners.
- Do not bypass CAPTCHAs, authentication, robots controls, or access restrictions.
- Preserve source URL and observed timestamp for every extracted fact.
- Prefer parcel ID matching over address-only matching.
