"""Vercel entrypoint for the Wholesale AI Agent."""
from __future__ import annotations
import csv
import io
import json
from typing import Any, Dict, List
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from qc import second_pass
from sources.st_joseph_live import query_parcels_pool, to_canonical

app = FastAPI(title="Wholesale AI Agent", version="0.6.0")

class RunRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)

REPORT_FIELDS = ["lead_score", "lead_tier", "verification_status", "confidence", "property_address", "property_city", "property_state", "property_zip", "owner_name", "mailing_address", "last_transfer_date", "last_sale_price", "property_type", "acreage", "assessed_land_value", "assessed_improvement_value", "parcel_id", "source", "screening_reasons"]


def _live_result(limit: int, city: str | None) -> Dict[str, Any]:
    where = "1=1"
    if city:
        safe_city = city.replace("'", "''")
        where = f"PROP_CITY = '{safe_city}'"
    pool_size = max(200, min(1000, limit * 10))
    pages = (pool_size + 199) // 200
    rows = query_parcels_pool(where=where, pages=pages, page_size=200)
    result = second_pass(to_canonical(rows))
    result["screening"] = {"pool_scanned": len(rows), "returned": min(limit, len(result.get("leads", []))), "method": "rank full bounded pool, then return top leads"}
    result["leads"] = result.get("leads", [])[:limit]
    return result


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
    return """<!doctype html>
<html lang='en'><head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Wholesale AI Agent</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#172033;--muted:#667085;--line:#e5e7eb;--accent:#2563eb;--accent2:#1d4ed8;--good:#087443;--warn:#a15c00;--shadow:0 12px 35px rgba(16,24,40,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:1100px;margin:auto;padding:28px 18px 60px}.top{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:28px}.brand{display:flex;align-items:center;gap:12px}.logo{width:42px;height:42px;border-radius:12px;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:800;box-shadow:0 8px 18px rgba(37,99,235,.25)}h1{font-size:24px;margin:0}.sub{color:var(--muted);font-size:13px;margin-top:3px}.status{display:flex;align-items:center;gap:7px;padding:8px 12px;border:1px solid #cfead9;background:#f0fdf4;color:var(--good);border-radius:999px;font-size:13px;font-weight:700}.dot{width:8px;height:8px;border-radius:50%;background:#16a34a}.hero{background:linear-gradient(135deg,#172554,#2563eb);color:#fff;border-radius:22px;padding:30px;box-shadow:var(--shadow);margin-bottom:20px}.hero h2{font-size:32px;line-height:1.1;margin:0 0 9px}.hero p{max-width:700px;margin:0;color:#dbeafe;line-height:1.55}.controls{margin-top:24px;display:grid;grid-template-columns:1fr 160px auto;gap:10px}.input,.select{width:100%;padding:13px 14px;border-radius:11px;border:1px solid rgba(255,255,255,.25);background:#fff;color:var(--ink);font-size:15px}.btn{border:0;border-radius:11px;padding:13px 18px;font-weight:800;cursor:pointer;background:#fff;color:var(--accent2);font-size:15px}.btn:hover{transform:translateY(-1px)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.metric,.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 5px 18px rgba(16,24,40,.04)}.metric{padding:18px}.metric .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}.metric .num{font-size:25px;font-weight:800;margin-top:5px}.panel{padding:20px}.panel h3{margin:0 0 4px;font-size:18px}.panel p{color:var(--muted);margin:0 0 16px;font-size:13px}.actions{display:flex;gap:8px;flex-wrap:wrap}.secondary{display:inline-block;text-decoration:none;color:var(--ink);background:#fff;border:1px solid var(--line);padding:10px 13px;border-radius:10px;font-weight:700;font-size:14px}.results{margin-top:18px}.lead{border:1px solid var(--line);border-radius:14px;padding:16px;margin-top:10px;background:#fff}.leadhead{display:flex;justify-content:space-between;gap:10px}.address{font-weight:800}.owner{color:var(--muted);font-size:13px;margin-top:3px}.score{font-weight:900;color:var(--accent);font-size:18px}.meta{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.tag{font-size:12px;padding:5px 8px;border-radius:999px;background:#f2f4f7;color:#475467}.reasons{color:#475467;font-size:12px;margin-top:10px;line-height:1.5}.empty{color:var(--muted);padding:20px 0}.foot{color:#98a2b3;text-align:center;font-size:12px;margin-top:28px}@media(max-width:720px){.top{align-items:flex-start}.status{display:none}.hero{padding:23px;border-radius:18px}.hero h2{font-size:27px}.controls{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}.leadhead{align-items:flex-start}.wrap{padding:20px 14px 45px}}
</style></head>
<body><main class='wrap'>
<header class='top'><div class='brand'><div class='logo'>W</div><div><h1>Wholesale AI Agent</h1><div class='sub'>Research • Verify • Score • QC</div></div></div><div class='status'><span class='dot'></span> System online</div></header>
<section class='hero'><h2>Find better wholesale leads.</h2><p>Scan public parcel data, rank the opportunity signals, and run a second-pass quality check before a lead reaches your list.</p><div class='controls'><input id='city' class='input' value='South Bend' placeholder='City (optional)'><select id='limit' class='select'><option value='10'>Top 10</option><option value='25' selected>Top 25</option><option value='50'>Top 50</option><option value='100'>Top 100</option></select><button class='btn' onclick='runSearch()'>Run Research</button></div></section>
<section class='grid'><div class='metric'><div class='label'>Pipeline</div><div class='num'>2-pass QC</div></div><div class='metric'><div class='label'>Source</div><div class='num'>Public GIS</div></div><div class='metric'><div class='label'>Mode</div><div class='num'>Zero-cost</div></div><div class='metric'><div class='label'>Output</div><div class='num'>Ranked</div></div></section>
<section class='panel'><h3>Quick access</h3><p>Run a fresh screen or download the current ranked report.</p><div class='actions'><a class='secondary' href='/api/live-leads?limit=25&city=South%20Bend'>View API results</a><a class='secondary' href='/api/report.csv?limit=25&city=South%20Bend'>Download CSV</a><a class='secondary' href='/api'>System status</a></div></section>
<section class='panel results'><h3>Research results</h3><p id='summary'>Run research to see ranked properties.</p><div id='results'><div class='empty'>Nothing scanned yet.</div></div></section>
<div class='foot'>Wholesale AI Agent • public-data screening only • every lead requires verification</div>
</main>
<script>
function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}
async function runSearch(){const city=document.getElementById('city').value.trim();const limit=document.getElementById('limit').value;const summary=document.getElementById('summary');const box=document.getElementById('results');summary.textContent='Scanning public parcel data and running QC…';box.innerHTML='<div class="empty">Research in progress…</div>';let url='/api/live-leads?limit='+encodeURIComponent(limit)+(city?'&city='+encodeURIComponent(city):'');try{const r=await fetch(url);const data=await r.json();if(data.status!=='ok')throw new Error(data.error||'Research failed');const result=data.result||{};const leads=result.leads||[];summary.textContent=`Scanned ${result.screening?.pool_scanned??0} records • returned ${leads.length} ranked leads`;if(!leads.length){box.innerHTML='<div class="empty">No ranked leads returned.</div>';return}box.innerHTML=leads.map((x,i)=>`<article class="lead"><div class="leadhead"><div><div class="address">${i+1}. ${esc(x.property_address||'Unknown address')}</div><div class="owner">${esc(x.owner_name||'Unknown owner')}</div></div><div class="score">${esc(x.lead_score??0)}/100</div></div><div class="meta"><span class="tag">Tier ${esc(x.lead_tier||'C')}</span><span class="tag">${esc(x.verification_status||'unverified')}</span>${x.last_transfer_date?`<span class="tag">Transfer ${esc(x.last_transfer_date)}</span>`:''}${x.property_type?`<span class="tag">${esc(x.property_type)}</span>`:''}</div><div class="reasons">${esc((x.screening_reasons||[]).join(' • ')||'No screening reasons recorded.')}</div></article>`).join('')}catch(e){summary.textContent='Research failed';box.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}}
</script></body></html>"""

@app.get("/api")
def home():
    return {"service": "Wholesale AI Agent", "status": "online", "pipeline": "public parcel research -> larger pool -> rank -> second-pass QC -> CSV report"}

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
