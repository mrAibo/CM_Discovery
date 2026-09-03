#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only IBM product discovery collector. Python 3.6+, stdlib only."""
import argparse, datetime, json, os, platform, re, socket, subprocess, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

SCHEMA_VERSION=1
COLLECTOR_VERSION="0.5.0"
P={
 "was":"/opt/IBM/WebSphere/AppServer/bin/versionInfo.sh",
 "db2":"/home/db2icm/sqllib/bin/db2level",
 "cm":"/opt/IBM/db2cmv8/bin/cmlevel",
 "icn":"/opt/IBM/ECMClient/version.txt",
 "iccsap":"/opt/IBM/iccsap/iccsap.version",
 "imcl":"/opt/IBM/InstallationManager/eclipse/tools/imcl",
}

def run(cmd,timeout=30):
 try:
  p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=timeout,check=False)
  return p.returncode,p.stdout or "",p.stderr or "","direct",None
 except OSError as e:
  if getattr(e,"errno",None)==8:
   for sh in ("/bin/sh","/bin/bash"):
    if os.path.isfile(sh):
     try:
      p=subprocess.run([sh,cmd[0]]+cmd[1:],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=timeout,check=False)
      return p.returncode,p.stdout or "",p.stderr or "","shell_fallback",sh
     except Exception: pass
  return None,"",str(e),"direct",None
 except Exception as e: return None,"",str(e),"direct",None

def read(path):
 try:
  with open(path,"r",encoding="utf-8",errors="replace") as f:return f.read()
 except Exception:return ""

def add(r,id,name,version,source,**kw):
 x={"id":id,"name":name,"version":version,"source":source};x.update({k:v for k,v in kw.items() if v is not None});r["products"].append(x)

def host():
 x={"hostname":socket.gethostname(),"fqdn":socket.getfqdn(),"platform":platform.platform(),"system":platform.system(),"release":platform.release(),"machine":platform.machine(),"python_version":platform.python_version()}
 o={}
 for l in read("/etc/os-release").splitlines():
  if "=" in l and not l.startswith("#"):
   k,v=l.split("=",1);o[k]=v.strip().strip('"')
 if o:x["os_release"]=o
 return x

def was(r):
 path=P["was"]
 if not os.access(path,os.X_OK):r["discovery"]["websphere"]={"status":"not_found","path":path};return
 rc,out,err,mode,sh=run([path]);r["discovery"]["websphere"]={"status":"ok" if rc==0 else "error","path":path,"returncode":rc}
 for b in re.split(r"\n\s*\n",out.replace("\r","")):
  if "Installiertes Produkt" not in b and "Installed Product" not in b:continue
  def g(pat):
   m=re.search(pat,b,re.M);return m.group(1).strip() if m else None
  n,v=g(r"^Name\s+(.+)$"),g(r"^Version\s+(.+)$")
  if not n or not v:continue
  if "WebSphere Application Server" in n:id,name="websphere","IBM WebSphere Application Server"
  elif "IBM SDK, Java Technology Edition" in n:id,name="ibm_java","IBM SDK, Java Technology Edition"
  else:id,name="websphere_component",n
  add(r,id,name,v,"websphere_versionInfo",product_id=g(r"^ID\s+(.+)$"),build_version=g(r"^(?:Build-Version|Build Version)\s+(.+)$"),build_date=g(r"^(?:Build-Datum|Build Date)\s+(.+)$"))

def db2(r):
 path=P["db2"]
 if not os.access(path,os.X_OK):r["discovery"]["db2"]={"status":"not_found","path":path};return
 rc,out,err,mode,sh=run([path]);profile="/home/db2icm/sqllib/db2profile"
 if (rc!=0 or not out.strip()) and os.path.isfile(profile):
  shell="/bin/bash" if os.path.isfile("/bin/bash") else "/bin/sh"
  rc2,o2,e2,_,_=run([shell,"-c",'. "{}" && exec "{}"'.format(profile,path)])
  if rc2==0 or o2.strip():rc,out,err,mode=rc2,o2,e2,"db2profile"
 st={"status":"ok" if rc==0 else "error","path":path,"returncode":rc,"execution_mode":mode}
 if mode=="db2profile":st["profile"]=profile
 r["discovery"]["db2"]=st
 m=re.search(r'DB2 v([^"\s,]+)',out)
 if not m:st["status"]="parse_error";st["stderr"]=err.strip();return
 v=m.group(1);fp=re.search(r'(?:Fix Pack|FixPak)\s+"([^"]+)"',out,re.I);cr=re.search(r'DB2 code release\s+"([^"]+)"',out,re.I) or re.search(r'\b(SQL\d{5})\b',out);sb=re.search(r'"(special_[^"]+)"',out)
 add(r,"db2","IBM DB2",v,"db2level",fix_pack=fp.group(1) if fp else None,code_release=cr.group(1) if cr else None,special_build=sb.group(1) if sb else None);st["status"]="ok"

