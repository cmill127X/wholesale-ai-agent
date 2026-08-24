"""Vercel entrypoint for the Wholesale AI Agent."""
from typing import Any, Dict, List
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from qc import second_pass
from sources.st_joseph_live import query_parcels, to_canonical

app = FastAPI(title="Wholesale AI Agent", version="0.2.0")

class RunRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)

@app.get("/", response_class=HTMLResponse)
def landing():
    return """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Wholesale AI Agent</title><style>body{font-family:system-ui;max-width:850px;margin:40px auto;padding:0 20px}button,a{font-size:16px;padding:12px 16px;margin:6px 6px 6px 0;border-radius:8px;border:1px solid #ccc;background:#fff;text-decoration:none;color:#111} .card{padding:20px;border:1px solid #ddd;border-radius:12px;margin:18px 0}code{background:#f3f3f3;padding:2px 5px}</style></head>
    <body><h1>Wholesale AI Agent</h1><p><b>Status:</b> online</p>
    <div class='card'><h2>Live St. Joseph County test</h2><p>Pull a small public parcel sample, rank it with transparent screening signals, then run two-pass QC.</p>
    <a href='/api/live-leads?limit=25'>Run 25 live leads</a><a href='/api/live-leads?limit=25&city=South%20Bend'>South Bend sample</a></div>
    <div class='card'><b>API:</b> <code>/api</code> &nbsp; <b>Manual QC:</b> <code>POST /api/run</code> &nbsp; <b>Live research:</b> <code>GET /api/live-leads</code></div>
    </body></html>"""

@app.get("/api")
def home():
    return {"service": "Wholesale AI Agent", "status": "online", "pipeline": "public parcel research -> normalize -> rank -> second-pass QC"}

@app.post("/api/run")
def run(request: RunRequest):
    return {"status": "ok", "result": second_pass(request.records)}

@app.get("/api/live-leads")
def live_leads(limit: int = Query(25, ge=1, le=100), city: str | None = Query(None, max_length=40)):
    """Fetch a bounded live parcel sample and run it through the full QC pipeline."""
    try:
        where = "1=1"
        if city:
            safe_city = city.replace("'", "''")
            where = f"PROP_CITY = '{safe_city}'"
        rows = query_parcels(where=where, limit=limit)
        records = to_canonical(rows)
        result = second_pass(records)
        return {
            "status": "ok",
            "source": "South Bend/St. Joseph County public ArcGIS parcel layer",
            "query": {"city": city, "limit": limit},
            "result": result,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "hint": "The public GIS service may be temporarily unavailable."}
