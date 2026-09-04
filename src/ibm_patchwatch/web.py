from __future__ import annotations

import base64
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/mrAibo/CM_Discovery/"
    "main/data/ibm/catalog.json"
)

HTML = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IBM Update Checker</title><link rel="stylesheet" href="/styles.css"><script src="/app.js" defer></script></head>
<body><header><h1>IBM Update Checker</h1><p id="host">Loading inventory...</p></header>
<section id="summary" aria-live="polite"></section>
<table><thead><tr><th>Product</th><th>Installed</th><th>Available</th><th>Status</th><th>IBM resources</th></tr></thead><tbody id="products"></tbody></table>
<p id="error" role="alert"></p></body></html>"""

CSS = b"""body{font:16px system-ui,sans-serif;max-width:1200px;margin:auto;padding:1rem;color:#161616}table{border-collapse:collapse;width:100%}th,td{border:1px solid #aaa;padding:.55rem;text-align:left;vertical-align:top}a{margin-right:.7rem}.CURRENT{color:#087830}.UPDATE_AVAILABLE{color:#b34b00}.NEWER_THAN_CATALOG,.CHECK_REQUIRED,.NOT_SUPPORTED{color:#a2191f}#summary{margin:1rem 0;padding:.7rem;background:#f4f4f4}#error{color:#a2191f}@media(max-width:700px){table,thead,tbody,tr,th,td{display:block}thead{display:none}tr{margin-bottom:1rem}td:before{content:attr(data-label);display:block;font-weight:700}}"""

JS_TEMPLATE = r'''"use strict";
const CATALOG_URL=__CATALOG_URL__;
const labels={CURRENT:"Current",UPDATE_AVAILABLE:"Update available",NEWER_THAN_CATALOG:"Newer than catalog",CHECK_REQUIRED:"Check required",NOT_SUPPORTED:"Not supported"};
const nums=v=>{const m=String(v||"").match(/\d+/g);return m?m.map(Number):null};
function cmp(a,b){a=nums(a);b=nums(b);if(!a||!b)return null;for(let i=0;i<Math.max(a.length,b.length);i++){const d=(a[i]||0)-(b[i]||0);if(d)return d>0?1:-1}return 0}
function numeric(installed,available){const c=cmp(installed.version,available.version);return c===null?"CHECK_REQUIRED":c<0?"UPDATE_AVAILABLE":c>0?"NEWER_THAN_CATALOG":"CURRENT"}
function compare(id,i,e){if(e.support_status==="not_supported")return "NOT_SUPPORTED";const a=e.available;if(!a||!a.version)return "CHECK_REQUIRED";
 if(["content_manager","websphere","ibm_java"].includes(id))return numeric(i,a);
 if(id==="content_navigator"){const v=cmp(i.version,a.version);if(v===null)return "CHECK_REQUIRED";if(v<0)return "UPDATE_AVAILABLE";if(v>0)return "NEWER_THAN_CATALOG";const m=String(i.build_level||"").match(/icn\d+\.(\d{3})\./i),x=m?Number(m[1]):null,y=a.interim_fix==null?null:Number(a.interim_fix);if(x===null||y===null||!Number.isFinite(y))return "CHECK_REQUIRED";return x<y?"UPDATE_AVAILABLE":x>y?"NEWER_THAN_CATALOG":"CURRENT"}
 if(id==="daeja_viewone_virtual"){const v=cmp(i.version,a.version);if(v===null)return "CHECK_REQUIRED";if(v<0)return "UPDATE_AVAILABLE";if(v>0)return "NEWER_THAN_CATALOG";const x=i.interim_fix==null?null:Number(i.interim_fix),y=a.interim_fix==null?null:Number(a.interim_fix);if(x===null||y===null||!Number.isFinite(x)||!Number.isFinite(y))return "CHECK_REQUIRED";return x<y?"UPDATE_AVAILABLE":x>y?"NEWER_THAN_CATALOG":"CURRENT"}
 if(id==="db2"){const v=cmp(i.version,a.version);if(v===null)return "CHECK_REQUIRED";if(v<0)return "UPDATE_AVAILABLE";if(v>0)return "NEWER_THAN_CATALOG";return i.special_build&&i.special_build===a.special_build?"CURRENT":"CHECK_REQUIRED"}
 if(id==="iccsap"){const v=cmp(i.version,a.version);if(v===null)return "CHECK_REQUIRED";if(v<0)return "UPDATE_AVAILABLE";if(v>0)return "NEWER_THAN_CATALOG";const ds=(i.installed_fixes||[]).map(x=>String(x).match(/JRE_fix_(\d{8})/i)).filter(Boolean).map(x=>x[1]);if(!ds.length||!a.jre_fix_date)return "CHECK_REQUIRED";const x=ds.sort().at(-1),y=String(a.jre_fix_date);return x<y?"UPDATE_AVAILABLE":x>y?"NEWER_THAN_CATALOG":"CURRENT"}
 return "CHECK_REQUIRED"}
function installed(p){return [p.version,p.build_level,p.special_build,p.interim_fix!=null?"iFix "+p.interim_fix:null].filter(Boolean).join(" ")||"?"}
function available(id,e){const a=e&&e.available||{};return [a.version,a.interim_fix!=null?"iFix "+a.interim_fix:null,a.special_build,a.jre_version?"JRE "+a.jre_version:null].filter(Boolean).join(" ")||"?"}
function td(row,label,node){const c=document.createElement("td");c.dataset.label=label;c.append(node);row.append(c)}
function link(text,url){const a=document.createElement("a");a.textContent=text;a.href=url;a.target="_blank";a.rel="noopener noreferrer";return a}
Promise.all([fetch("/inventory.json",{cache:"no-store"}),fetch(CATALOG_URL,{cache:"no-store"})]).then(async rs=>{for(const r of rs)if(!r.ok)throw Error(`${r.url}: HTTP ${r.status}`);return Promise.all(rs.map(r=>r.json()))}).then(([inv,cat])=>{
 document.getElementById("host").textContent=`Host: ${inv.host&&inv.host.hostname||"?"} — inventory: ${inv.timestamp||"?"} — catalog: ${cat.generated_at||"?"}`;
 const age=Date.now()-Date.parse(cat.generated_at||"");const stale=!Number.isFinite(age)||age>72*3600*1000;const counts={};
 for(const p of inv.products||[]){const e=cat.products&&cat.products[p.id],entryAge=e?Date.now()-Date.parse(e.refreshed_at||cat.generated_at||""):NaN,entryBad=!Number.isFinite(entryAge)||entryAge>72*3600*1000||Boolean(e&&e.refresh_error),status=stale||entryBad?"CHECK_REQUIRED":e?compare(p.id,p,e):"CHECK_REQUIRED";counts[status]=(counts[status]||0)+1;
  const row=document.createElement("tr");td(row,"Product",document.createTextNode(p.name||p.id||"Unknown"));td(row,"Installed",document.createTextNode(installed(p)));td(row,"Available",document.createTextNode(available(p.id,e)));
  const mark=document.createElement("strong");mark.className=status;mark.textContent=labels[status];td(row,"Status",mark);const actions=document.createElement("span");if(e&&e.source_url)actions.append(link("Details",e.source_url));const download=e&&(e.download_url||(e.available||{}).download_url);if(download)actions.append(link("Download",download));td(row,"IBM resources",actions);document.getElementById("products").append(row)}
 document.getElementById("summary").textContent=Object.entries(counts).map(([k,v])=>`${v} ${labels[k]}`).join(" · ")+(stale?" · Catalog is stale or undated":"")
}).catch(e=>document.getElementById("error").textContent="Update data unavailable: "+e.message);
'''


def make_handler(inventory: dict[str, Any], user: str, password: str, catalog_url: str = DEFAULT_CATALOG_URL):
    inventory_json = json.dumps(inventory, ensure_ascii=False).encode("utf-8")
    app_js = JS_TEMPLATE.replace("__CATALOG_URL__", json.dumps(catalog_url)).encode("utf-8")
    expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    routes = {
        "/": (HTML, "text/html; charset=utf-8"),
        "/app.js": (app_js, "text/javascript; charset=utf-8"),
        "/styles.css": (CSS, "text/css; charset=utf-8"),
        "/inventory.json": (inventory_json, "application/json; charset=utf-8"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="IBM Update Checker"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            path = self.path.split("?", 1)[0]
            payload, content_type = routes.get(path, (b"Not Found", "text/plain; charset=utf-8"))
            self.send_response(200 if path in routes else 404)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https://raw.githubusercontent.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


def serve(inventory: dict[str, Any], bind: str, port: int, user: str, password: str) -> None:
    with ThreadingHTTPServer((bind, port), make_handler(inventory, user, password)) as server:
        print(f"IBM Update Checker: http://{bind}:{server.server_port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
