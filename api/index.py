from __future__ import annotations
import csv, io, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from qc import second_pass
from sources.st_joseph_live import query_parcels_pool, to_canonical
from sources.st_joseph_lowtax import search_owner, find_matching_record, to_enrichment

app=FastAPI(title='Wholesale AI Agent',version='1.2.0')
FIELDS=['lead_score','lead_tier','verification_status','confidence','property_address','property_city','property_state','property_zip','owner_name','mailing_address','last_transfer_date','last_sale_price','property_type','acreage','assessed_land_value','assessed_improvement_value','parcel_id','lowtax_match_status','lowtax_owner_of_record','lowtax_mailing_address','lowtax_current_account_balance','lowtax_fall_balance_due','lowtax_fall_tax','lowtax_spring_balance_due','lowtax_spring_tax','lowtax_pay_year','lowtax_status','lowtax_tax_type','lowtax_photo','source','screening_reasons']
_CACHE:dict[tuple,tuple[float,dict]]={}
class ChatRequest(BaseModel):
    message:str
    property:Dict[str,Any]=Field(default_factory=dict)

def num(v):
    try:return float(v or 0)
    except:return 0

def owner_name(v):
    p=re.findall(r"[A-Za-z][A-Za-z'-]+",str(v or ''))
    return ' '.join(p[:2]) if len(p)>=2 else (p[0] if p else '')

def enrich(rows,limit):
    jobs={}
    for r in rows:
        o=owner_name(r.get('owner_name')); pid=r.get('parcel_id')
        if o and pid and o not in jobs and len(jobs)<limit: jobs[o]=1
    cache={}
    with ThreadPoolExecutor(max_workers=min(8,max(1,len(jobs)))) as pool:
        fs={pool.submit(search_owner,o,0):o for o in jobs}
        for f in as_completed(fs):
            o=fs[f]
            try:cache[o]=list(f.result().get('Results') or [])
            except Exception:cache[o]=[]
    matched=0
    for r in rows:
        m=find_matching_record(cache.get(owner_name(r.get('owner_name')),[]),r.get('parcel_id'))
        if m:r.update(to_enrichment(m));matched+=1
        else:r['lowtax_match_status']='not_found'
    return {'lookups':len(jobs),'matched':matched}

