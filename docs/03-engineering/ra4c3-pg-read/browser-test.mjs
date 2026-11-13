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
await mkdir(path.join(own,'runtime'),{recursive:true});
const profile=await mkdtemp(path.join(own,'runtime','browser-profile-'));
const py=process.env.RA4C0_PYTHON||path.resolve(root,'../ra2b3/.venv/Scripts/python.exe');
const audit=path.join(out,'actual-db-reads.jsonl');
assert(process.env.RA4C3_PROFILE,'RA4C3_PROFILE_REQUIRED');
assert(process.env.RA4C3_STATE,'BOOTSTRAP_CONTROL_STATE_REQUIRED_OUTSIDE_HTTP');
const nativePins=JSON.parse(await readFile(path.join(app,'native-pins.json'),'utf8'));
const fixtureActions=[];
function fixtureAction(action){const raw=execFileSync(py,['-B','-m','integration.ra4c3.mutate_fixture',action],{cwd:root,windowsHide:true,env:process.env});fixtureActions.push(JSON.parse(raw.toString().trim()))}
const serverEnv={...process.env};delete serverEnv.RA4C3_STATE;
const server=spawn(py,['-B','-m','integration.ra4c3.http_preview','--profile',process.env.RA4C3_PROFILE,'--audit',audit],{cwd:root,env:serverEnv,windowsHide:true,stdio:['ignore','pipe','pipe']});
async function reads(){try{return (await readFile(audit,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse)}catch(e){if(e.code==='ENOENT')return[];throw e}}
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
  for(let i=0;i<3000&&!serverLog.includes('\n');i++)await new Promise(r=>setTimeout(r,50));
  base=JSON.parse(serverLog.trim()).url;
  const chromePath=process.env.RA4C0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
  chrome=spawn(chromePath,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROMIUM_TIMEOUT')),20000);chrome.on('error',reject);chrome.stderr.on('data',d=>{stderr+=d;const m=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}}if(m.method==='Page.loadEventFired')loaded.set(m.sessionId,(loaded.get(m.sessionId)||0)+1);if(m.method==='Network.requestWillBeSent')network.push(m.params);if(m.method==='Network.responseReceived')responses.push(m.params);if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params);if(m.method==='Fetch.requestPaused'){const u=m.params.request.url;void call('Fetch.'+(u.startsWith(new URL(base).origin+'/')?'continueRequest':'failRequest'),{requestId:m.params.requestId,...(!u.startsWith(new URL(base).origin+'/')?{errorReason:'BlockedByClient'}:{})},m.sessionId)}});
  version=await call('Browser.getVersion');
  async function formMetrics(id){
    const observed=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,banner:parseFloat(getComputedStyle(document.querySelector('.private-bar')).fontSize),controls:[...document.querySelectorAll('select,textarea,button,.check,.action,summary')].filter(e=>e.getClientRects().length).map(e=>({name:e.name||e.innerText,height:e.getBoundingClientRect().height})),scripts:document.scripts.length})`);
    await check(id,observed.width>=observed.scroll&&observed.banner>=12&&observed.scripts===0&&observed.controls.every(c=>c.height>=44),observed);
  }
  async function select(selector,index){await click(selector);await key('Home','Home',36);for(let n=0;n<index;n++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13);}
  async function fill(action=1,changed=null,reason=''){
    const count=await ev('document.querySelectorAll("select[name^=disposition]").length');
    for(let i=0;i<count;i++)await select(`#disposition-${i}`,changed?.index===i?changed.option:1);
    for(let i=0;i<4;i++)await click(`.ack-section:nth-of-type(${i+1}) .check`);
    await select('#proposal-action',action);
    if(reason){await click('#proposal-reason');await call('Input.insertText',{text:reason},sid)}
  }
  async function fresh(){await click('[data-key="new-proposal"]','/proposal?');}
  for(const width of [1280,375,320]){
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true}));
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);await call('Fetch.enable',{patterns:[{urlPattern:'*'}]},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height:width===1280?1000:812,deviceScaleFactor:1,mobile:width<640},sid);
    const beforeReads=(await reads()).length;
    await navigate(base);await check(`${width}-original-eleven-tasks`,`document.querySelectorAll('.task').length===11`);
    await call('DOM.enable',{},sid);await call('CSS.enable',{},sid);
    const dom=await call('DOM.getDocument',{},sid);
    const heading=await call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'h1'},sid);
    const fonts=await call('CSS.getPlatformFontsForNode',{nodeId:heading.nodeId},sid);
    await check(`${width}-actual-chinese-glyph-font`,fonts.fonts.some(f=>f.glyphCount>0&&/CJK|YaHei|PingFang|SimSun|Heiti|Noto Sans SC|Source Han|WenQuanYi|DengXian|JhengHei/i.test(f.familyName)),fonts);
    await check(`${width}-actual-db-read`,(await reads()).slice(beforeReads).some(e=>e.event==='spy_actual_p2a_read_returned'));
    await check(`${width}-explicit-db-mode`,`document.body.innerText.includes('PG16 TEST_ONLY')`);
    await key('Tab','Tab',9);await check(`${width}-keyboard-focus`,`document.activeElement.className==='skip'&&getComputedStyle(document.activeElement).outlineStyle!=='none'`);
    await click('[data-key="task-404"]','/tasks/task-404');await click('[data-key="review"]','/review?');
    await screenshot(`native-report-404-${width}.png`,true);
    await check(`${width}-original-source-sha`,await ev(`document.querySelector('[data-key=pg-origin]').innerHTML.includes(${JSON.stringify(nativePins.cases['404'].source_sha256)})`));
    await click('[data-key="target"]','/target?');
    await check(`${width}-original-target-intact`,`document.body.innerText.includes('审核条件尚未满足')&&document.querySelectorAll('[data-key="target-source"]').length===6`);
    await click('[data-key="proposal"]','/proposal?');const freshUrl=await ev('location.href');
    await formMetrics(`${width}-fresh-layout`);await screenshot(`proposal-fresh-404-${width}.png`,true);
    await check(`${width}-no-default-consent`,`[...document.querySelectorAll('select')].every(e=>e.value==='')&&[...document.querySelectorAll('[type=checkbox]')].every(e=>!e.checked)&&!document.querySelector('[data-outcome]')`);
    await check(`${width}-six-types-and-source-links`,`document.querySelectorAll('.claim-card').length===6&&document.querySelectorAll('[data-key="proposal-source"]').length===6&&document.body.innerText.includes('HUMAN_REVIEW_REQUIRED')&&document.body.innerText.includes('网站字面自述')`);
    await click('[data-key="proposal-source"]','/evidence/');await check(`${width}-exact-source`,`location.search.includes('target=5705ac')&&document.body.innerText.includes('UTF-8 字节 [158, 177)')`);
    await screenshot(`proposal-source-${width}.png`,true);
    const history=await call('Page.getNavigationHistory',{},sid);await call('Page.navigateToHistoryEntry',{entryId:history.entries[history.currentIndex-1].id},sid);await waitReady('/proposal?');
    await check(`${width}-back-keeps-target`,`location.href===${JSON.stringify(freshUrl)}`);
    const back=await call('Page.getNavigationHistory',{},sid);await call('Page.navigateToHistoryEntry',{entryId:back.entries[back.currentIndex+1].id},sid);await waitReady('/evidence/');
    await check(`${width}-forward-keeps-source-pin`,`location.search.includes('target=5705ac')`);await navigate(freshUrl);
    await fill();await check(`${width}-actual-selected-and-acknowledged`,`[...document.querySelectorAll('select')].every(e=>e.value)&&document.querySelectorAll('[type=checkbox]:checked').length===4`);
    await click('#preview-proposal','/proposal-preview');await formMetrics(`${width}-candidate-preview-layout`);
    await check(`${width}-candidate-pure-valid`,`document.querySelector('[data-outcome]').dataset.outcome==='CONTRACT_VALID_ONLY'&&document.body.innerText.includes('PRIVATE_NOT_APPROVED')&&document.body.innerText.includes('未产生决定')`);
    await screenshot(`candidate-preview-404-${width}.png`,true);await writeFile(path.join(out,`candidate-preview-${width}.html`),await ev('document.documentElement.outerHTML'));
    await fresh();await fill(2,{index:1,option:2},'第 2 项影响假设需要补充采购商路径研究。');await click('#preview-proposal','/proposal-preview');
    await check(`${width}-changes-located-reason`,`document.querySelector('[data-outcome]').dataset.outcome==='CONTRACT_VALID_ONLY'&&document.querySelector('#proposal-reason').value.includes('第 2 项')&&document.querySelector('#disposition-1').value==='CHANGE_REQUESTED'`);
    await screenshot(`request-changes-${width}.png`,true);
    await fresh();await fill(3,{index:1,option:3},'拒绝第 2 项：现有资料不足以支持该影响假设。');await click('#preview-proposal','/proposal-preview');
    await check(`${width}-reject-is-only-proposal`,`document.querySelector('[data-outcome]').dataset.outcome==='CONTRACT_VALID_ONLY'&&document.querySelector('#disposition-1').value==='REJECTED'&&document.body.innerText.includes('不是真人验收')`);await screenshot(`reject-proposal-${width}.png`,true);
    await fresh();await fill();
    await ev(`(()=>{const s=document.querySelector('#disposition-1');s.add(new Option('恶意提升为事实','ACK_LITERAL_FACT'));s.value='ACK_LITERAL_FACT'})()`);
    await click('#preview-proposal','/proposal-preview');await check(`${width}-native-ceiling-refusal`,`document.querySelector('[data-outcome]').dataset.outcome==='D_CLAIM_CEILING'`);await screenshot(`ceiling-refusal-${width}.png`,true);
    await fresh();await fill();await ev(`document.querySelector('input[name=target]').value='0'.repeat(64)`);await click('#preview-proposal','/proposal-preview');
    await check(`${width}-changed-target-denied-no-source`,`document.body.innerText.includes('STALE_VERSION')&&!document.body.innerText.includes('ev-')&&!document.querySelector('[name^=disposition]')`);await screenshot(`stale-refusal-${width}.png`,true);
    await navigate(freshUrl);await fill(3,{index:1,option:3},'<script>fetch("https://evil.example")</script>');await click('#preview-proposal','/proposal-preview');
    await check(`${width}-injection-escaped-inert`,`document.scripts.length===0&&document.querySelector('#proposal-reason').value.includes('<script>')&&document.querySelector('[data-outcome]').dataset.outcome==='CONTRACT_VALID_ONLY'`);
    await navigate(freshUrl);await check(`${width}-reopened-unsaved`,`!document.querySelector('[data-outcome]')&&document.querySelector('#proposal-action').value===''&&document.querySelectorAll('[type=checkbox]:checked').length===0`);
    await navigate(base);await click('[data-key="task-200"]','/tasks/task-200');await click('[data-key="review"]','/review?');await click('[data-key="target"]','/target?');await click('[data-key="proposal"]','/proposal?');
    await check(`${width}-zero-distinct-contract`,`document.querySelectorAll('.claim-card').length===3&&!document.querySelector('#proposal-action [value=APPROVE_CANDIDATE]')&&document.body.innerText.includes('在已检查的范围内未发现可确认问题')&&document.body.innerText.includes('native H0 = null')`);
    await fill();await click('#preview-proposal','/proposal-preview');await formMetrics(`${width}-zero-preview-layout`);
    await click('#checked-command > summary');
    await check(`${width}-zero-ack-not-approval`,`document.querySelector('[data-outcome]').dataset.outcome==='CONTRACT_VALID_ONLY'&&document.querySelector('#proposal-action').value==='SIMULATED_INTERNAL_SCOPE_ACK'&&document.querySelector('#checked-command').innerText.includes('COVERAGE_ACK_PROPOSAL')`);await screenshot(`coverage-ack-200-${width}.png`,true);
    await writeFile(path.join(out,`coverage-ack-${width}.html`),await ev('document.documentElement.outerHTML'));
    await navigate(base+'tasks/task-403');await check(`${width}-403-no-composer`,`document.body.innerText.includes('不能据此判断网站缺陷')&&!document.querySelector('[data-key=proposal]')`);
    await navigate(base+'tasks/task-unknown');await check(`${width}-unknown-no-composer`,`document.body.innerText.includes('不能据此判断网站缺陷')&&!document.querySelector('[data-key=proposal]')`);
    await call('Target.closeTarget',{targetId});
  }
  await check('zero-external-network',network.every(r=>r.request.url.startsWith(new URL(base).origin+'/')),{requests:network.length});
  await check('no-script-exceptions',exceptions.length===0);
  for(const [name,target,opts,status] of [
    ['no-fixture-context',new URL(base).origin+'/',{},403],
    ['foreign-origin',base,{headers:{Origin:'https://evil.example'}},403],
    ['mutation',base+'tasks/task-404/approve',{method:'POST'},501],
    ['url-input',base+'?url=https://evil.example',{},400],
  ]){const before=(await reads()).length;const r=await fetch(target,opts);await check(name,r.status===status,{status:r.status,body:await r.text()});await check(name+'-zero-byte-reads',(await reads()).length===before)}
  {
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true}));
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);
    await call('Emulation.setDeviceMetricsOverride',{width:375,height:812,deviceScaleFactor:1,mobile:true},sid);
    fixtureAction('revoke');
    try{await navigate(base+'tasks/task-404');await check('browser-revoked-policy-denied',responses.filter(r=>r.type==='Document').at(-1).response.status===403);await check('browser-revoked-no-report',`!document.querySelector('.issue,.claim-card,[data-key=review]')`);await screenshot('blocked-policy-375.png',true)}
    finally{fixtureAction('restore')}
    await navigate(base+'tasks/task-404');await check('browser-policy-restored',responses.filter(r=>r.type==='Document').at(-1).response.status===200);
    fixtureAction('stop-db');
    await navigate(base+'tasks/task-404');await check('browser-stopped-db-503',responses.filter(r=>r.type==='Document').at(-1).response.status===503);
    await check('browser-db-down-no-fallback',`!document.querySelector('.issue,.claim-card,[data-key=review]')&&!document.body.innerText.includes('password')`);await screenshot('blocked-database-375.png',true);
    await call('Target.closeTarget',{targetId});
  }
  for(const [name,hash] of Object.entries(sourceHashes))assert.equal(createHash('sha256').update(await readFile(path.join(app,name))).digest('hex'),hash,'SOURCE_CHANGED_'+name);
}catch(error){await writeFile(path.join(out,'failure.txt'),error.stack);process.exitCode=1}
finally{
  await writeFile(path.join(out,'fixture-actions.json'),JSON.stringify(fixtureActions,null,2));
  await writeFile(path.join(out,'raw-cdp.json'),JSON.stringify({commands,network,responses,exceptions},null,2));
  await writeFile(path.join(out,'receipt.json'),JSON.stringify({version,sourceHead,sourceHashes,mode:'PG16_TEST_ONLY_READ',assertions:records.length,passed:records.filter(r=>r.pass).length,screenshots:shots,networkCount:network.length,actualDbReads:await reads(),serverError},null,2));
  await writeFile(path.join(out,'chromium-stderr.txt'),stderr);await writeFile(path.join(out,'server-stderr.txt'),serverError);
  if(ws)ws.close();if(chrome)chrome.kill();server.kill();
  console.log(JSON.stringify({out,assertions:records.length,failures:records.filter(r=>!r.pass),exitCode:process.exitCode||0}));
}
