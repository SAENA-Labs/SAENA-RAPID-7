/* Local synthetic browser regression. Node >=22, installed Chromium, Python
 * with project src PYTHONPATH. No real credentials, external URLs or deploy. */
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const serverCode = String.raw`
import asyncio, hashlib, json, os, socket, tempfile, time
from pathlib import Path
import jwt, uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from saena_forge_console.app import create_app
from saena_forge_console.verified_auth import TokenVerifier, Membership
from saena_forge_console.report_store import ReportCatalog, ReportEntry
from saena_pilot.page_audit_report import build_page_audit_report
from saena_site_discovery.page_audit import audit_supplied_html
os.environ['SAENA_TENANT_ID']='demo-corp'
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
now=int(time.time())
def token(subject='demo',exp=now+600):
 return jwt.encode(dict(iss='https://synthetic.invalid',aud='viewer-demo',sub=subject,jti='demo-session',iat=now-2,nbf=now-2,exp=exp),key,algorithm='RS256')
verifier=TokenVerifier(public_key_pem=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo),issuer='https://synthetic.invalid',audience='viewer-demo',memberships={'demo':Membership('actor-demo','demo-corp',frozenset()),'denied':Membership('actor-denied','demo-corp',frozenset())})
with tempfile.TemporaryDirectory(prefix='saena-viewer-data-') as tmp:
 root=Path(tmp).resolve();entries={}
 for name in ['valid','clean','review','empty','slow','broken','long']:
  directory=root/name;directory.mkdir(mode=0o700)
  audits=[] if name=='empty' else [audit_supplied_html(tenant_id='demo-corp',page_url='https://example.invalid/product',html=(b'<html><head><title>Demo</title><meta name=robots content=noindex></head></html>' if name=='review' else b'<html><head><title>Demo</title></head></html>'),evidence_ref='local-html://fixture')]
  report=json.loads(build_page_audit_report(tenant_id='demo-corp',expected_pages=['https://example.invalid/product','https://example.invalid/missing'],audits=audits).json_text)
  if name in ['valid','slow']:report['measured_pages'][0]['findings'][0]['detail']='<img src=x onerror="window.XSS=true"> fixture text, not HTML'
  if name=='long':
   from copy import deepcopy
   page=report['measured_pages'][0];report['measured_pages']=[]
   for i in range(100):
    item=deepcopy(page);item['page_url']='https://example.invalid/'+str(i)+'/'+'long-segment-'*20;report['measured_pages'].append(item)
   report['measured_page_count']=100;report['expected_page_count']=101
  rb=json.dumps(report).encode();cb=json.dumps(dict(tenant_id='demo-corp',scope='offline_supplied_html',raw_html_stored=False,manifest_sha256='sha256:'+'1'*64)).encode()
  (directory/'report.json').write_bytes(rb);(directory/'receipt.json').write_bytes(cb)
  sha=lambda x:'sha256:'+hashlib.sha256(x).hexdigest()
  entries[name]=ReportEntry('demo-corp',name,sha(rb),sha(cb))
  if name=='broken':(directory/'report.json').write_bytes(b'{}')
 app=create_app(token_verifier=verifier,report_catalog=ReportCatalog(root=str(root),entries=entries,readers={('demo-corp','actor-demo')}),enable_report_viewer=True)
 @app.middleware('http')
 async def delay(request,call_next):
  if request.url.path.endswith('/slow'):await asyncio.sleep(1)
  return await call_next(request)
 sock=socket.socket();sock.bind(('127.0.0.1',0))
 print(json.dumps(dict(url='http://127.0.0.1:'+str(sock.getsockname()[1]),token=token(),expired=token(exp=now-1),denied=token('denied'))),flush=True)
 uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False)).run(sockets=[sock])
`;
const python = process.env.SAENA_PYTHON;
const chromePath = process.env.SAENA_CHROMIUM;
if (!python || !chromePath) throw new Error('SAENA_PYTHON and SAENA_CHROMIUM required');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'saena-viewer-browser-'));
const output = process.env.SAENA_VIEWER_OUTPUT || profile;
fs.mkdirSync(output,{recursive:true});
const server = spawn(python,['-u','-c',serverCode],{env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
let chrome, ws, pending = new Map(), nextId=0, external=[], errors=[];
function cdp(method,params={}) { return new Promise((resolve,reject)=> { const id=++nextId; pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params})); }); }
async function evaluate(expression) { const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error('Browser evaluation failed');return r.result.value; }
async function until(expression, timeout=10000) {const start=Date.now();while(Date.now()-start<timeout){if(await evaluate(expression))return;await sleep(50);}throw new Error('UI condition timed out: '+expression);}
async function navigate(url) {await cdp('Page.navigate',{url});await until('document.readyState === "complete"');await until('!!document.getElementById("load")');}
(async()=>{
 const fixture=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(new Error('fixture startup timeout')),15000);server.stdout.on('data',chunk=>{buf+=chunk;if(buf.includes('\n')){clearTimeout(timer);resolve(JSON.parse(buf.split('\n')[0]));}});server.on('exit',()=>reject(new Error('fixture exited')));});
 for(let i=0;i<100;i++){try{await fetch(fixture.url+'/report-viewer');break;}catch{await sleep(100);}}
 chrome=spawn(chromePath,['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'--no-first-run','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--metrics-recording-only','about:blank'],{stdio:'ignore'});
 let port;
 for(let i=0;i<150;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break;}catch{await sleep(100);}}
 if(!port)throw new Error('Chromium startup timeout');
 const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));
 ws.addEventListener('message',e=>{const v=JSON.parse(e.data);if(v.id){const item=pending.get(v.id);pending.delete(v.id);v.error?item.reject(new Error(v.error.message)):item.resolve(v.result);}else if(v.method==='Network.requestWillBeSent'&&!v.params.request.url.startsWith(fixture.url+'/')){external.push(v.params.request.url);}else if(v.method==='Runtime.exceptionThrown'){errors.push(v.params.exceptionDetails.text);}});
 await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Network.enable');
 await cdp('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 await navigate(fixture.url+'/report-viewer');
 async function load(id,tok=fixture.token) {await evaluate(`document.getElementById('report-id').value=${JSON.stringify(id)};document.getElementById('report-id').dispatchEvent(new Event('input'));document.getElementById('access-token').value=${JSON.stringify(tok)};document.getElementById('load').click()`);}
 await load('valid');await until('!document.getElementById("report").hidden');
 assert(await evaluate('document.getElementById("report").textContent.includes("미측정")'));
 assert(await evaluate('document.getElementById("report").textContent.includes("<img src=x")'));
 assert.equal(await evaluate('!!window.XSS || document.querySelectorAll("#report img").length>0'),false);
 assert.equal(await evaluate('document.getElementById("access-token").value'),'');
 assert.equal(await evaluate('localStorage.length + sessionStorage.length'),0);
 assert.equal(await evaluate('document.cookie'),'');
 assert(await evaluate('document.querySelector(".finding .tag").textContent === "정보"'));
 await evaluate(`document.getElementById('clear').click();document.getElementById('report-id').value='valid';document.getElementById('access-token').value=${JSON.stringify(fixture.token)};document.getElementById('access-token').focus()`);
 await cdp('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await until('!document.getElementById("report").hidden');
 await load('clean');await until('!document.getElementById("report").hidden');
 const size= (await cdp('Page.getLayoutMetrics')).cssContentSize;
 fs.writeFileSync(path.join(output,'viewer-desktop.png'),Buffer.from((await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1280,height:size.height,scale:1}})).data,'base64'));
 await load('empty');await until('!document.getElementById("report").hidden');
 assert(await evaluate('document.getElementById("report").textContent.includes("HTML 진단0")'));
 for(const [id,tok,phrase] of [['valid',fixture.expired,'유효하지'],['valid',fixture.denied,'권한'],['unknown',fixture.token,'찾을 수'],['broken',fixture.token,'안전하게']]){
  await load(id,tok);await until(`document.getElementById('status').textContent.includes(${JSON.stringify(phrase)})`);assert(await evaluate('document.getElementById("report").hidden'));
 }
 await load('review');await until('!document.getElementById("report").hidden');
 assert(await evaluate('document.getElementById("report").textContent.includes("검토 필요")'));
 await load('slow');await evaluate('document.getElementById("load").click()');await until('!document.getElementById("report").hidden');
 assert(await evaluate('document.getElementById("status").textContent.includes("표시했습니다")'));
 await load('slow');await load('empty');await until('!document.getElementById("report").hidden');await sleep(1300);
 assert(await evaluate('document.getElementById("report").textContent.includes("HTML 진단0")'));
 await load('slow');await evaluate('document.getElementById("clear").click()');await sleep(1300);
 assert(await evaluate('document.getElementById("report").hidden && document.getElementById("access-token").value === ""'));
 await load('clean');await until('!document.getElementById("report").hidden');
 await cdp('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
 fs.writeFileSync(path.join(output,'viewer-mobile.png'),Buffer.from((await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
 await load('long');await until('document.querySelectorAll("#report .page").length === 100');
 assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
 await evaluate('window.savedFetch = window.fetch; window.fetch = () => Promise.reject(new Error("synthetic network error"))');
 await load('valid');await until('document.getElementById("status").textContent.includes("연결 또는")');
 assert(await evaluate('document.getElementById("report").hidden'));
 await evaluate('window.fetch = () => Promise.resolve(new Response("{}", {headers:{"Content-Type":"application/json"}}))');
 await load('valid');await until('document.getElementById("status").textContent.includes("연결 또는")');
 await evaluate('window.fetch = window.savedFetch; delete window.savedFetch');
 await cdp('Page.reload');await until('!!document.getElementById("load") && document.readyState === "complete"');await sleep(100);
 assert(await evaluate('document.getElementById("report").hidden && document.getElementById("access-token").value === ""'));
 await load('valid');await until('!document.getElementById("report").hidden');
 await navigate(fixture.url+'/report-viewer?second');await cdp('Runtime.evaluate',{expression:'history.back()'});await sleep(300);
 assert(await evaluate('document.getElementById("report").hidden && document.getElementById("access-token").value === ""'));
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
 console.log(JSON.stringify({result:'PASS',scenarios:['valid','unmeasured','xss-text','memory-only-token','401','403','404','503','stale-response','repeated-click','review-level','cancel','keyboard-enter','severity-label','mobile','long-report','network-failure','invalid-response','reload','back'],screenshots:output}));
})().catch(e=>{console.error(e.message);process.exitCode=1;}).finally(async()=>{if(ws)ws.close();if(chrome)chrome.kill();server.kill();await sleep(300);});