def cm(r):
 path=P["cm"]
 if not os.access(path,os.X_OK):r["discovery"]["content_manager"]={"status":"not_found","path":path};return
 rc,out,err,mode,sh=run([path,"-l"]);st={"status":"ok" if rc==0 else "error","path":path,"returncode":rc,"execution_mode":mode};
 if sh:st["shell"]=sh
 r["discovery"]["content_manager"]=st;rows=[];sec=None
 for raw in out.replace("\r","").splitlines():
  l=raw.strip();lo=l.lower()
  if lo.startswith("products installed:"):sec="installed";continue
  if lo.startswith("products configured:"):sec="configured";continue
  if sec and "+" in l:
   n,z=l.split("+",1);f=z.split()
   if f and re.match(r"^\d+(?:\.\d+)+$",f[0]):rows.append((n.strip(),f[0],f[1] if len(f)>1 else None,sec))
 main=[x for x in rows if x[0].lower()=="content manager"]
 if not main:st["status"]="parse_error";return
 v,b=main[0][1],main[0][2];comps=[]
 for n in sorted(set(x[0] for x in rows if x[0].lower()!="content manager"),key=str.lower):
  rr=[x for x in rows if x[0]==n];c={"name":n,"version":rr[0][1],"installed":any(x[3]=="installed" for x in rr),"configured":any(x[3]=="configured" for x in rr)}
  if rr[0][2]:c["build"]=rr[0][2]
  comps.append(c)
 add(r,"content_manager","IBM Content Manager",v,"cmlevel",build=b,fix_level=v.split(".")[-1],installed=any(x[3]=="installed" for x in main),configured=any(x[3]=="configured" for x in main),components=comps);st["component_count"]=len(comps)

def icn(r):
 path=P["icn"];t=read(path).replace("\r","");r["discovery"]["content_navigator"]={"status":"ok" if t else "not_found","path":path}
 if not t:return
 kv=dict(l.strip().split("=",1) for l in t.splitlines() if "=" in l)
 if kv.get("version"):add(r,"content_navigator","IBM Content Navigator",kv["version"],"ecmclient_version_txt",build_level=kv.get("build.level"),build_number=kv.get("build.number"))
 for id,name,pat in (("filenet_ce_client","IBM FileNet Content Engine client",r"IBM FileNet Content Engine client Version\s+(.+)"),("filenet_pe_client","IBM FileNet Process Engine client",r"IBM FileNet Process Engine client Version\s+(.+)"),("content_manager_apis","IBM Content Manager APIs",r"IBM Content Manager APIs Version\s+(.+)")):
  m=re.search(pat,t)
  if m:add(r,id,name,m.group(1).strip(),"ecmclient_version_txt")
 m=re.search(r"IBM Daeja ViewONE Virtual Version\s+(.+)",t)
 if m:
  raw=m.group(1).strip();v=re.match(r"\S+",raw);i=re.search(r"iFix\s+(\d+)",raw,re.I);b=re.search(r"\((\d+)\)\s*$",raw)
  add(r,"daeja_viewone_virtual","IBM Daeja ViewONE Virtual",v.group(0) if v else "?","ecmclient_version_txt",raw_version=raw,interim_fix=int(i.group(1)) if i else None,build=b.group(1) if b else None)

def iccsap(r):
 path=P["iccsap"];t=read(path).replace("\r","");r["discovery"]["iccsap"]={"status":"ok" if t else "not_found","path":path}
 if not t:return
 ls=[x.strip() for x in t.splitlines() if x.strip()];name=next((x for x in ls if not x.startswith(("Version","Build"))),"IBM Content Collector for SAP Applications");v=next((x.split(None,1)[1] for x in ls if x.startswith("Version") and len(x.split(None,1))>1),None);b=next((x.split(None,1)[1] for x in ls if x.startswith("Build") and len(x.split(None,1))>1),None)
 if v:add(r,"iccsap",name,v,"iccsap_version_file",build=b)

