// Actual Chrome; bounded synthetic bytes fulfilled over CDP, every other request
// denied. Diagnostic measurements are NOT inserted into BrowserObservation v1.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const root=path.dirname(fileURLToPath(import.meta.url));
const label=process.argv[2];
assert(/^[a-z0-9-]{3,50}$/.test(label||''),'unique output label required');
const out=path.join(root,'.runtime',label);
await mkdir(out,{recursive:false});
const profile=await mkdtemp(path.join(out,'chrome-profile-'));
const fixture=await readFile(path.join(root,'fixture.html'));
const legacyScript=await readFile(path.join(root,'../../vrae/browser/controller.py'),'utf8');
const legacy=legacyScript.match(/DOM_SCRIPT = """([\s\S]*?)"""/)[1];
const sha=b=>createHash('sha256').update(b).digest('hex');
let ws,child,serial=0,session,exitCode=null;
let stderr='',closed=false;
const pending=new Map(),records=[],requests=[],assertions=[],protocol=[];
const chrome=process.env.L2_CHROMIUM||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':'/usr/bin/google-chrome');
function call(method,params={},sessionId=session){return new Promise((resolve,reject)=>{
  protocol.push({at:new Date().toISOString(),direction:'send',method,session:sessionId||null});
  const id=++serial,t=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method));},15000);
  pending.set(id,{resolve,reject,t});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails);return r.result.value;}
function check(name,pass){assertions.push({name,pass:!!pass});assert(pass,name);}
try{
  child=spawn(chrome,[`--user-data-dir=${profile}`,'--remote-debugging-port=0','--headless=new',
    '--no-first-run','--disable-extensions','--disable-background-networking','--disable-sync',
    '--disable-gpu','--disable-component-update','--disable-default-apps','--no-default-browser-check',
    '--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter',
    '--proxy-server=http://127.0.0.1:9','--host-resolver-rules=MAP * ~NOTFOUND',
    '--remote-debugging-address=127.0.0.1','about:blank'],
    {windowsHide:true,stdio:['ignore','ignore','pipe']});
  child.on('exit',code=>{exitCode=code;closed=true;});
  const endpoint=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('CHROME_START_TIMEOUT')),20000);
    child.once('error',reject);
    child.stderr.on('data',b=>{stderr+=b.toString();const m=stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
  });
  ws=new WebSocket(endpoint);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=event=>{const m=JSON.parse(event.data);protocol.push({at:new Date().toISOString(),direction:'receive',id:m.id,method:m.method,error:m.error});if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.t);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result);}return;}
    if(m.method==='Fetch.requestPaused')void(async()=>{
      const p=m.params,allowed=p.request.method==='GET'&&p.resourceType==='Document'&&/^https:\/\/synthetic\.invalid\/\?case=(clean|hidden|covered|overflow|multilingual|blocked)$/.test(p.request.url);
      requests.push({url:p.request.url,method:p.request.method,type:p.resourceType,allowed});
      await call(allowed?'Fetch.fulfillRequest':'Fetch.failRequest',allowed?{
        requestId:p.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'text/html; charset=utf-8'}],body:fixture.toString('base64')
      }:{requestId:p.requestId,errorReason:'BlockedByClient'},m.sessionId);
    })().catch(e=>assertions.push({name:'resource-handler',pass:false,error:e.message}));
  };
  const version=await call('Browser.getVersion',{},null);
  const target=(await call('Target.createTarget',{url:'about:blank'},null)).targetId;
  session=(await call('Target.attachToTarget',{targetId:target,flatten:true},null)).sessionId;
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Network.setBypassServiceWorker',{bypass:true});
  await call('Network.setCacheDisabled',{cacheDisabled:true});
  await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  for(const width of [1280,390,375,320])for(const scenario of ['clean','hidden','covered','overflow','multilingual','blocked']){
    const height=width===1280?720:844,url=`https://synthetic.invalid/?case=${scenario}`;
    await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<1280});
    await call('Page.navigate',{url});
    let ready=false;
    for(let n=0;n<100;n++){if(await evaluate(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'&&document.body.dataset.case===${JSON.stringify(scenario)}`)){ready=true;break;}await new Promise(r=>setTimeout(r,25));}
    assert(ready,'page complete');
    const observedAt=new Date().toISOString(),dom=await evaluate(legacy);
    const metrics=await evaluate(`(()=>{const a=document.querySelector('#quote'),r=a.getBoundingClientRect(),x=Math.max(0,Math.min(innerWidth-1,r.x+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2)),hit=document.elementFromPoint(x,y);return {viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,href:a.getAttribute('href'),opacity:getComputedStyle(a).opacity,centerHit:!!hit&&(hit===a||a.contains(hit)),image:{complete:document.querySelector('#drawing').complete,naturalWidth:document.querySelector('#drawing').naturalWidth,alt:document.querySelector('#drawing').getAttribute('alt')}}})()`);
    const png=Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64');
    const stem=`${scenario}-${width}`;
    await writeFile(path.join(out,stem+'.png'),png);
    await writeFile(path.join(out,stem+'.dom.json'),JSON.stringify(dom));
    const anchor=dom.elements.find(e=>e.tag==='A'&&e.text==='Request a quote');
    check(stem+'-legacy-missing-href',anchor&&!('href' in anchor));
    if(scenario==='hidden')check(stem+'-nonzero-is-not-visible',anchor.visible&&metrics.opacity==='0');
    if(scenario==='covered')check(stem+'-nonzero-is-not-hit',anchor.visible&&!metrics.centerHit);
    if(scenario==='overflow'&&width<560)check(stem+'-real-overflow',metrics.scrollWidth>metrics.clientWidth);
    if(scenario==='clean')check(stem+'-actual-measured-control',metrics.href==='/rfq'&&metrics.centerHit&&metrics.image.complete&&metrics.image.naturalWidth>0);
    if(scenario==='multilingual')check(stem+'-missing-alt',metrics.image.alt===null);
    records.push({scenario,width,height,url,observed_at:observedAt,dom_sha256:sha(Buffer.from(JSON.stringify(dom))),screenshot_sha256:sha(png),metrics,
      eligible_v1_viewport:width===390||width===1280,diagnostic_only:true});
  }
  check('unapproved-subrequests-denied',requests.some(r=>r.url==='https://unapproved.invalid/tracker'&&!r.allowed));
  check('no-rfq-or-write-request',requests.every(r=>r.method==='GET'&&!r.url.endsWith('/rfq')));
  check('no-resource-handler-failure',assertions.every(a=>a.pass));
  await writeFile(path.join(out,'browser.json'),JSON.stringify({kind:'SYNTHETIC_OFFLINE_DIAGNOSTIC_NOT_AUTHORITY',version:version.product,fixture_sha256:sha(fixture),legacy_script_sha256:sha(Buffer.from(legacy)),records,requests,assertions},null,2));
}finally{
  if(ws&&ws.readyState===WebSocket.OPEN){try{await call('Browser.close',{},null);}catch{}ws.close();}
  if(child&&!closed){for(let n=0;n<100&&!closed;n++)await new Promise(r=>setTimeout(r,30));if(!closed)child.kill();}
  if(child&&!closed)await new Promise(resolve=>{child.once('exit',resolve);setTimeout(resolve,5000);});
  await writeFile(path.join(out,'cleanup.json'),JSON.stringify({pid:child?.pid,closed,exitCode,profile_retained_for_evidence:true}));
  await writeFile(path.join(out,'protocol.json'),JSON.stringify(protocol,null,2));
  await writeFile(path.join(out,'chrome.stderr.log'),stderr);
  check('dedicated-chrome-exited',closed);
}
