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

app = FastAPI(title="Wholesale AI Agent", version="0.3.0")

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
    <title>Wholesale AI Agent</title><style>body{font-family:system-ui;max-width:900px;margin:40px auto;padding:0 20px}button,a{font-size:16px;padding:12px 16px;margin:6px 6px 6px 0;border-radius:8px;border:1px solid #ccc;background:#fff;text-decoration:none;color:#111} .card{padding:20px;border:1px solid #ddd;border-radius:12px;margin:18px 0}code{background:#f3f3f3;padding:2px 5px}</style></head>
    <body><h1>Wholesale AI Agent</h1><p><b>Status:</b> online</p>
    <div class='card'><h2>Live St. Joseph County research</h2><p>Pull a bounded public parcel sample, rank it with transparent screening signals, run two-pass QC, and export a clean lead report.</p>
    <a href='/api/live-leads?limit=25'>View 25 live leads</a><a href='/api/report.csv?limit=25'>Download 25-lead CSV</a><a href='/api/live-leads?limit=25&city=South%20Bend'>South Bend sample</a></div>
    <div class='card'><b>API:</b> <code>/api</code> &nbsp; <b>Manual QC:</b> <code>POST /api/run</code> &nbsp; <b>Live research:</b> <code>GET /api/live-leads</code> &nbsp; <b>CSV:</b> <code>GET /api/report.csv</code></div>
    </body></html>"""


@app.get("/api")
def home():
    return {"service": "Wholesale AI Agent", "status": "online", "pipeline": "public parcel research -> normalize -> rank -> second-pass QC -> CSV report"}


@app.post("/api/run")
def run(request: RunRequest):
    return {"status": "ok", "result": second_pass(request.records)}


@app.get("/api/live-leads")
def live_leads(limit: int = Query(25, ge=1, le=100), city: str | None = Query(None, max_length=40)):
    """Fetch a bounded live parcel sample and run it through the full QC pipeline."""
    try:
        return {"status": "ok", "source": "South Bend/St. Joseph County public ArcGIS parcel layer", "query": {"city": city, "limit": limit}, "result": _live_result(limit, city)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "hint": "The public GIS service may be temporarily unavailable."}


@app.get("/api/report.csv")
def report_csv(limit: int = Query(25, ge=1, le=100), city: str | None = Query(None, max_length=40)):
    """Generate a downloadable CSV report from live public parcel research."""
    try:
        result = _live_result(limit, city)
        content = _csv_text(result)
        filename = f"wholesale_leads_{(city or 'st_joseph_county').lower().replace(' ', '_')}_{limit}.csv"
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        return PlainTextResponse(f"Report generation failed: {exc}", status_code=502)
