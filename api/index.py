"""Vercel entrypoint for the Wholesale AI Agent."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from qc import second_pass
from sources.st_joseph_live import query_parcels, to_canonical

app = FastAPI(title="Wholesale AI Agent", version="0.4.0")

class RunRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)

REPORT_FIELDS = [
    "lead_score", "lead_tier", "verification_status", "confidence",
    "property_address", "property_city", "property_state", "property_zip",
    "owner_name", "mailing_address", "last_transfer_date", "last_sale_price",
    "property_type", "acreage", "assessed_land_value", "assessed_improvement_value",
    "parcel_id", "source", "screening_reasons",
]


def _live_result(limit: int, city: str | None) -> Dict[str, Any]:
    where = "1=1"
    if city:
        safe_city = city.replace("'", "''")
        where = f"PROP_CITY = '{safe_city}'"
    rows = query_parcels(where=where, limit=limit)
    return second_pass(to_canonical(rows))


def _csv_text(result: Dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=REPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for lead in result.get("leads", []):
        row = dict(lead)
        row["screening_reasons"] = "; ".join(row.get("screening_reasons") or [])
        writer.writerow(row)
    return output.getvalue()


@app.get("/", response_class=HTMLResponse)
def landing():
    return """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Wholesale AI Agent</title><style>
    body{font-family:system-ui,-apple-system,sans-serif;max-width:980px;margin:0 auto;padding:36px 20px;color:#111}
    .hero{padding:28px 0}.eyebrow{font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
    h1{font-size:42px;line-height:1.05;margin:10px 0}.sub{font-size:19px;line-height:1.5;max-width:720px;color:#555}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:24px 0}
    .card{padding:22px;border:1px solid #ddd;border-radius:14px;background:#fff}.card h2,.card h3{margin-top:0}
    a.btn{display:inline-block;font-size:16px;font-weight:650;padding:12px 16px;margin:6px 8px 6px 0;border-radius:9px;border:1px solid #222;background:#111;color:#fff;text-decoration:none}
    a.btn.secondary{background:#fff;color:#111;border-color:#bbb}.muted{color:#666}.price{font-size:28px;font-weight:750}.small{font-size:13px;color:#666}
    ul{padding-left:20px;line-height:1.7}.note{font-size:13px;color:#666;margin-top:18px}
    </style></head><body>
    <section class='hero'><div class='eyebrow'>Wholesale AI Agent</div><h1>Find better real-estate leads without doing the research by hand.</h1>
    <p class='sub'>Public parcel data is screened, normalized, ranked, and quality-checked so investors can spend more time contacting owners and less time building spreadsheets.</p>
    <a class='btn' href='/api/live-leads?limit=25'>Run 25-lead sample</a><a class='btn secondary' href='/api/report.csv?limit=25'>Download sample CSV</a></section>
    <div class='grid'><div class='card'><h3>Research</h3><p>Pulls a bounded sample from the public St. Joseph County parcel layer.</p></div>
    <div class='card'><h3>Rank</h3><p>Scores transparent signals such as absentee ownership, long hold periods, recorded sale price, and assessed value.</p></div>
    <div class='card'><h3>QC</h3><p>Deduplicates records and runs a second quality-control pass before delivery.</p></div></div>
    <div class='card'><h2>Simple service model</h2><div class='grid'><div><div class='price'>Free sample</div><p>25 leads from one target market.</p></div><div><div class='price'>$49</div><p>Example starting price for a larger custom lead report. Pricing can change after testing demand.</p></div><div><div class='price'>Custom</div><p>Recurring market-specific research and reporting.</p></div></div>
    <p class='small'>No payment is collected on this development site. The pricing above is a product-testing placeholder.</p></div>
    <p class='note'>Public-record screening signals are not proof that an owner is distressed, motivated, or willing to sell. Verify important facts independently before contacting an owner or making an offer.</p>
    </body></html>"""


@app.get("/api")
def home():
    return {"service": "Wholesale AI Agent", "status": "online", "pipeline": "public parcel research -> normalize -> rank -> second-pass QC -> CSV report"}


@app.post("/api/run")
def run(request: RunRequest):
    return {"status": "ok", "result": second_pass(request.records)}


@app.get("/api/live-leads")
def live_leads(limit: int = Query(25, ge=1, le=100), city: str | None = Query(None, max_length=40)):
    try:
        return {"status": "ok", "source": "South Bend/St. Joseph County public ArcGIS parcel layer", "query": {"city": city, "limit": limit}, "result": _live_result(limit, city)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "hint": "The public GIS service may be temporarily unavailable."}


@app.get("/api/report.csv")
def report_csv(limit: int = Query(25, ge=1, le=100), city: str | None = Query(None, max_length=40)):
    try:
        result = _live_result(limit, city)
        content = _csv_text(result)
        filename = f"wholesale_leads_{(city or 'st_joseph_county').lower().replace(' ', '_')}_{limit}.csv"
        return StreamingResponse(io.BytesIO(content.encode("utf-8")), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as exc:
        return PlainTextResponse(f"Report generation failed: {exc}", status_code=502)
