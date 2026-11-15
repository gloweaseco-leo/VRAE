// Transport and cleanup reused from accepted PR89 browser.mjs; B5B-only journeys.
﻿// Actual Chromium, native cookie reception and real pointer/keyboard events.
// Never retain CDP request headers, token-bearing commands, HAR or raw HTML.
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir,writeFile,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import assert from 'node:assert/strict';
import {pointerPosition} from '../../docs/03-engineering/ra4c3-pg-read/browser-input.mjs';

const lines=readline.createInterface({input:process.stdin});
const rpcPending=new Map();let rpcSerial=0;
let initResolve;const initial=new Promise(r=>initResolve=r);
lines.on('line',line=>{const v=JSON.parse(line);if(v.type==='init')initResolve(v);else{const p=rpcPending.get(v.id);if(p){rpcPending.delete(v.id);v.error?p.reject(Error('PRIVATE_FIXTURE_RPC_FAILED')):p.resolve(v.result)}}});
function rpc(kind,data={}){return new Promise((resolve,reject)=>{const id=++rpcSerial;rpcPending.set(id,{resolve,reject});process.stdout.write(JSON.stringify({id,kind,...data})+'\n')})}
const config=await initial;
let origin=new URL(config.base).origin,base=origin+'/b5a/m2/';const out=config.output;
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(config.private,'chrome-'));
const chromePath=process.env.B5P0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
let chrome,ws,sid,serial=0,loaded=0,loginPending=null,browserVersion=null,phase='startup',step='startup';
const commands=[];
const pending=new Map(),records=[],network=[],shots=[],exceptions=[];
let privateStderr='';
const hash=b=>createHash('sha256').update(b).digest('hex');
function call(method,params={},sessionId=sid,timeout=30000){commands.push({method,event:'start'});if(commands.length>40)commands.shift();return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},timeout);pending.set(id,{resolve,reject,timer,method});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'BROWSER_EVALUATION_FAILED');return r.result.value}
async function check(name,condition,metadata={}){records.push({name,pass:!!condition,metadata});await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2));assert(condition,name)}
async function waitLoad(before){for(let i=0;i<1500;i++){if(loaded>before&&await ev("document.readyState==='complete'"))return;await new Promise(r=>setTimeout(r,20))}throw Error('BROWSER_LOAD_TIMEOUT')}
async function nav(url){const before=loaded;await call('Page.navigate',{url});await waitLoad(before)}
async function click(selector,navigation=false){const point=await pointerPosition(ev,selector);const before=loaded;await call('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});if(navigation)await waitLoad(before)}
async function key(key,code,virtual){await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual});await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual})}
async function select(selector,index){await click(selector);await key('Home','Home',36);for(let i=0;i<index;i++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13)}
async function screenshot(name){await ev('window.scrollTo(0,0)');const width=await ev('innerWidth'),height=await ev('document.documentElement.scrollHeight');const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height,scale:1}});const raw=Buffer.from(r.data,'base64');await writeFile(path.join(out,name),raw);shots.push({file:name,sha256:hash(raw),width,height,viewportHeight:await ev('innerHeight')})}
async function metrics(label){const m=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,scripts:document.scripts.length,banner:parseFloat(getComputedStyle(document.querySelector('.private-bar')).fontSize),footer:document.querySelector('footer')?.textContent||'',controls:[...document.querySelectorAll('.action,button,select,textarea,summary,.check')].filter(e=>e.getClientRects().length).map(e=>({height:e.getBoundingClientRect().height,name:e.id||e.name||e.tagName})),external:[...document.querySelectorAll('[src],[href]')].map(e=>e.src||e.href).filter(u=>u.startsWith('http')&&!u.startsWith(location.origin)),jwt:/eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+/.test(document.documentElement.outerHTML)})`);await check(label,m.scroll<=m.width&&m.scripts===0&&m.banner>=12&&m.external.length===0&&!m.jwt&&m.controls.every(c=>c.height>=44)&&m.footer.includes('仅保存内部演练记录')&&!m.footer.includes('不保存核对结果'),m)}
async function login(caseName) {
  step='login-page'; await nav(base);
  const csrf=await ev("document.querySelector('[name=_csrf]').value");
  await select('[name=case]',caseName==='404'?0:1);
  await click('button[type=submit]',true);
  const challenge=JSON.parse(await ev('document.body.innerText'));
  const token=await rpc('sign',{nonce:challenge.nonce,case:caseName});
  const jar=await call('Network.getCookies',{urls:[base]});
  const c=jar.cookies.find(c=>c.name==='b5a_m2_challenge');
  loginPending={token,csrf:challenge.csrf,cookie:'b5a_m2_challenge='+c.value};
  step='session'; await nav(base+'session');
  await check('real-signed-new-result-'+phase,await ev("location.pathname==='/b5a/m2/report'&&!!document.querySelector('form[action=\"/b5a/m2/review\"]')"));
  const cookies=await call('Network.getCookies',{urls:[base]});
  const session=cookies.cookies.find(c=>c.name==='b5a_m2_session');
  await check('httponly-new-result-session-'+phase,!!session&&session.httpOnly&&session.sameSite==='Strict'&&session.path==='/b5a/m2/');
}
try{
  chrome=spawn(chromePath,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROMIUM_START_TIMEOUT')),30000);chrome.on('error',()=>reject(Error('CHROMIUM_START_FAILED')));chrome.stderr.on('data',d=>{privateStderr+=d;const m=privateStderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',()=>reject(Error('CDP_CONNECT_FAILED')),{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){commands.push({method:p.method,event:m.error?'error':'complete'});if(commands.length>40)commands.shift();pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}}
    if(m.method==='Page.loadEventFired'&&m.sessionId===sid)loaded++;
    if(m.method==='Network.responseReceived'){const r=m.params.response;network.push({path:new URL(r.url).pathname,status:r.status,cache:r.fromDiskCache||false})}
    if(m.method==='Runtime.exceptionThrown')exceptions.push({description:'BROWSER_EXCEPTION'});
    if(m.method==='Fetch.requestPaused')void(async()=>{const r=m.params;const u=new URL(r.request.url);
      if(u.origin!==origin){await call('Fetch.failRequest',{requestId:r.requestId,errorReason:'BlockedByClient'},m.sessionId);return}
      if(u.pathname==='/b5a/m2/session'&&loginPending){const auth=loginPending;loginPending=null;await call('Fetch.continueRequest',{requestId:r.requestId,method:'POST',postData:Buffer.from('{}').toString('base64'),headers:[{name:'Origin',value:origin},{name:'Content-Type',value:'application/json'},{name:'Authorization',value:auth.token},{name:'X-M2-CSRF',value:auth.csrf},{name:'Cookie',value:auth.cookie}]},m.sessionId)}
      else await call('Fetch.continueRequest',{requestId:r.requestId},m.sessionId);
    })().catch(()=>{exceptions.push({description:'BROWSER_TRANSPORT_FAILED'})});
  });
  const version=browserVersion=await call('Browser.getVersion',{},null);

  async function bounded(name) {
    const m=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,scripts:document.scripts.length,external:[...document.querySelectorAll('[src],[href]')].map(e=>e.src||e.href).filter(u=>u.startsWith('http')&&!u.startsWith(location.origin)),jwt:/eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+/.test(document.documentElement.outerHTML),controls:[...document.querySelectorAll('button,a.action')].filter(e=>e.getClientRects().length).map(e=>e.getBoundingClientRect().height)})`);
    await check(name,m.scroll<=m.width&&m.scripts===0&&!m.jwt&&m.external.length===0&&m.controls.every(h=>h>=44),m);
  }
  // One actual staff browser tab across viewport/task navigation. Repeatedly
  // disposing incognito contexts is not part of the user journey under test.
  const context=await call('Target.createBrowserContext',{},null);
  const target=await call('Target.createTarget',{url:'about:blank',browserContextId:context.browserContextId},null);
  const attached=await call('Target.attachToTarget',{targetId:target.targetId,flatten:true},null);sid=attached.sessionId;
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  for(const width of [1280,375,320]) for(const caseName of ['404','200']) {
    phase=width+'/'+caseName;step='viewport';
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await login(caseName);
    const pins=config.pins[caseName];
    await check('exact-new-job-and-file-hash-'+phase,await ev(`document.body.innerText.includes(${JSON.stringify(pins.job_id)})&&document.body.innerText.includes(${JSON.stringify(pins.report_sha256)})`));
    await check('actual-evidence-and-guard-'+phase,await ev("document.body.innerText.includes('Evidence')&&document.body.innerText.includes('Guard')&&document.body.innerText.includes('NOT APPROVED')"));
    if(caseName==='200') await check('no-invented-issue-on-200-'+phase,await ev("document.querySelectorAll('.m2-issue').length===0&&document.body.innerText.includes('证据不足')"));
    else await check('actual-supported-issue-on-404-'+phase,await ev("document.querySelectorAll('.m2-issue').length===1&&document.body.innerText.includes('HTTP 404')"));
    await bounded('bounded-generated-report-'+phase);
    await screenshot('report-'+width+'-'+caseName+'.png');
    for(const selector of await ev("[...document.querySelectorAll('select[name^=decision]')].map(e=>'[name=\"'+e.name+'\"]')")) await select(selector,3);
    for(const selector of await ev("[...document.querySelectorAll('textarea')].map(e=>'[name=\"'+e.name+'\"]')")) {
      await click(selector);await call('Input.insertText',{text:'内部合成审核修订，请复核本版来源与证据。'});
    }
    step='save';await click('button[type=submit]',true);
    await check('real-persistent-review-receipt-'+phase,await ev("location.pathname.startsWith('/b5a/m2/receipt/')&&document.body.innerText.includes('已持久化')&&document.body.innerText.includes('REVISE_INTERNAL')"));
    await check('not-human-or-external-approval-'+phase,await ev("document.body.innerText.includes('NOT_APPROVED')&&document.body.innerText.includes('false')&&document.body.innerText.includes('不是实际人工批准')"));
    await click('[data-key=m2-a4]',true);
    await check('watermarked-version-bound-a4-'+phase,await ev(`document.querySelector('.m2-watermark')?.textContent.includes('合成样本')&&document.body.innerText.includes(${JSON.stringify(pins.report_sha256)})&&document.body.innerText.includes('REVISE_INTERNAL')`));
    await check('bounded-a4-screen-'+phase,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0"));
    await screenshot('a4-'+width+'-'+caseName+'.png');
    if(width===1280) {
      step='pdf';
      const r=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
      const pdf=Buffer.from(r.data,'base64');
      const pages=(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;
      await writeFile(path.join(out,'a4-'+caseName+'.pdf'),pdf);
      await check('one-real-A4-PDF-'+caseName,pages===1,{pages,sha256:hash(pdf),bytes:pdf.length});
    }
  }
  await call('Target.disposeBrowserContext',{browserContextId:context.browserContextId},null);
  await check('no-browser-exceptions',exceptions.length===0);
  await writeFile(path.join(out,'browser.json'),JSON.stringify({status:'M2_REAL_SIGNED_GENERATED_REPORT_REVIEW_A4_NOT_TASK_SUBMISSION',version,records,shots,network,exceptions},null,2));
  process.stdout.write(JSON.stringify({kind:'done',pass:true,assertions:records.length,screenshots:shots.length})+'\n');
}catch(error){await writeFile(path.join(out,'browser-failure.json'),JSON.stringify({status:'RED',code:error.message,phase,step,commands,version:browserVersion,records,network,exceptions},null,2));process.stdout.write(JSON.stringify({kind:'done',pass:false,code:error.message})+'\n');process.exitCode=1}
finally{
  let graceful=false,forced=false;
  try{if(ws?.readyState===WebSocket.OPEN){await call('Browser.close',{},null,5000);graceful=true}}catch{}
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}pending.clear();ws?.close();
  if(chrome&&chrome.exitCode===null&&chrome.signalCode===null)await new Promise(resolve=>{const timer=setTimeout(()=>{forced=true;chrome.kill();resolve()},3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()})});
  if(chrome&&chrome.exitCode===null&&chrome.signalCode===null)await new Promise(resolve=>{const timer=setTimeout(resolve,3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()})});
  await writeFile(path.join(out,'browser-process-cleanup.json'),JSON.stringify({exit_observed:!!chrome&&(chrome.exitCode!==null||chrome.signalCode!==null),exit_code:chrome?.exitCode??null,signal:chrome?.signalCode??null,graceful,forced}));
  lines.close()
}
