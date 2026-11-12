// Actual SSR navigation and native source disclosure in local Chromium; no packages.
import {spawn,execFileSync} from 'node:child_process';
import {mkdir,mkdtemp,writeFile,readFile,readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const own=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(own,'../../..');
const out=path.join(own,'evidence','browser-'+new Date().toISOString().replace(/[:.]/g,'-'));
await mkdir(out,{recursive:true});
const sourceHead=execFileSync('git',['rev-parse','HEAD'],{cwd:root,windowsHide:true}).toString().trim();
const app=path.join(root,'apps/operator_console'),sourceHashes={};
for(const name of await readdir(app)){if(/\.(py|css|json)$/.test(name))sourceHashes[name]=createHash('sha256').update(await readFile(path.join(app,name))).digest('hex')}
const profile=await mkdtemp(path.join(out,'profile-'));
const py=process.env.RA4C0_PYTHON||path.resolve(root,'../ra2b3/.venv/Scripts/python.exe');
const server=spawn(py,['-B','-m','apps.operator_console.preview','--test-only','--synthetic-fixtures'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
let serverLog='',serverError='',chrome,ws,sid,serial=0,stderr='',version,base;
const pending=new Map(),loaded=new Map(),commands=[],network=[],responses=[],exceptions=[],records=[],shots=[];
server.stdout.on('data',d=>{serverLog+=d});server.stderr.on('data',d=>{serverError+=d});
function call(method,params={},sessionId){commands.push({method,params,sessionId});return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sid);assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value}
async function check(id,expression,details={}){const observed=typeof expression==='string'?await ev(expression):expression;records.push({id,pass:!!observed,observed,details});await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2));assert(observed,id)}
async function waitReady(fragment){for(let i=0;i<150;i++){if(await ev(`document.readyState==='complete'&&location.href.includes(${JSON.stringify(fragment)})`))return;await new Promise(r=>setTimeout(r,40))}throw Error('NAVIGATION_TIMEOUT_'+fragment)}
async function waitLoad(before){for(let i=0;i<1500;i++){if((loaded.get(sid)||0)>before)return;await new Promise(r=>setTimeout(r,20))}throw Error('DOCUMENT_LOAD_TIMEOUT')}
async function navigate(url){const before=loaded.get(sid)||0;await call('Page.navigate',{url},sid);await waitLoad(before);await waitReady(new URL(url).pathname)}
async function key(key,code,virtual,extra={}){await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual,...extra},sid);await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual},sid)}
async function click(selector,fragment){await ev(`(()=>{document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'center'});return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))})()`);const p=await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)}),r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);const before=loaded.get(sid)||0;await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1},sid);await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1},sid);if(fragment){await waitLoad(before);await waitReady(fragment)}}
async function screenshot(name,full=false){await ev('window.scrollTo(0,0)');const width=await ev('innerWidth'),height=full?await ev('document.documentElement.scrollHeight'):await ev('innerHeight');const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:full,...(full?{clip:{x:0,y:0,width,height,scale:1}}:{})},sid);const b=Buffer.from(r.data,'base64');await writeFile(path.join(out,name),b);shots.push({file:name,width,height,sha256:createHash('sha256').update(b).digest('hex')})}
async function metrics(id){const result=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,bannerSize:parseFloat(getComputedStyle(document.querySelector('.private-bar')).fontSize),banner:document.querySelector('.private-bar').innerText,actions:[...document.querySelectorAll('.action,button,input,select,summary')].map(e=>({text:e.innerText||e.name,height:e.getBoundingClientRect().height})),external:[...document.querySelectorAll('[src],[href]')].map(e=>e.src||e.href).filter(u=>u.startsWith('http')&&!u.startsWith(location.origin)),scripts:document.scripts.length})`);await check(id,result.scroll<=result.width&&result.bannerSize>=12&&result.banner.includes('NOT APPROVED')&&result.external.length===0&&result.scripts===0&&result.actions.every(a=>a.height>=44),result)}
try{
  for(let i=0;i<300&&!serverLog.includes('\n');i++)await new Promise(r=>setTimeout(r,50));
  base=JSON.parse(serverLog.trim()).url;
  const chromePath=process.env.RA4C0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
  chrome=spawn(chromePath,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROMIUM_TIMEOUT')),20000);chrome.on('error',reject);chrome.stderr.on('data',d=>{stderr+=d;const m=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}if(m.method==='Page.loadEventFired')loaded.set(m.sessionId,(loaded.get(m.sessionId)||0)+1);if(m.method==='Network.requestWillBeSent')network.push(m.params);if(m.method==='Network.responseReceived')responses.push(m.params);if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params);if(m.method==='Fetch.requestPaused'){const u=m.params.request.url;void call('Fetch.'+(u.startsWith(new URL(base).origin+'/')?'continueRequest':'failRequest'),{requestId:m.params.requestId,...(!u.startsWith(new URL(base).origin+'/')?{errorReason:'BlockedByClient'}:{})},m.sessionId)}});
  version=await call('Browser.getVersion');
  for(const width of [1280,375,320]){
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true}));
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);await call('Fetch.enable',{patterns:[{urlPattern:'*'}]},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height:width===1280?1000:812,deviceScaleFactor:1,mobile:width<640},sid);
    await navigate(base);await metrics(`${width}-pool-metrics`);await screenshot(`pool-${width}.png`,true);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sid);await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sid);
    await check(`${width}-keyboard-focus-ring`,`(()=>{const e=document.activeElement;return e.tagName==='A'&&getComputedStyle(e).outlineStyle!=='none'&&e.innerText.includes('跳至')})()`);
    for(const c of ['404','200']){
      await click(`[data-key="task-${c}"]`,`/tasks/task-${c}`);await metrics(`${width}-${c}-detail-metrics`);
      await click('[data-key="review"]',`/tasks/task-${c}/review`);await metrics(`${width}-${c}-review-metrics`);await screenshot(`review-${c}-${width}.png`,true);
      await check(`${width}-${c}-facts-vs-hypotheses`,c==='404'?`document.body.innerText.includes('SOURCE_FACT_BINDING_VERIFIED')&&document.body.innerText.includes('HUMAN_REVIEW_REQUIRED')`:`document.body.innerText.includes('0 条已证实问题')&&document.body.innerText.includes('没有 CTA Claim / Guard 绑定')`);
      await click('[data-key="target"]',`/tasks/task-${c}/target`);
      await metrics(`${width}-${c}-target-metrics`);
      await check(`${width}-${c}-target-conditions`,`document.body.innerText.includes('审核条件尚未满足')&&!document.querySelector('button')&&document.body.innerText.includes('没有任何项目被人工接受或批准')`);
      if(c==='200')await check(`${width}-zero-target-h0-null`,`document.body.innerText.includes('native H0 = null')&&document.body.innerText.includes('native ReportVersion = null')&&document.body.innerText.includes('仅内部覆盖核对')`);
      await click('#target-pins > summary');
      const digest=c==='404'?'5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256':'c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050';
      await check(`${width}-${c}-accepted-original-target-digest`,`document.querySelector('#target-pins').innerText.includes(${JSON.stringify(digest)})&&document.querySelector('#target-pins').innerText.includes('renderer_asset_sha256')&&document.querySelector('#target-pins').innerText.includes('policy_snapshot_sha256')`);
      await click('#target-limits > summary');await metrics(`${width}-${c}-target-expanded`);await screenshot(`target-${c}-${width}.png`,true);
      await writeFile(path.join(out,`target-${c}-${width}.html`),await ev('document.documentElement.outerHTML'));
      await click(c==='404'?'[data-key="target-source"]':'[data-key="target-capture"]',`/tasks/task-${c}/evidence/`);
      await check(`${width}-${c}-target-bound-source`,`location.search.includes('target=')&&document.body.innerText.includes('2026-11-10T12:00:00+00:00')&&document.querySelector('[data-key="back-target"]')`);
      await screenshot(`target-source-${c}-${width}.png`,true);
      await click('[data-key="back-target"]',`/tasks/task-${c}/target`);
      await call('Page.navigateToHistoryEntry',{entryId:(await call('Page.getNavigationHistory',{},sid)).entries.slice(-2,-1)[0].id},sid);
      await waitReady(`/tasks/task-${c}/evidence/`);await check(`${width}-${c}-history-back-preserves-pins`,`location.search.includes(${JSON.stringify(digest)})`);
      const history=await call('Page.getNavigationHistory',{},sid);
      await call('Page.navigateToHistoryEntry',{entryId:history.entries[history.currentIndex+1].id},sid);
      await waitReady(`/tasks/task-${c}/target`);await check(`${width}-${c}-history-forward-preserves-pins`,`location.search.includes(${JSON.stringify(digest)})&&document.body.innerText.includes('审核条件尚未满足')`);
      await click('[data-key="target-back-review"]',`/tasks/task-${c}/review`);
      await click('[data-key="evidence-primary"]',`/tasks/task-${c}/evidence/`);await metrics(`${width}-${c}-evidence-metrics`);
      await check(`${width}-${c}-native-provenance`,`document.body.innerText.includes('https://example.org/products/mp-25')&&document.body.innerText.includes('2026-11-10T12:00:00+00:00')&&document.body.innerText.includes('ev-')`);
      await click('details > summary');await check(`${width}-${c}-raw-bytes-visible`,`document.querySelector('details').open&&document.querySelector('details pre').textContent.includes('<a href="/contact">')&&!document.querySelector('details script')`);
      await metrics(`${width}-${c}-expanded-metrics`);await screenshot(`evidence-${c}-${width}.png`,true);
      const html=await ev('document.documentElement.outerHTML');await writeFile(path.join(out,`evidence-${c}-${width}.html`),html);
      await click('[data-key="back-review"]',`/tasks/task-${c}/review`);await click('[data-key="back-detail"]',`/tasks/task-${c}`);await click('[data-key="back-pool"]',new URL(base).pathname);
      await check(`${width}-${c}-return-to-pool`,`document.querySelectorAll('.task').length===11`);
    }
    for(const task of ['403','unknown']){
      await click(`[data-key="task-${task}"]`,`/tasks/task-${task}`);await check(`${width}-${task}-neutral-no-report`,`document.body.innerText.includes('不能据此判断网站缺陷')&&!document.querySelector('[data-key="review"]')`);await screenshot(`blocked-${task}-${width}.png`,true);await click('[data-key="back-pool"]',new URL(base).pathname);
    }
    await click('select[name="stage"]');await key('Home','Home',36);for(let n=0;n<6;n++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13);
    await click('input[name="q"]');await call('Input.insertText',{text:'工业泵'},sid);await click('button[type="submit"]');await waitReady('?stage=REVIEW_REQUIRED');
    await check(`${width}-real-filter-request`,`document.querySelectorAll('.task').length===1&&document.querySelector('.task').innerText.includes('404')&&document.querySelector('select').value==='REVIEW_REQUIRED'&&document.querySelector('input').value==='工业泵'`);
    await navigate(base+'?q='+encodeURIComponent('<script>alert(1)</script>'));await check(`${width}-query-injection-inert`,`document.scripts.length===0&&document.body.innerText.includes('没有匹配')`);
    await navigate(base+'tasks/task-404/review?version=2&draft=rd-stale');await check(`${width}-stale-denial`,`document.body.innerText.includes('STALE_VERSION')&&!document.body.innerText.includes('Captured static href')`);
    await navigate(base+'tasks/task-404/target?version=1&draft=rd-forged&target='+('0'.repeat(64)));await check(`${width}-target-denial-no-source`,`document.body.innerText.includes('STALE_VERSION')&&!document.body.innerText.includes('ev-')&&!document.querySelector('[data-key="target-source"]')`);
    await call('Target.closeTarget',{targetId});
  }
  await check('zero-external-network',network.every(r=>r.request.url.startsWith(new URL(base).origin+'/')),{requests:network.length});
  await check('no-script-exceptions',exceptions.length===0);
  for(const [name,target,opts,status] of [
    ['no-fixture-context',new URL(base).origin+'/',{},403],
    ['foreign-origin',base,{headers:{Origin:'https://evil.example'}},403],
    ['mutation',base+'tasks/task-404/approve',{method:'POST'},501],
    ['url-input',base+'?url=https://evil.example',{},400],
  ]){const r=await fetch(target,opts);await check(name,r.status===status,{status:r.status,body:await r.text()})}
  for(const [name,hash] of Object.entries(sourceHashes))assert.equal(createHash('sha256').update(await readFile(path.join(app,name))).digest('hex'),hash,'SOURCE_CHANGED_'+name);
}catch(error){await writeFile(path.join(out,'failure.txt'),error.stack);process.exitCode=1}
finally{
  await writeFile(path.join(out,'raw-cdp.json'),JSON.stringify({commands,network,responses,exceptions},null,2));
  await writeFile(path.join(out,'receipt.json'),JSON.stringify({version,sourceHead,sourceHashes,mode:'SYNTHETIC_TEST_ONLY',assertions:records.length,passed:records.filter(r=>r.pass).length,screenshots:shots,networkCount:network.length,serverError},null,2));
  await writeFile(path.join(out,'chromium-stderr.txt'),stderr);await writeFile(path.join(out,'server-stderr.txt'),serverError);
  if(ws)ws.close();if(chrome)chrome.kill();server.kill();
  console.log(JSON.stringify({out,assertions:records.length,failures:records.filter(r=>!r.pass),exitCode:process.exitCode||0}));
}