def research_data(limit,city,sort='best',strategy='all'):
    key=(limit,city,sort,strategy);now=time.time();hit=_CACHE.get(key)
    if hit and now-hit[0]<60:return hit[1]
    pool_size=max(100,min(400,limit*8))
    where=f"PROP_CITY = '{city.replace(chr(39),chr(39)*2)}'" if city else '1=1'
    rows=query_parcels_pool(where=where,pages=(pool_size+199)//200,page_size=200)
    candidates=list(second_pass(to_canonical(rows)).get('leads',[]))
    candidates.sort(key=lambda x:(-num(x.get('lead_score')),-num(x.get('confidence')),x.get('property_address','')))
    enrichment=enrich(candidates[:max(limit,8)],min(12,max(limit,8)))
    leads=list(second_pass(candidates).get('leads',[]))
    def ok(x):
        s=num(x.get('lead_score'))
        if strategy=='hot' and s<80:return False
        if strategy=='equity' and not (x.get('last_sale_price') or x.get('assessed_improvement_value') or x.get('assessed_land_value')):return False
        if strategy=='longterm':
            try:
                if datetime.now().year-int(str(x.get('last_transfer_date') or '')[:4])<15:return False
            except:return False
        return True
    leads=[x for x in leads if ok(x)]
    if sort=='lowest':leads.sort(key=lambda x:(num(x.get('lead_score')),-num(x.get('confidence')),x.get('property_address','')))
    else:leads.sort(key=lambda x:(-num(x.get('lead_score')),-num(x.get('confidence')),x.get('property_address','')))
    out={'leads':leads[:limit],'screening':{'pool_scanned':len(rows),'returned':min(limit,len(leads)),'sort':sort,'strategy':strategy,'lowtax':enrichment}}
    _CACHE[key]=(now,out);return out

def csv_text(r):
    o=io.StringIO();w=csv.DictWriter(o,fieldnames=FIELDS,extrasaction='ignore');w.writeheader()
    for x in r.get('leads',[]):
        x=dict(x);x['screening_reasons']='; '.join(x.get('screening_reasons') or []);w.writerow(x)
    return o.getvalue()

HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wholesale AI Agent</title><style>body{margin:0;background:#f5f7fb;color:#172033;font-family:system-ui,-apple-system,Segoe UI,sans-serif}.wrap{max-width:1100px;margin:auto;padding:18px}.hero{background:linear-gradient(135deg,#172554,#2563eb);color:white;border-radius:18px;padding:22px}.brand{font-size:24px;font-weight:900}.muted{color:#667085}.hero .muted{color:#dbeafe}.controls{display:grid;grid-template-columns:1fr 90px 180px 120px;gap:8px;margin-top:14px}input,select,button{padding:11px;border-radius:9px;border:1px solid #d0d5dd;font:inherit}button{cursor:pointer;font-weight:700}.go{background:white;color:#2563eb;border:0}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.chip{background:#ffffff22;color:white;border:1px solid #ffffff55;border-radius:999px}.panel{background:white;border:1px solid #e5e7eb;border-radius:14px;padding:15px;margin-top:13px}.lead{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:13px;margin-top:8px;cursor:pointer}.row{display:flex;justify-content:space-between;gap:10px}.score{font-weight:900;color:#2563eb}.tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.tag{background:#f2f4f7;border-radius:999px;padding:4px 7px;font-size:11px}.modal{display:none;position:fixed;inset:0;background:#0f172a99;padding:15px;z-index:5;overflow:auto}.modal.open{display:flex;align-items:center;justify-content:center}.card{background:white;width:min(900px,100%);max-height:92vh;overflow:auto;border-radius:16px;padding:18px}.details{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.detail{border:1px solid #e5e7eb;border-radius:8px;padding:9px}.detail b{display:block;font-size:10px;color:#667085;text-transform:uppercase;margin-bottom:3px}.chat{border-top:1px solid #e5e7eb;margin-top:16px;padding-top:12px}.msgs{height:180px;overflow:auto;background:#f8fafc;border-radius:9px;padding:8px}.msg{padding:7px 9px;border-radius:9px;margin:4px 0;font-size:13px}.user{background:#dbeafe;margin-left:15%}.ai{background:white;border:1px solid #e5e7eb;margin-right:15%}.chatrow{display:flex;gap:6px;margin-top:6px}.chatrow input{flex:1}.chatrow button{background:#2563eb;color:white;border:0}.close{float:right}@media(max-width:700px){.controls{grid-template-columns:1fr 1fr}.details{grid-template-columns:1fr 1fr}}@media(max-width:480px){.controls{grid-template-columns:1fr}.details{grid-template-columns:1fr}}</style></head><body><main class="wrap"><section class="hero"><div class="brand">Wholesale AI Agent</div><div class="muted">GIS → LowTaxInfo → 2-pass QC → ranked leads</div><div class="chips"><button class="chip" onclick="strategy='all';run()">All</button><button class="chip" onclick="strategy='hot';run()">🔥 Hot</button><button class="chip" onclick="strategy='equity';run()">💰 Equity</button><button class="chip" onclick="strategy='longterm';run()">🏠 Long-Term</button></div><div class="controls"><input id="city" value="South Bend" placeholder="City"><select id="limit"><option selected>10</option><option>25</option><option>50</option><option>100</option></select><select id="sort"><option value="best">Best → lowest</option><option value="lowest">Lowest → highest</option></select><button class="go" onclick="run()">Run Research</button></div></section><section class="panel"><b>Research results</b><p id="summary" class="muted">Ready.</p><div id="results">Nothing scanned yet.</div></section></main><div id="modal" class="modal"><div class="card"><button class="close" onclick="closeProp()">Close</button><h2 id="title"></h2><div id="details"></div><div class="chat"><b>Ask the Wholesale AI Agent</b><div id="msgs" class="msgs"><div class="msg ai">Ask why this property ranked or what to verify.</div></div><div class="chatrow"><input id="q" placeholder="Ask about this property…" onkeydown="if(event.key==='Enter')ask()"><button onclick="ask()">Send</button></div></div></div></div><script>let strategy='all',current={};const e=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));const v=(x,k)=>x&&x[k]!=null&&String(x[k]).trim()?String(x[k]):'Not available';function card(x){return `<div class="lead" onclick='openProp(${JSON.stringify(x).replace(/'/g,'&#39;')})'><div class="row"><div><b>${e(v(x,'property_address'))}</b><div class="muted">${e(v(x,'owner_name'))}</div></div><div class="score">${e(v(x,'lead_score'))}/100</div></div><div class="tags"><span class="tag">${e(v(x,'property_type'))}</span><span class="tag">${e(v(x,'property_city'))}</span><span class="tag">Parcel ${e(v(x,'parcel_id'))}</span><span class="tag">Tax ${e(v(x,'lowtax_current_account_balance'))}</span><span class="tag">LowTax ${e(v(x,'lowtax_match_status'))}</span></div></div>`}function dc(a,b){return `<div class="detail"><b>${e(a)}</b>${e(b||'Not available')}</div>`}function openProp(x){current=x;document.getElementById('title').textContent=v(x,'property_address');let g=[['Property',[['Type',v(x,'property_type')],['Address',v(x,'property_address')],['City',v(x,'property_city')],['State',v(x,'property_state')],['ZIP',v(x,'property_zip')],['Parcel',v(x,'parcel_id')]]],['Ownership',[['Owner',v(x,'owner_name')],['LowTax owner',v(x,'lowtax_owner_of_record')],['Mailing',v(x,'mailing_address')],['LowTax mailing',v(x,'lowtax_mailing_address')],['Last transfer',v(x,'last_transfer_date')],['Last sale',v(x,'last_sale_price')]]],['Tax',[['Current',v(x,'lowtax_current_account_balance')],['Fall due',v(x,'lowtax_fall_balance_due')],['Spring due',v(x,'lowtax_spring_balance_due')],['Tax year',v(x,'lowtax_pay_year')],['Status',v(x,'lowtax_status')],['Match',v(x,'lowtax_match_status')]]],['QC',[['Score',v(x,'lead_score')],['Tier',v(x,'lead_tier')],['Verification',v(x,'verification_status')],['Confidence',v(x,'confidence')],['Land value',v(x,'assessed_land_value')],['Improvement',v(x,'assessed_improvement_value')]]]];document.getElementById('details').innerHTML=g.map(z=>`<h3>${z[0]}</h3><div class="details">${z[1].map(q=>dc(...q)).join('')}</div>`).join('');document.getElementById('modal').classList.add('open')}function closeProp(){document.getElementById('modal').classList.remove('open')}async function run(){let p=new URLSearchParams({city:city.value,limit:limit.value,sort:sort.value,strategy});results.textContent='Researching…';let t=performance.now(),r=await fetch('/api/research?'+p),d=await r.json();summary.textContent=`${d.screening?.pool_scanned||0} parcels • ${d.screening?.lowtax?.matched||0}/${d.screening?.lowtax?.lookups||0} tax matches • ${((performance.now()-t)/1000).toFixed(1)}s`;results.innerHTML=(d.leads||[]).map(card).join('')||'No matches.'}async function ask(){let q=document.getElementById('q'),m=q.value.trim();if(!m)return;let b=document.getElementById('msgs');b.innerHTML+=`<div class="msg user">${e(m)}</div>`;q.value='';let r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,property:current})});let d=await r.json();b.innerHTML+=`<div class="msg ai">${e(d.reply)}</div>`;b.scrollTop=b.scrollHeight}</script></body></html>'''

@app.get('/',response_class=HTMLResponse)
def home():return HTMLResponse(HTML)
@app.get('/health',response_class=PlainTextResponse)
def health():return 'ok'
@app.get('/api/research')
def research(limit:int=Query(10,ge=1,le=100),city:str|None=None,sort:str='best',strategy:str='all'):return research_data(limit,city or '',sort,strategy)
@app.get('/api/export.csv')
def export_csv(limit:int=Query(10,ge=1,le=100),city:str|None=None,sort:str='best',strategy:str='all'):
    return StreamingResponse(io.BytesIO(csv_text(research_data(limit,city or '',sort,strategy)).encode()),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=wholesale-leads.csv'})
@app.post('/api/chat')
def chat(req:ChatRequest):
    p=req.property or {};m=req.message.lower()
    if not p:return {'reply':'Ask about ranking, taxes, ownership, or verification.'}
    if any(k in m for k in ('why','rank','score')):reply=f"{p.get('property_address','This property')} scored {p.get('lead_score','N/A')}/100. Reasons: {', '.join(p.get('screening_reasons') or []) or 'none recorded'}. This is a prioritization signal, not proof of motivation."
    elif any(k in m for k in ('tax','balance')):reply=f"LowTax match: {p.get('lowtax_match_status','N/A')}; current balance: {p.get('lowtax_current_account_balance','N/A')}; fall due: {p.get('lowtax_fall_balance_due','N/A')}; spring due: {p.get('lowtax_spring_balance_due','N/A')}."
    elif any(k in m for k in ('owner','ownership','history','transfer')):reply=f"Owner: {p.get('owner_name','N/A')}; LowTax owner: {p.get('lowtax_owner_of_record','N/A')}; last transfer: {p.get('last_transfer_date','N/A')}; parcel: {p.get('parcel_id','N/A')}."
    else:reply=f"Type: {p.get('property_type','N/A')}; location: {p.get('property_city','N/A')}, {p.get('property_state','N/A')}; parcel: {p.get('parcel_id','N/A')}."
    return {'reply':reply}
