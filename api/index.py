from __future__ import annotations
import csv, io, re
from datetime import datetime
from typing import Any, Dict
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from qc import second_pass
from sources.st_joseph_live import query_parcels_pool, to_canonical
from sources.st_joseph_lowtax import search_owner, find_matching_record, to_enrichment

app = FastAPI(title="Wholesale AI Agent", version="1.1.0")
FIELDS=["lead_score","lead_tier","verification_status","confidence","property_address","property_city","property_state","property_zip","owner_name","mailing_address","last_transfer_date","last_sale_price","property_type","acreage","assessed_land_value","assessed_improvement_value","parcel_id","lowtax_match_status","lowtax_owner_of_record","lowtax_mailing_address","lowtax_current_account_balance","lowtax_fall_balance_due","lowtax_fall_tax","lowtax_spring_balance_due","lowtax_spring_tax","lowtax_pay_year","lowtax_status","lowtax_tax_type","lowtax_photo","source","screening_reasons"]
class ChatRequest(BaseModel):
    message:str
    property:Dict[str,Any]=Field(default_factory=dict)

def num(v):
    try:return float(v or 0)
    except:return 0

def owner_search_name(owner:str)->str:
    """Use a narrow first+last search rather than a broad surname search."""
    parts=re.findall(r"[A-Za-z][A-Za-z'-]+", owner or "")
    return " ".join(parts[:2]) if len(parts)>=2 else (parts[0] if parts else "")

def enrich_lowtax(rows:list[dict[str,Any]], max_lookups:int=40)->dict[str,Any]:
    cache={}; lookups=0; matched=0
    for row in rows:
        owner=owner_search_name(str(row.get("owner_name") or "")); parcel=row.get("parcel_id")
        if not owner or not parcel: continue
        if owner not in cache:
            if lookups>=max_lookups: break
            try:
                payload=search_owner(owner,0)
                cache[owner]=list(payload.get("Results") or [])
            except Exception:
                cache[owner]=[]
            lookups+=1
        match=find_matching_record(cache[owner],parcel)
        if match:
            row.update(to_enrichment(match)); matched+=1
        else:
            row["lowtax_match_status"]="not_found"
    return {"lookups":lookups,"matched":matched,"cache_names":len(cache)}

def research_data(limit:int,city:str|None,sort:str="best",strategy:str="all",min_score:int=0,property_type:str="all",owner_type:str="all",min_years:int=0,tax_signal:str="all",absentee:str="all"):
    where="1=1"
    if city: where=f"PROP_CITY = '{city.replace(chr(39),chr(39)*2)}'"
    pool=max(200,min(1000,limit*10)); rows=query_parcels_pool(where=where,pages=(pool+199)//200,page_size=200)
    first=second_pass(to_canonical(rows)); candidates=list(first.get("leads",[]))
    candidates.sort(key=lambda x:(-num(x.get("lead_score")),-num(x.get("confidence")),x.get("property_address","")))
    enrichment=enrich_lowtax(candidates[:max(50,limit*2)])
    result=second_pass(candidates); leads=list(result.get("leads",[]))
    def ok(x):
        score=num(x.get("lead_score")); reasons=" ".join(x.get("screening_reasons") or []).lower()
        if score<min_score:return False
        if property_type!="all" and str(x.get("property_type","")).lower()!=property_type.lower():return False
        if owner_type!="all" and owner_type.lower() not in str(x.get("owner_name","")).lower():return False
        if absentee=="yes" and not any(k in reasons for k in ("absentee","mailing","different address")):return False
        if absentee=="no" and any(k in reasons for k in ("absentee","different address")):return False
        if tax_signal=="balance" and num(x.get("lowtax_current_account_balance"))<=0:return False
        if min_years:
            try:
                if datetime.now().year-int(str(x.get("last_transfer_date") or "")[:4])<min_years:return False
            except:return False
        if strategy=="hot" and score<80:return False
        if strategy=="equity" and not (x.get("last_sale_price") or x.get("assessed_improvement_value") or x.get("assessed_land_value")):return False
        if strategy=="longterm":
            try:
                if datetime.now().year-int(str(x.get("last_transfer_date") or "")[:4])<15:return False
            except:return False
        return True
    leads=[x for x in leads if ok(x)]
    key=(lambda x:(num(x.get("lead_score")),-num(x.get("confidence")),x.get("property_address",""))) if sort=="lowest" else (lambda x:(-num(x.get("lead_score")),-num(x.get("confidence")),x.get("property_address","")))
    leads.sort(key=key); result["leads"]=leads[:limit]
    result["screening"]={"pool_scanned":len(rows),"returned":len(result["leads"]),"sort":sort,"strategy":strategy,"lowtax":enrichment}
    return result

def csv_text(result):
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=FIELDS,extrasaction="ignore");w.writeheader()
    for x in result.get("leads",[]):
        r=dict(x);r["screening_reasons"]="; ".join(r.get("screening_reasons") or []);w.writerow(r)
    return out.getvalue()

HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wholesale AI Agent</title><style>body{margin:0;background:#f5f7fb;color:#172033;font-family:system-ui,-apple-system,Segoe UI,sans-serif}.wrap{max-width:1150px;margin:auto;padding:20px}.hero{background:linear-gradient(135deg,#172554,#2563eb);color:white;border-radius:20px;padding:24px}.brand{font-size:24px;font-weight:900}.muted{color:#667085}.hero .muted{color:#dbeafe}.controls{display:grid;grid-template-columns:1fr 110px 190px 120px;gap:8px;margin-top:16px}input,select,button{padding:11px;border-radius:9px;border:1px solid #d0d5dd;font:inherit}button{cursor:pointer;font-weight:750}.go{background:white;color:#2563eb;border:0}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.chip{background:#ffffff22;color:white;border:1px solid #ffffff55;border-radius:999px}.panel{background:white;border:1px solid #e5e7eb;border-radius:15px;padding:16px;margin-top:14px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.metric{background:white;border:1px solid #e5e7eb;border-radius:13px;padding:14px}.metric b{font-size:22px}.lead{background:white;border:1px solid #e5e7eb;border-radius:13px;padding:14px;margin-top:9px;cursor:pointer}.row{display:flex;justify-content:space-between;gap:10px}.score{font-weight:900;color:#2563eb;font-size:18px}.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.tag{background:#f2f4f7;border-radius:999px;padding:5px 8px;font-size:11px}.modal{display:none;position:fixed;inset:0;background:#0f172a99;padding:18px;z-index:10;overflow:auto}.modal.open{display:flex;align-items:center;justify-content:center}.card{background:white;width:min(960px,100%);max-height:92vh;overflow:auto;border-radius:18px;padding:20px}.details{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.detail{border:1px solid #e5e7eb;border-radius:9px;padding:10px}.detail b{display:block;font-size:10px;color:#667085;text-transform:uppercase;margin-bottom:3px}.chat{border-top:1px solid #e5e7eb;margin-top:18px;padding-top:14px}.msgs{height:210px;overflow:auto;background:#f8fafc;border-radius:10px;padding:9px}.msg{padding:8px 10px;border-radius:10px;margin:5px 0;font-size:13px}.user{background:#dbeafe;margin-left:15%}.ai{background:white;border:1px solid #e5e7eb;margin-right:15%}.chatrow{display:flex;gap:7px;margin-top:7px}.chatrow input{flex:1}.chatrow button{background:#2563eb;color:white;border:0}.close{float:right}@media(max-width:750px){.controls{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr 1fr}.details{grid-template-columns:1fr 1fr}}@media(max-width:500px){.controls{grid-template-columns:1fr}.details{grid-template-columns:1fr}.wrap{padding:12px}}</style></head><body><main class="wrap"><section class="hero"><div class="brand">Wholesale AI Agent</div><div class="muted">GIS → LowTaxInfo → 2-pass QC → ranked leads</div><div class="chips"><button class="chip" onclick="strategy='all';run()">All Leads</button><button class="chip" onclick="strategy='hot';run()">🔥 Hot Wholesale</button><button class="chip" onclick="strategy='equity';run()">💰 High Equity</button><button class="chip" onclick="strategy='longterm';run()">🏠 Long-Term</button></div><div class="controls"><input id="city" value="South Bend" placeholder="City"><select id="limit"><option>10</option><option selected>25</option><option>50</option><option>100</option></select><select id="sort"><option value="best">Best rated → lowest</option><option value="lowest">Lowest rated → highest</option></select><button class="go" onclick="run()">Run Research</button></div></section><section class="grid"><div class="metric"><span class="muted">Pipeline</span><br><b>2-pass QC</b></div><div class="metric"><span class="muted">Tax source</span><br><b>LowTaxInfo</b></div><div class="metric"><span class="muted">Mode</span><br><b>Zero-cost</b></div><div class="metric"><span class="muted">Output</span><br><b>Ranked</b></div></section><section class="panel"><b>Research results</b><p id="summary" class="muted">Run research, then click any property for the complete combined record.</p><div id="results">Nothing scanned yet.</div></section></main><div id="modal" class="modal"><div class="card"><button class="close" onclick="closeProp()">Close</button><h2 id="title"></h2><div id="details"></div><div class="chat"><b>Ask the Wholesale AI Agent</b><div id="msgs" class="msgs"><div class="msg ai">Ask me why this property ranked or what should be verified next.</div></div><div class="chatrow"><input id="q" placeholder="Ask about this property…" onkeydown="if(event.key==='Enter')ask()"><button onclick="ask()">Send</button></div></div></div></div><script>let strategy='all',current={};const e=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));const v=(x,k)=>x&&x[k]!=null&&String(x[k]).trim()?String(x[k]):'Not available';function card(x){return `<div class="lead" onclick='openProp(${JSON.stringify(x).replace(/'/g,'&#39;')})'><div class="row"><div><b>${e(v(x,'property_address'))}</b><div class="muted">${e(v(x,'owner_name'))}</div></div><div class="score">${e(v(x,'lead_score'))}/100</div></div><div class="tags"><span class="tag">${e(v(x,'property_type'))}</span><span class="tag">${e(v(x,'property_city'))}, ${e(v(x,'property_state'))} ${e(v(x,'property_zip'))}</span><span class="tag">Parcel ${e(v(x,'parcel_id'))}</span><span class="tag">Tax balance ${e(v(x,'lowtax_current_account_balance'))}</span><span class="tag">LowTax ${e(v(x,'lowtax_match_status'))}</span></div></div>`}function dc(a,b){return `<div class="detail"><b>${e(a)}</b>${e(b||'Not available')}</div>`}function openProp(x){current=x;document.getElementById('title').textContent=v(x,'property_address');const p=[['Property type',v(x,'property_type')],['Property address',v(x,'property_address')],['City',v(x,'property_city')],['State',v(x,'property_state')],['ZIP',v(x,'property_zip')],['Parcel ID',v(x,'parcel_id')],['Acreage',v(x,'acreage')]],o=[['Owner',v(x,'owner_name')],['LowTax owner',v(x,'lowtax_owner_of_record')],['Mailing address',v(x,'mailing_address')],['LowTax mailing',v(x,'lowtax_mailing_address')],['Last transfer date',v(x,'last_transfer_date')],['Last sale price',v(x,'last_sale_price')]],t=[['Current account balance',v(x,'lowtax_current_account_balance')],['Fall balance due',v(x,'lowtax_fall_balance_due')],['Fall tax',v(x,'lowtax_fall_tax')],['Spring balance due',v(x,'lowtax_spring_balance_due')],['Spring tax',v(x,'lowtax_spring_tax')],['Tax year',v(x,'lowtax_pay_year')],['Tax status',v(x,'lowtax_status')],['Tax type',v(x,'lowtax_tax_type')]],a=[['Assessed land value',v(x,'assessed_land_value')],['Assessed improvement value',v(x,'assessed_improvement_value')],['Lead score',v(x,'lead_score')],['Lead tier',v(x,'lead_tier')],['Verification',v(x,'verification_status')],['Confidence',v(x,'confidence')],['LowTax match',v(x,'lowtax_match_status')],['Source',v(x,'source')],['Screening reasons',(x.screening_reasons||[]).join('; ')||'Not available']];document.getElementById('details').innerHTML='<h3>Property</h3><div class="details">'+p.map(z=>dc(...z)).join('')+'</div><h3>Ownership & transaction</h3><div class="details">'+o.map(z=>dc(...z)).join('')+'</div><h3>Tax record</h3><div class="details">'+t.map(z=>dc(...z)).join('')+'</div><h3>Assessment & QC</h3><div class="details">'+a.map(z=>dc(...z)).join('')+'</div>';document.getElementById('msgs').innerHTML='<div class="msg ai">Ask me about this property.</div>';document.getElementById('modal').classList.add('open')}function closeProp(){document.getElementById('modal').classList.remove('open')}async function run(){const p=new URLSearchParams({city:document.getElementById('city').value,limit:document.getElementById('limit').value,sort:document.getElementById('sort').value,strategy});document.getElementById('results').textContent='Researching GIS + LowTaxInfo…';const r=await fetch('/api/research?'+p);const d=await r.json();document.getElementById('summary').textContent=`Scanned ${d.screening?.pool_scanned||0} GIS parcels; LowTaxInfo matched ${d.screening?.lowtax?.matched||0} records across ${d.screening?.lowtax?.lookups||0} owner searches; returned ${d.leads?.length||0} leads.`;document.getElementById('results').innerHTML=(d.leads||[]).map(card).join('')||'No matches.'}async function ask(){const q=document.getElementById('q'),m=q.value.trim();if(!m)return;const box=document.getElementById('msgs');box.innerHTML+=`<div class="msg user">${e(m)}</div>`;q.value='';const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,property:current})});const d=await r.json();box.innerHTML+=`<div class="msg ai">${e(d.reply)}</div>`;box.scrollTop=box.scrollHeight}</script></body></html>'''

@app.get('/',response_class=HTMLResponse)
def home(): return HTMLResponse(HTML)
@app.get('/health',response_class=PlainTextResponse)
def health(): return 'ok'
@app.get('/api/research')
def research(limit:int=Query(25,ge=1,le=100),city:str|None=None,sort:str='best',strategy:str='all',min_score:int=Query(0,ge=0,le=100),property_type:str='all',owner_type:str='all',min_years:int=Query(0,ge=0,le=100),tax_signal:str='all',absentee:str='all'):
    return research_data(limit,city,sort,strategy,min_score,property_type,owner_type,min_years,tax_signal,absentee)
@app.get('/api/export.csv')
def export_csv(limit:int=Query(25,ge=1,le=100),city:str|None=None,sort:str='best',strategy:str='all',min_score:int=0,property_type:str='all',owner_type:str='all',min_years:int=0,tax_signal:str='all',absentee:str='all'):
    r=research_data(limit,city,sort,strategy,min_score,property_type,owner_type,min_years,tax_signal,absentee);return StreamingResponse(io.BytesIO(csv_text(r).encode()),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=wholesale-leads.csv'})
@app.post('/api/chat')
def chat(req:ChatRequest):
    p=req.property or {};m=req.message.lower()
    if not p:return {'reply':'I can explain public-record signals, tax data, ranking, and verification steps.'}
    if any(k in m for k in ('why','rank','score')):reply=f"{p.get('property_address','This property')} is scored {p.get('lead_score','N/A')}/100. Reasons: {', '.join(p.get('screening_reasons') or []) or 'none recorded'}. This is a prioritization signal, not proof of seller motivation."
    elif any(k in m for k in ('tax','balance')):reply=f"LowTaxInfo match: {p.get('lowtax_match_status','N/A')}; current account balance: {p.get('lowtax_current_account_balance','N/A')}; fall balance: {p.get('lowtax_fall_balance_due','N/A')}; spring balance: {p.get('lowtax_spring_balance_due','N/A')}; tax year: {p.get('lowtax_pay_year','N/A')}."
    elif any(k in m for k in ('owner','ownership','history','transfer')):reply=f"Owner: {p.get('owner_name','N/A')}; LowTax owner: {p.get('lowtax_owner_of_record','N/A')}; last transfer: {p.get('last_transfer_date','N/A')}; parcel ID: {p.get('parcel_id','N/A')}. Verify deed history separately."
    else:reply=f"Property type: {p.get('property_type','N/A')}; location: {p.get('property_city','N/A')}, {p.get('property_state','N/A')} {p.get('property_zip','N/A')}; parcel ID: {p.get('parcel_id','N/A')}. Ask about ranking, taxes, ownership, or next verification steps."
    return {'reply':reply}
