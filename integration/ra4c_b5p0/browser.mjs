// Actual Chromium, native cookie reception and real pointer/keyboard events.
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
let origin=new URL(config.base).origin,base=origin+'/b5a/';const out=config.output;
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(config.private,'chrome-'));
const chromePath=process.env.B5P0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
let chrome,ws,sid,serial=0,loaded=0,loginPending=null,browserVersion=null,phase='startup';
const pending=new Map(),records=[],network=[],shots=[],exceptions=[];
let privateStderr='';
const hash=b=>createHash('sha256').update(b).digest('hex');
function call(method,params={},sessionId=sid,timeout=30000){return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},timeout);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'BROWSER_EVALUATION_FAILED');return r.result.value}
async function check(name,condition,metadata={}){records.push({name,pass:!!condition,metadata});await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2));assert(condition,name)}
async function waitLoad(before){for(let i=0;i<1500;i++){if(loaded>before&&await ev("document.readyState==='complete'"))return;await new Promise(r=>setTimeout(r,20))}throw Error('BROWSER_LOAD_TIMEOUT')}
async function nav(url){const before=loaded;await call('Page.navigate',{url});await waitLoad(before)}
async function click(selector,navigation=false){const point=await pointerPosition(ev,selector);const before=loaded;await call('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1});if(navigation)await waitLoad(before)}
async function key(key,code,virtual){await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual});await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual})}
async function select(selector,index){await click(selector);await key('Home','Home',36);for(let i=0;i<index;i++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13)}
async function screenshot(name){await ev('window.scrollTo(0,0)');const width=await ev('innerWidth'),height=await ev('document.documentElement.scrollHeight');const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height,scale:1}});const raw=Buffer.from(r.data,'base64');await writeFile(path.join(out,name),raw);shots.push({file:name,sha256:hash(raw),width,height,viewportHeight:await ev('innerHeight')})}
async function metrics(label){const m=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,scripts:document.scripts.length,banner:parseFloat(getComputedStyle(document.querySelector('.private-bar')).fontSize),footer:document.querySelector('footer')?.textContent||'',controls:[...document.querySelectorAll('.action,button,select,textarea,summary,.check')].filter(e=>e.getClientRects().length).map(e=>({height:e.getBoundingClientRect().height,name:e.id||e.name||e.tagName})),external:[...document.querySelectorAll('[src],[href]')].map(e=>e.src||e.href).filter(u=>u.startsWith('http')&&!u.startsWith(location.origin)),jwt:/eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+/.test(document.documentElement.outerHTML)})`);await check(label,m.scroll<=m.width&&m.scripts===0&&m.banner>=12&&m.external.length===0&&!m.jwt&&m.controls.every(c=>c.height>=44)&&m.footer.includes('仅保存内部演练记录')&&!m.footer.includes('不保存核对结果'),m)}
async function login(caseName,{tokenOverride,denied=false}={}){
  await nav(base+'login');
  const csrf=await ev("document.querySelector('[name=_bootstrap_csrf]').value");
  const before=loaded;
  await ev(`(()=>{const f=document.createElement('form');f.method='post';f.action='/b5a/challenge';for(const [name,value] of Object.entries({task:${JSON.stringify('task-'+caseName)},_csrf:${JSON.stringify(csrf)}})){const e=document.createElement('input');e.type='hidden';e.name=name;e.value=value;f.append(e)}document.body.append(f);f.submit();return true})()`);
  await waitLoad(before);
  const challenge=JSON.parse(await ev('document.body.innerText'));
  const token=tokenOverride||await rpc('sign',{nonce:challenge.nonce,case:caseName});
  const cookies=await call('Network.getCookies',{urls:[base]});
  const challengeCookie=cookies.cookies.find(c=>c.name==='b5a_challenge');
  assert(challengeCookie?.httpOnly&&challengeCookie.sameSite==='Strict');
  loginPending={token,csrf:challenge.csrf,cookie:'b5a_challenge='+challengeCookie.value};
  await nav(base+'session');
  if(denied){await check('consumed-token-after-process-restart-denied',await ev("document.body.innerText.includes('UNAUTHORIZED')&&!document.querySelector('[data-key=b5a-session]')"));return}
  await check('actual-browser-signed-login-'+caseName,await ev("location.pathname==='/b5a/'&&!!document.querySelector('[data-key=b5a-session]')"));
  const jar=await call('Network.getCookies',{urls:[base]});
  const session=jar.cookies.find(c=>c.name==='b5a_session');
  await check('native-httponly-session-cookie-'+caseName,!!session&&session.httpOnly&&session.sameSite==='Strict'&&session.path==='/b5a/'&&session.value.length===43&&!(await ev('document.cookie')).includes('b5a_session'));
  return token;
}

try{
  chrome=spawn(chromePath,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROMIUM_START_TIMEOUT')),30000);chrome.on('error',()=>reject(Error('CHROMIUM_START_FAILED')));chrome.stderr.on('data',d=>{privateStderr+=d;const m=privateStderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',()=>reject(Error('CDP_CONNECT_FAILED')),{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}}
    if(m.method==='Page.loadEventFired'&&m.sessionId===sid)loaded++;
    if(m.method==='Network.responseReceived'){const r=m.params.response;network.push({path:new URL(r.url).pathname,status:r.status,cache:r.fromDiskCache||false})}
    if(m.method==='Runtime.exceptionThrown')exceptions.push({description:'BROWSER_EXCEPTION'});
    if(m.method==='Fetch.requestPaused')void(async()=>{const r=m.params;const u=new URL(r.request.url);
      if(u.origin!==origin){await call('Fetch.failRequest',{requestId:r.requestId,errorReason:'BlockedByClient'},m.sessionId);return}
      if(u.pathname==='/b5a/session'&&loginPending){const auth=loginPending;loginPending=null;await call('Fetch.continueRequest',{requestId:r.requestId,method:'POST',postData:Buffer.from('{}').toString('base64'),headers:[{name:'Origin',value:origin},{name:'Content-Type',value:'application/json'},{name:'Authorization',value:auth.token},{name:'X-B5A-CSRF',value:auth.csrf},{name:'Cookie',value:auth.cookie}]},m.sessionId)}
      else await call('Fetch.continueRequest',{requestId:r.requestId},m.sessionId);
    })().catch(()=>{exceptions.push({description:'BROWSER_TRANSPORT_FAILED'})});
  });
  const version=browserVersion=await call('Browser.getVersion',{},null);
  const receipts=new Map();
  for(const width of [1280,375,320]){
    for(const caseName of ['404','200']){
      phase=`${width}/${caseName}/new-native-context`;
      const context=await call('Target.createBrowserContext',{},null);
      const target=await call('Target.createTarget',{url:'about:blank',browserContextId:context.browserContextId},null);
      const attached=await call('Target.attachToTarget',{targetId:target.targetId,flatten:true},null);sid=attached.sessionId;
      await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
      await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      phase=`${width}/${caseName}/signed-login`;
      await login(caseName);
      phase=`${width}/${caseName}/original-form`;
      await click('[data-key=b5p0-entry]',true);
      const count=await ev("document.querySelectorAll('select[name^=disposition]').length");
      await check('exact-original-claims-'+width+'-'+caseName,count===(caseName==='404'?6:3));
      await metrics('rehearsal-form-'+width+'-'+caseName);
      await check('explicit-non-approval-action-'+width+'-'+caseName,await ev("document.querySelector('#save-rehearsal').textContent==='保存内部演练记录（非审批）'&&document.body.innerText.includes('NOT APPROVED')&&document.body.innerText.includes('没有法律或业务效力')"));
      for(let i=0;i<count;i++)await select('#disposition-'+i,1);
      const sections=await ev("[...document.querySelectorAll('#proposal-form .check input')].map(e=>e.name)");
      for(const name of sections)await click(`#proposal-form label.check:has(input[name=${JSON.stringify(name)}])`);
      await select('#proposal-action',1);
      await screenshot('form-'+width+'-'+caseName+'.png');
      await ev("document.querySelector('#save-rehearsal').focus()");
      await check('keyboard-focus-'+width+'-'+caseName,await ev("document.activeElement.id==='save-rehearsal'&&parseFloat(getComputedStyle(document.activeElement).outlineWidth)>=3"));
      const before=loaded;
      phase=`${width}/${caseName}/save-rehearsal`;
      if(width===375){
        await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',unmodifiedText:'\r',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});
        await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});
        await waitLoad(before)
      }
      else await click('#save-rehearsal',true);
      await check('durable-non-effective-receipt-'+width+'-'+caseName,await ev("!!document.querySelector('#rehearsal-receipt')&&document.body.innerText.includes('TEST_ONLY_REVIEW_INTENT')&&document.body.innerText.includes('NOT APPROVED')&&!document.body.innerText.includes('idempotency_key')&&!document.body.innerText.includes('witness')"));
      const digest=await ev("document.querySelector('[data-key=receipt-sha]').textContent");
      if(receipts.has(caseName))await check('same-durable-receipt-'+width+'-'+caseName,receipts.get(caseName)===digest);else receipts.set(caseName,digest);
      if(caseName==='200')await check('zero-only-coverage-'+width,await ev("document.body.innerText.includes('COVERAGE_ACK_TEST_ONLY')&&!document.body.innerText.includes('REVIEW_INTENT_TEST_ONLY')"));
      await metrics('receipt-'+width+'-'+caseName);
      await screenshot('receipt-'+width+'-'+caseName+'.png');
      const url=await ev('location.href');await nav(url+'/receipt');
      await check('authorized-get-raw-verified-receipt-'+width+'-'+caseName,await ev("document.querySelector('[data-key=receipt-sha]')?.textContent")===digest);
    }
  }
  const glyph=await ev(`(()=>{const c=document.createElement('canvas');c.width=160;c.height=48;const x=c.getContext('2d');x.font='24px "Microsoft YaHei", "Noto Sans CJK SC", sans-serif';x.fillText('核对原文',0,30);const a=Array.from(x.getImageData(0,0,160,48).data);x.clearRect(0,0,160,48);x.fillText('□□□□',0,30);const b=Array.from(x.getImageData(0,0,160,48).data);return {ink:a.filter(Boolean).length,distinct:a.some((v,i)=>v!==b[i])}})()`);
  await check('actual-chinese-glyph-raster',glyph.ink>100&&glyph.distinct,glyph);
  await check('no-browser-exceptions',exceptions.length===0);
  const report={status:'ACTUAL_B5P0_SIGNED_PG_INTENT_SSR_PASS',version,records,shots,network,exceptions};
  await writeFile(path.join(out,'browser.json'),JSON.stringify(report,null,2));
  process.stdout.write(JSON.stringify({kind:'done',pass:true,assertions:records.length,screenshots:shots.length})+'\n');
}catch(error){await writeFile(path.join(out,'browser-failure.json'),JSON.stringify({status:'RED',code:error.message,phase,version:browserVersion,records,network,exceptions},null,2));process.stdout.write(JSON.stringify({kind:'done',pass:false,code:error.message})+'\n');process.exitCode=1}
finally{
  let graceful=false,forced=false;
  try{if(ws?.readyState===WebSocket.OPEN){await call('Browser.close',{},null,5000);graceful=true}}catch{}
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}pending.clear();ws?.close();
  if(chrome&&chrome.exitCode===null&&chrome.signalCode===null)await new Promise(resolve=>{const timer=setTimeout(()=>{forced=true;chrome.kill();resolve()},3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()})});
  if(chrome&&chrome.exitCode===null&&chrome.signalCode===null)await new Promise(resolve=>{const timer=setTimeout(resolve,3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()})});
  await writeFile(path.join(out,'browser-process-cleanup.json'),JSON.stringify({exit_observed:!!chrome&&(chrome.exitCode!==null||chrome.signalCode!==null),exit_code:chrome?.exitCode??null,signal:chrome?.signalCode??null,graceful,forced}));
  lines.close()
}