def im(r):
 path=P["imcl"]
 if not os.access(path,os.X_OK):r["discovery"]["installation_manager"]={"status":"not_found","path":path};return
 rc,out,err,mode,sh=run([path,"listInstalledPackages","-verbose"],60);r["discovery"]["installation_manager"]={"status":"ok" if rc==0 else "error","path":path,"returncode":rc};lines=[x.strip() for x in out.replace("\r","").splitlines() if x.strip()];r["installation_manager"]={"path":path,"packages_raw":lines}

def timed(name,fn,r):
 s=time.monotonic()
 try:fn(r)
 except Exception as e:r["discovery"][name]={"status":"exception","error":"{}: {}".format(type(e).__name__,e)}
 finally:r["discovery"].setdefault(name,{"status":"unknown"})["duration_seconds"]=round(time.monotonic()-s,3)

def inventory(skip_im=False):
 r={"schema_version":SCHEMA_VERSION,"collector_version":COLLECTOR_VERSION,"timestamp":datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),"host":host(),"products":[],"discovery":{}}
 jobs=[("websphere",was),("db2",db2),("content_manager",cm),("content_navigator",icn),("iccsap",iccsap)]
 if skip_im:r["discovery"]["installation_manager"]={"status":"skipped","duration_seconds":0.0}
 else:jobs.append(("installation_manager",im))
 with ThreadPoolExecutor(max_workers=len(jobs)) as p:
  fs=[p.submit(timed,n,f,r) for n,f in jobs]
  for f in as_completed(fs):f.result()
 r["products"].sort(key=lambda x:(x.get("id",""),x.get("name","")));return r

def human(r):
 print("="*78);print("IBM Product Discovery");print("="*78);print("Host       : {}".format(r["host"]["hostname"]));print("Zeitpunkt  : {}".format(r["timestamp"]));print("OS         : {}\n".format((r["host"].get("os_release") or {}).get("PRETTY_NAME",r["host"]["platform"])))
 for x in r["products"]:
  print("--- {} ---\n  Version       : {}".format(x["name"],x.get("version","N/A")))
  for k,l in (("product_id","Produkt-ID"),("build","Build"),("build_version","Build-Version"),("build_level","Build-Level"),("build_number","Build-Nummer"),("fix_level","Fix-Level"),("fix_pack","Fix Pack"),("interim_fix","Interim Fix"),("code_release","Code Release"),("special_build","Special Build"),("installed","Installiert"),("configured","Konfiguriert"),("source","Quelle")):
   if k in x:print("  {:14}: {}".format(l,x[k]))
  print()
 print("--- Discovery Status ---")
 for n,s in sorted(r["discovery"].items()):print("  {:24}: {:12} ({:.3f}s)".format(n,s.get("status","unknown"),s.get("duration_seconds",0.0)))
 print("\n"+"="*78)

