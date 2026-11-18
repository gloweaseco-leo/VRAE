// Approved P0 fixture + unchanged v1 DOM_SCRIPT. Supplemental geometry stays outside v1.
import {spawn,execFileSync} from 'node:child_process';
import {readFile,writeFile,mkdir,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const own=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(own,'../..');
const out=path.resolve(process.argv[2]);assert(out.startsWith(path.join(root,'integration/s2_buyer_workbench/.runtime')+path.sep));
await mkdir(out,{recursive:false});
const fixtureFile='integration/s2_ux/fixture.html';
assert.equal(execFileSync('git',['hash-object','--path',fixtureFile,fixtureFile],{cwd:root,encoding:'utf8'}).trim(),'6b1e3d606de594e8359c8f08a64b11d7378d9637');
const fixture=await readFile(path.join(root,fixtureFile));
const controller=(await readFile(path.join(root,'vrae/browser/controller.py'),'utf8')).replace(/\r\n/g,'\n');
const legacy=controller.match(/DOM_SCRIPT = """([\s\S]*?)"""/)[1];
const hash=b=>createHash('sha256').update(b).digest('hex');
const profile=await mkdtemp(path.join(tmpdir(),'s2-cta-'));
const records=[],requests=[],checks=[];let chrome,ws,sid,serial=0,tail='',exitObserved=false;
const pending=new Map();const startedAt=new Date().toISOString();
function call(method,params={},sessionId=sid){return new Promise((resolve,reject)=>{const id=++serial,t=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method));},15000);pending.set(id,{resolve,reject,t});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'EVALUATION_FAILED');return r.result.value;}
function check(name,value){checks.push({name,pass:!!value});assert(value,name);}
try{
  chrome=spawn(process.env.RA4C0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe',[
    '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter',
    '--proxy-server=http://127.0.0.1:9','--host-resolver-rules=MAP * ~NOTFOUND','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  chrome.once('exit',()=>{exitObserved=true;});
  const endpoint=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('CHROME_START_TIMEOUT')),20000);chrome.once('error',()=>{clearTimeout(t);reject(Error('CHROME_START_FAILED'));});chrome.stderr.on('data',b=>{tail=(tail+b.toString()).slice(-4096);const m=tail.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(t);resolve(m[0]);}});});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.t);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result);}
    if(m.method==='Fetch.requestPaused')void(async()=>{const q=m.params,allowed=q.request.method==='GET'&&q.resourceType==='Document'&&/^https:\/\/synthetic\.invalid\/\?case=(clean|hidden|covered|overflow)$/.test(q.request.url);
      requests.push({url:q.request.url,method:q.request.method,type:q.resourceType,allowed});
      await call(allowed?'Fetch.fulfillRequest':'Fetch.failRequest',allowed?{requestId:q.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'text/html; charset=utf-8'}],body:fixture.toString('base64')}:{requestId:q.requestId,errorReason:'BlockedByClient'},m.sessionId);
    })().catch(()=>checks.push({name:'request-handler',pass:false}));});
  const version=await call('Browser.getVersion',{},null);
  const {targetId}=await call('Target.createTarget',{url:'about:blank'},null);({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true},null));
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Network.setBypassServiceWorker',{bypass:true});await call('Network.setCacheDisabled',{cacheDisabled:true});await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  for(const width of [390,375,320,1280])for(const scenario of ['clean','hidden','covered','overflow']){
    const height=width===1280?720:844,url='https://synthetic.invalid/?case='+scenario;
    await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<1280});await call('Page.navigate',{url});
    let ready=false;for(let n=0;n<100;n++){if(await ev(`location.href===${JSON.stringify(url)}&&document.readyState==='complete'&&document.body.dataset.case===${JSON.stringify(scenario)}`)){ready=true;break;}await new Promise(r=>setTimeout(r,30));}assert(ready,'SOURCE_NOT_READY');
    await ev('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))).then(()=>true)');
    const dom=await ev(legacy);
    const metrics=await ev(`(()=>{const clientWidth=document.documentElement.clientWidth;return{clientWidth,scrollWidth:document.documentElement.scrollWidth,innerWidth,innerHeight,
      targets:['quote','inquiry'].map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect(),s=getComputedStyle(e);let opacity=1;for(let n=e;n;n=n.parentElement)opacity*=Number(getComputedStyle(n).opacity);
        const inViewport=r.width>0&&r.height>0&&r.x<clientWidth&&r.right>0&&r.y<innerHeight&&r.bottom>0;
        const x=Math.max(0,Math.min(clientWidth-1,r.x+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2)),hit=inViewport?document.elementFromPoint(x,y):null;
        return{id,tag:e.tagName,text:e.textContent.slice(0,160),href:e.getAttribute('href'),resolvedHref:e.tagName==='A'?e.href:null,
          rect:{x:r.x,y:r.y,width:r.width,height:r.height},display:s.display,visibility:s.visibility,opacity,
          inViewport,centerOnTarget:!!hit&&(hit===e||e.contains(hit)),topTag:hit?.tagName??null,topId:hit?.id??null};})}})()`);
    const png=Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64');
    const stem=scenario+'-'+width;await writeFile(path.join(out,stem+'.png'),png);
    const quote=metrics.targets[0],old=dom.elements.find(e=>e.tag==='A'&&e.text==='Request a quote');
    check(stem+'-real-href-without-navigation',quote.href==='/rfq'&&quote.resolvedHref==='https://synthetic.invalid/rfq');
    check(stem+'-original-dom-unchanged',!!old&&old.visible===true&&!Object.hasOwn(old,'href'));
    if(scenario==='hidden')check(stem+'-box-is-not-visibility',quote.opacity===0&&old.visible);
    if(scenario==='covered')check(stem+'-box-is-not-center-hit',!quote.centerOnTarget&&old.visible);
    if(scenario==='overflow'&&width<560)check(stem+'-actual-overflow',metrics.scrollWidth>metrics.clientWidth);
    if(scenario==='clean')check(stem+'-positive-control',quote.opacity>0&&quote.centerOnTarget&&metrics.scrollWidth<=metrics.clientWidth);
    records.push({scenario,width,height,url,observedAt:new Date().toISOString(),dom,domSha256:hash(Buffer.from(JSON.stringify(dom))),metrics,
      screenshot:stem+'.png',screenshotSha256:hash(png),legacyV1DimensionsOnly:width===390||width===1280});
  }
  check('no-contact-or-write-request',requests.every(r=>r.method==='GET'&&new URL(r.url).pathname!=='/rfq'));
  check('all-observation-checks',checks.every(c=>c.pass));
  await writeFile(path.join(out,'receipt.json'),JSON.stringify({kind:'CONTROLLED_OFFLINE_CTA_SIDECAR',version:'c2-cta-offline-1.0.0',
    fixtureSha256:hash(fixture),legacyScriptSha256:hash(Buffer.from(legacy)),observerSha256:hash(await readFile(fileURLToPath(import.meta.url))),
    startedAt,finishedAt:new Date().toISOString(),browserVersion:version.product,records,requests,checks,
    nativeFactAdmission:'NONE',responseObservation:'UNKNOWN',submission:'UNKNOWN',delivery:'UNKNOWN'},null,2)+'\n');
}finally{
  if(ws?.readyState===WebSocket.OPEN){try{await call('Browser.close',{},null);}catch{}ws.close();}
  for(let i=0;i<100&&chrome&&!exitObserved;i++)await new Promise(r=>setTimeout(r,30));
  if(chrome&&!exitObserved){chrome.kill('SIGTERM');for(let i=0;i<100&&!exitObserved;i++)await new Promise(r=>setTimeout(r,30));}
  if(chrome&&!exitObserved){chrome.kill('SIGKILL');for(let i=0;i<100&&!exitObserved;i++)await new Promise(r=>setTimeout(r,30));}
  await writeFile(path.join(out,'cleanup.json'),JSON.stringify({chromePid:chrome?.pid,exitObserved}));await rm(profile,{recursive:true,force:true,maxRetries:3});
}
assert(exitObserved,'OWNED_CHROME_EXIT_UNOBSERVED');console.log(JSON.stringify({records:records.length,checks:checks.length,result:'PASS'}));
