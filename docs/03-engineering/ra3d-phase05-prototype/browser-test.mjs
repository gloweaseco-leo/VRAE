// Real local Chromium + CDP. No dependencies; no production modules imported.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const runId=new Date().toISOString().replace(/[:.]/g,'-');
const out=path.join(here,'evidence','browser-'+runId);
await mkdir(out,{recursive:true});
await mkdir(path.join(out,'input-files'),{recursive:true});
for(const f of ['index.html','workbench.css','workbench.js','fixtures.js','fixtures.json','browser-test.mjs'])await writeFile(path.join(out,'input-files',f),await readFile(path.join(here,f)));
const profile=await mkdtemp(path.join(out,'profile-'));
const chrome=process.env.RA3D_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const args=['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=<-loopback>','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',`--user-data-dir=${profile}`,`--disk-cache-dir=${profile}/cache`,'about:blank'];
const proc=spawn(chrome,args,{windowsHide:true,stdio:['ignore','pipe','pipe']});
let stderr='',ws,version,sid;let serial=0;const pending=new Map(),network=[],exceptions=[],records=[],shots=[],commands=[];
let infrastructureError=null;
const sha=b=>createHash('sha256').update(b).digest('hex');
function call(method,params={},sessionId){commands.push({method,params,sessionId});return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP_TIMEOUT_'+method))},20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sid);assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value}
async function click(selector){const p=await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('MISSING '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1},sid);await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1},sid)}
async function key(key,extra={}){await call('Input.dispatchKeyEvent',{type:'keyDown',key,...extra},sid);await call('Input.dispatchKeyEvent',{type:'keyUp',key,...extra},sid)}
async function choose(selector,value){await ev(`document.querySelector(${JSON.stringify(selector)}).focus()`);await key('Home');const values=await ev(`[...document.querySelector(${JSON.stringify(selector)}).options].map(o=>o.value)`);for(let i=0;i<values.indexOf(value);i++)await key('ArrowDown');await key('Enter');assert.equal(await ev(`document.querySelector(${JSON.stringify(selector)}).value`),value)}
async function text(selector,value){await click(selector);await call('Input.insertText',{text:value},sid)}
async function check(id,condition,detail={}){const value=typeof condition==='string'?await ev(condition):condition;const pass=!!value;const ui=sid?await ev(`({feedback:document.querySelector('#live')?.textContent,events:document.querySelector('#events')?.innerText,focused:document.activeElement?.id})`):null;records.push({id,status:pass?'PASS':'FAIL',observed:value,detail,ui});await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2)+'\n');if(!pass)throw Error('ASSERTION_FAILED_'+id)}
async function scenario(name){await click(`[data-scenario="${name}"]`)}
async function complete(){await click('#open-evidence');await click('#return-issue');for(const id of ['fact','impact','action','verification','scope','preview','boundary'])await click('#check-'+id)}
async function screenshot(name,full=false){await ev('window.scrollTo(0,0)');const height=full?await ev('document.documentElement.scrollHeight'):await ev('innerHeight');const width=await ev('innerWidth');const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:full,...(full?{clip:{x:0,y:0,width,height,scale:1}}:{})},sid);const b=Buffer.from(r.data,'base64');await writeFile(path.join(out,name),b);shots.push({file:name,sha256:sha(b),width,height})}
try{
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('LOCAL_CHROMIUM_START_TIMEOUT')),20000);proc.once('error',e=>{clearTimeout(timer);reject(e)});proc.once('exit',code=>{clearTimeout(timer);reject(new Error('CHROMIUM_EARLY_EXIT_'+code))});proc.stderr.on('data',d=>{stderr+=d;const m=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result)}}if(m.method==='Network.requestWillBeSent')network.push(m.params);if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params)});
  version=await call('Browser.getVersion');
  for(const width of [1280,375,320]){
    const height=width===1280?1000:812;
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true}));
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*','ftp://*']},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<740},sid);
    await call('Page.navigate',{url:pathToFileURL(path.join(here,'index.html')).href},sid);
    for(let i=0;i<200;i++){if(await ev(`document.readyState==='complete'&&!!document.querySelector('#positive')`))break;await new Promise(r=>setTimeout(r,25))}
    await ev('document.fonts.ready');
    async function layout(name){await ev('window.scrollTo(0,0)');const m=await ev(`(()=>{const b=document.querySelector('.private-bar'),r=b.getBoundingClientRect();return{width:innerWidth,scrollWidth:document.documentElement.scrollWidth,lang:document.documentElement.lang,banner:{text:b.innerText,minFontPx:Math.min(...[b,...b.querySelectorAll('*')].map(n=>parseFloat(getComputedStyle(n).fontSize))),visible:getComputedStyle(b).visibility==='visible'&&getComputedStyle(b).display!=='none',top:r.top,bottom:r.bottom,height:innerHeight},targets:[...document.querySelectorAll('button,select,textarea,summary,label.check')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({id:e.id,tag:e.tagName,height:e.getBoundingClientRect().height,width:e.getBoundingClientRect().width}))}})()`);await check(`${width}-${name}-layout`,m.scrollWidth<=width&&m.banner.minFontPx>=12&&m.banner.visible&&m.banner.top>=0&&m.banner.bottom<=height&&m.banner.text.includes('非真实审核/审批/分享')&&m.banner.text.includes('NOT APPROVED')&&m.targets.every(t=>t.height>=44),m);return m}
    await layout('contact');await screenshot(`contact-${width}.png`,true);
    await check(`${width}-initial-block`,'document.querySelector("#positive").disabled && document.querySelector("#check-fact").disabled');
    await click('#open-evidence');
    await check(`${width}-original-quote`,'document.querySelector("#evidence-panel pre").textContent===window.REVIEW_FIXTURE.source.quote && document.activeElement.id==="evidence-panel"');
    await click('#raw-source summary');
    await check(`${width}-inert-attack`,'document.querySelector("#raw-source pre").textContent.includes("onerror") && typeof window.PWNED==="undefined" && document.querySelectorAll("img,iframe").length===0');
    await screenshot(`evidence-${width}.png`);
    await click('#return-issue');await check(`${width}-return-focus`,'document.activeElement.id==="open-evidence"');
    await key('Tab',{windowsVirtualKeyCode:9});await check(`${width}-keyboard-tab`,'document.activeElement.id==="check-fact"');
    await key(' ',{code:'Space',windowsVirtualKeyCode:32});await check(`${width}-keyboard-space`,'document.querySelector("#check-fact").checked');
    const focus=await ev(`({outline:getComputedStyle(document.activeElement).outlineStyle,width:getComputedStyle(document.activeElement).outlineWidth})`);await check(`${width}-visible-focus`,focus.outline!=='none'&&parseFloat(focus.width)>=3,focus);
    for(const id of ['impact','action','verification','scope','preview','boundary'])await click('#check-'+id);
    await check(`${width}-positive-enabled`,'!document.querySelector("#positive").disabled');
    await click('#positive');await check(`${width}-two-step-confirm`,'document.querySelector("#confirmation").open && !document.querySelector(".result") && document.activeElement.id==="cancel-confirm"');
    await click('#commit-simulation');await check(`${width}-positive-simulation-only`,'document.querySelector(".result").innerText.includes("模拟满足审核条件，未形成真实 APPROVE") && document.querySelector(".private-bar").innerText.includes("NOT APPROVED") && !document.querySelector("#positive")');
    await screenshot(`positive-simulation-${width}.png`,true);
    await call('Page.reload',{},sid);for(let i=0;i<100;i++){if(await ev('!!document.querySelector("#positive")'))break;await new Promise(r=>setTimeout(r,25))}
    await check(`${width}-reload-resets`,'!!document.querySelector("#positive") && document.querySelector("#positive").disabled && !document.querySelector(".result") && !document.querySelector("#check-impact").checked');
    await click('#request-changes');await check(`${width}-missing-note-blocks`,'!document.querySelector("#confirmation").open && document.querySelector("#live").innerText.includes("请填写")');
    const note='<img src="https://invalid.example/reason" onerror="window.PWNED=2"> 请保留假设措辞';
    await text('#review-note',note);await click('#request-changes');await click('#commit-simulation');await check(`${width}-changes-inert-terminal`,'document.querySelector(".result").innerText.includes("模拟已退回修改") && document.querySelector(".result").innerText.includes("onerror") && !document.querySelector("img") && !document.querySelector("#positive")');
    await screenshot(`changes-${width}.png`,true);
    await click('#reset');await text('#review-note','不适合本轮商务沟通，需补充上下文。');await click('#reject');await click('#commit-simulation');await check(`${width}-reject-terminal`,'document.querySelector(".result").innerText.includes("模拟已拒绝") && !document.querySelector("#positive")');
    await scenario('coverage');await layout('coverage');await check(`${width}-zero-no-approval`,'!document.querySelector("#positive") && !document.querySelector("#request-changes") && document.querySelector("#review").innerText.includes("native ReportVersion = null") && document.querySelector("#ack-coverage").disabled');
    await click('#open-evidence');await check(`${width}-coverage-response-200`,'document.querySelector("#evidence-panel").innerText.includes("联系目标 200") && document.querySelector("#evidence-panel").innerText.includes(window.REVIEW_FIXTURE.scenarios.coverage.source.bindingRef)');await click('#return-issue');for(const k of ['scope','preview','boundary'])await click('#check-'+k);await click('#ack-coverage');await check(`${width}-coverage-confirm-id`,'document.querySelector("#confirm-body").innerText.includes(window.REVIEW_FIXTURE.scenarios.coverage.reportId)');await click('#commit-simulation');await check(`${width}-coverage-internal-only`,'document.querySelector(".result").innerText.includes("模拟范围已核对") && !document.querySelector("#positive") && document.querySelector("#review").innerText.includes("native ReportVersion = null")');await screenshot(`coverage-${width}.png`,true);
    await scenario('stale');await complete();await click('#positive');await click('#commit-simulation');await choose('#mutation-type','footer');await click('#mutate');await check(`${width}-old-positive-invalidated`,'document.querySelector("#inspector").innerText.includes("历史模拟结果") && document.querySelector("#inspector").innerText.includes("当前失效") && !document.querySelector(".result") && !document.querySelector("#positive")');await layout('stale');await screenshot(`stale-${width}.png`,true);
    await click('#open-new-version');await check(`${width}-new-version-empty`,'document.querySelector("#context").innerText.includes("v2") && document.querySelector("#positive").disabled && !document.querySelector("#check-impact").checked && document.querySelector("#check-fact").disabled');
    for(const change of ['version','html','citation','summary','layout','source','tenant']){await scenario('stale');await complete();await choose('#mutation-type',change);await click('#mutate');await check(`${width}-change-${change}-blocked`,'!document.querySelector("#positive") && !document.querySelector(".result") && !document.querySelector("#check-fact:checked")');if(['html','citation','source','tenant'].includes(change))await check(`${width}-changed-${change}-no-self-repin`,'!document.querySelector("#open-new-version")')}
    await scenario('stale');await complete();await choose('#mutation-type','version');await click('#positive');await ev('document.querySelector("#mutate").click()');await click('#commit-simulation');await check(`${width}-confirmation-stale-block`,'!document.querySelector("#confirmation").open && !document.querySelector(".result") && document.querySelector("#live").innerText.includes("阻断")',{method:'Simulated background version event via existing mutation button while modal open'});
    await scenario('stale');await complete();await click('#missing-evidence');await check(`${width}-missing-source-block`,'document.querySelector("#positive").disabled && document.querySelector("#check-fact").disabled && document.querySelector("#evidence-panel").innerText.includes("证据缺失")');
    await scenario('denied');await layout('denied');
    for(const mode of ['foreign','unassigned','guard']){if(mode!=='foreign')await choose('#denial-type',mode);await check(`${width}-denied-${mode}-no-disclosure`,'!document.querySelector("#positive") && !document.querySelector("#open-evidence") && !document.querySelector("#context").textContent && !document.querySelector("#review").innerText.includes(window.REVIEW_FIXTURE.source.quote) && !document.querySelector("#review").innerText.includes(window.REVIEW_FIXTURE.reportId) && !document.querySelector("#inspector").innerText.includes(window.REVIEW_FIXTURE.source.sourceSha256)');if(mode==='foreign')await screenshot(`denied-${width}.png`,true)}
    await check(`${width}-no-share-send-export`,'![...document.querySelectorAll("button,a")].some(e=>/分享|导出|发送/.test(e.textContent)) && document.querySelector("footer").innerText.includes("NOT IMPLEMENTED")');
    const logs=await ev('document.querySelector("#events").innerText');await writeFile(path.join(out,`final-dom-${width}.html`),await ev('document.documentElement.outerHTML'));await writeFile(path.join(out,`last-scenario-events-${width}.txt`),logs);
    await call('Target.closeTarget',{targetId});sid=null;
  }
  await check('no-external-page-requests',network.filter(n=>!n.request.url.startsWith('file:')&&!n.request.url.startsWith('about:')).length===0);
  await check('no-runtime-exceptions',exceptions.length===0);
  const js=await readFile(path.join(here,'workbench.js'),'utf8');await check('no-persistence-or-network-code',!/(localStorage|sessionStorage|indexedDB|document\.cookie|fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|serviceWorker)/.test(js));
}catch(e){infrastructureError={message:e.message,stack:e.stack};records.push({id:'execution-error',status:'ERROR',error:infrastructureError});console.error(e.stack);process.exitCode=1}
finally{
  const inputFiles={};for(const f of ['index.html','workbench.css','workbench.js','fixtures.js','fixtures.json','browser-test.mjs']){const b=await readFile(path.join(here,f));inputFiles[f]={sha256:sha(b),bytes:b.length}}
  const result={status:infrastructureError?'NOT_PASS':'OFFLINE_INTERACTION_PASS',scope:'SYNTHETIC_UI_ONLY_NOT_PRODUCTION_RA3D',runId,browser:version,chromiumExecutable:chrome,chromiumArgs:args.map(a=>a.includes(profile)?a.replaceAll(profile,'<run-profile>'):a),inputs:inputFiles,counts:Object.fromEntries(['PASS','FAIL','ERROR','SKIP'].map(s=>[s,records.filter(r=>r.status===s).length])),assertions:records,screenshots:shots,observedExternalPageRequests:network.filter(n=>!n.request.url.startsWith('file:')&&!n.request.url.startsWith('about:')),runtimeExceptions:exceptions,infrastructureError};
  await writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2)+'\n');await writeFile(path.join(out,'network-events.json'),JSON.stringify(network,null,2)+'\n');await writeFile(path.join(out,'cdp-command-log.json'),JSON.stringify(commands,null,2)+'\n');await writeFile(path.join(out,'chromium-stderr.txt'),stderr);
  console.log(JSON.stringify({out,status:result.status,counts:result.counts,screenshots:shots.length}));
  if(ws?.readyState===1){await call('Browser.close').catch(()=>{});ws.close()}if(proc.exitCode===null)proc.kill();
}