WEB_HTML=b'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IBM Update Checker</title><style>
body{font:16px system-ui,sans-serif;max-width:1200px;margin:auto;padding:1rem;color:#161616}table{border-collapse:collapse;width:100%}th,td{border:1px solid #aaa;padding:.5rem;text-align:left;vertical-align:top}input{box-sizing:border-box;width:100%;min-width:9rem;padding:.4rem}.CURRENT{color:#087830}.UPDATE{color:#b34b00}.REVIEW{color:#a2191f}.UNKNOWN{color:#525252}.note{background:#fff8e1;padding:.8rem}button,a{margin:.15rem}</style>
<script src="/app.js" defer></script></head><body>
<h1>IBM Update Checker</h1><p id="host"></p>
<p class="note"><strong>Manual check:</strong> the browser cannot inspect IBM tabs. Open the IBM source, enter the confirmed target level, then optionally paste an official HTTP(S) details/download URL. IBMid credentials remain on IBM.</p>
<table><thead><tr><th>Product</th><th>Installed</th><th>Confirmed target</th><th>Status</th><th>IBM / download</th></tr></thead><tbody id="products"></tbody></table>
</body></html>'''

WEB_JS=r'''"use strict";
const sources={
 content_manager:"https://www.ibm.com/docs/en/content-manager/8.7.0?topic=fix-packs",
 content_navigator:"https://www.ibm.com/support/pages/ibm-content-navigator-version-310-interim-fix-12-readme",
 daeja_viewone_virtual:"https://delivery04.dhe.ibm.com/sar/CMA/OSA/0dx21/0/5.0.15_DAEJA_VIEWONE_IFIX006_Readme.htm",
 db2:"https://www.ibm.com/support/pages/node/7087189",
 ibm_java:"https://www.ibm.com/support/pages/ibm-sdk-java-technology-edition-refreshes",
 iccsap:"https://www.ibm.com/support/pages/security-bulletin-multiple-vulnerabilities-may-affect-ibm%C2%AE-sdk-java%E2%84%A2-technology-edition-ibm-content-collector-sap-applications-16",
 websphere:"https://www.ibm.com/support/pages/fix-list-ibm-websphere-application-server-traditional-v9-0"
};
function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node}
function parts(value){const found=String(value).match(/\d+/g);return found&&found.map(Number)}
function status(installed,target){const a=parts(installed),b=parts(target);if(!target)return"UNKNOWN";if(!a||!b)return"REVIEW";const n=Math.max(a.length,b.length);for(let i=0;i<n;i++){const x=a[i]||0,y=b[i]||0;if(y>x)return"UPDATE";if(y<x)return"REVIEW"}return"CURRENT"}
function safeUrl(value){try{const u=new URL(value);return u.protocol==="http:"||u.protocol==="https:"?u.href:null}catch(_){return null}}
function openUrl(value){const url=safeUrl(value);if(url)window.open(url,"_blank","noopener,noreferrer");else alert("Only HTTP(S) URLs are allowed.")}
function installedLevel(p){let level=String(p.version||"?");if(p.interim_fix!==undefined)level+=" iFix "+p.interim_fix;else if(p.id==="content_navigator"&&p.build_level){const m=String(p.build_level).match(/icn\d+\.(\d+)/i);if(m)level+=" iFix "+Number(m[1])}if(p.special_build)level+=" "+p.special_build;return level}
function cell(row,node){const td=el("td");td.append(node);row.append(td)}
fetch("/inventory.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(data=>{
 document.getElementById("host").textContent="Host: "+(data.host&&data.host.hostname||"?")+" — inventory: "+(data.timestamp||"?");
 for(const product of data.products||[]){const row=el("tr"),installed=installedLevel(product);cell(row,el("strong",product.name||product.id||"Unknown"));cell(row,el("span",installed));
  const manualTarget=el("input");manualTarget.className="manualTarget";manualTarget.placeholder="e.g. 9.0.5.28";cell(row,manualTarget);
  const result=el("strong","UNKNOWN");result.className="UNKNOWN";cell(row,result);
  const actions=el("div"),source=sources[product.id];if(source){const a=el("a","Open IBM source");a.href=source;a.target="_blank";a.rel="noopener noreferrer";actions.append(a)}
  const url=el("input");url.placeholder="Optional IBM URL";actions.append(url);const button=el("button","Open URL");button.type="button";button.onclick=()=>openUrl(url.value);actions.append(button);cell(row,actions);
  manualTarget.oninput=()=>{result.textContent=status(installed,manualTarget.value.trim());result.className=result.textContent};document.getElementById("products").append(row)
 }
}).catch(error=>{document.getElementById("host").textContent="Inventory unavailable: "+error});
'''.encode("utf-8")

def make_web_handler(snapshot):
 inventory_json=json.dumps(snapshot,ensure_ascii=False).encode("utf-8")
 class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
   path=self.path.split("?",1)[0]
   payload,content_type=({"/":(WEB_HTML,"text/html; charset=utf-8"),"/app.js":(WEB_JS,"text/javascript; charset=utf-8"),"/inventory.json":(inventory_json,"application/json; charset=utf-8")}).get(path,(b"Not Found","text/plain; charset=utf-8"))
   self.send_response(200 if path in ("/","/app.js","/inventory.json") else 404)
   self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(payload)));self.send_header("Cache-Control","no-store")
   self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
   self.send_header("X-Content-Type-Options","nosniff");self.end_headers();self.wfile.write(payload)
  def log_message(self,format,*args): pass
 return Handler

def serve_web(snapshot,bind,port):
 with HTTPServer((bind,port),make_web_handler(snapshot)) as server:
  print("IBM Update Checker: http://{}:{}/".format(bind,server.server_port))
  try:server.serve_forever()
  except KeyboardInterrupt:pass

def main():
 p=argparse.ArgumentParser();p.add_argument("--json",action="store_true");p.add_argument("--pretty",action="store_true");p.add_argument("--skip-im",action="store_true");p.add_argument("--serve",action="store_true");p.add_argument("--bind",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);a=p.parse_args();r=inventory(a.skip_im)
 if a.serve:serve_web(r,a.bind,a.port);return
 if a.json:print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None))
 else:human(r)
if __name__=="__main__":main()
