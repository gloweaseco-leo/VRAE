// Generated from pinned Phase0.5 harness + browser-cases.txt.
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
for(const f of ['index.html','bridge.css','bridge-fixture.js','bridge-view.js','dossier-data.js','browser-test.mjs'])await writeFile(path.join(out,'input-files',f),await readFile(path.join(here,f)));
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
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);
    await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*','ftp://*']},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<740},sid);
    await call('Page.navigate',{url:pathToFileURL(path.join(here,'index.html')).href},sid);
    for(let i=0;i<200;i++){if(await ev(`document.readyState==='complete'&&!!document.querySelector('#native-dossier .native-claim')`))break;await new Promise(r=>setTimeout(r,25))}
    await ev('document.fonts.ready');
    for(const c of ['404','200']){
      if(c==='200')await scenario('coverage');
      await ev('window.scrollTo(0,0)');
      const metrics=await ev(`(()=>{const e=document.querySelector('.private-bar'),r=e.getBoundingClientRect();return{width:innerWidth,scrollWidth:document.documentElement.scrollWidth,lang:document.documentElement.lang,banner:{text:e.innerText,minFont:Math.min(...[e,...e.querySelectorAll('*')].map(n=>parseFloat(getComputedStyle(n).fontSize))),top:r.top,bottom:r.bottom},context:document.querySelector('#context').innerText}})()`);
      await check(`${width}-${c}-layout`,metrics.scrollWidth<=width&&metrics.banner.minFont>=12&&metrics.banner.top>=0&&metrics.banner.bottom<=height&&metrics.banner.text.includes('真实 RA3C 合成证据重放')&&metrics.banner.text.includes('NOT APPROVED'),metrics);
      await check(`${width}-${c}-native-context`,`document.querySelector('#context').innerText.includes(window.NATIVE_DOSSIERS['${c}'].native_document.metadata.report_id)&&document.querySelector('#context').innerText.includes('2026-11-10T12:00:00+00:00')&&!document.querySelector('#context').innerText.includes('sim-')`);
      await screenshot(`native-${c}-${width}.png`,true);
      if(c==='404'){
        await check(`${width}-404-fact-and-proposals`,`(()=>{const d=window.NATIVE_DOSSIERS['404'].native_document,i=d.issues[0],t=document.querySelector('#review').innerText;return [i.fact_claim,...Object.values(i.proposals)].every(c=>t.includes(c.text))&&i.finding.buyer_task==='INQUIRE'&&i.fact_claim.status==='SOURCE_FACT_BINDING_VERIFIED'&&Object.values(i.proposals).every(c=>c.status==='HUMAN_REVIEW_REQUIRED')})()`);
        await check(`${width}-initial-positive-disabled`,'document.querySelector("#positive").disabled');
      }else await check(`${width}-zero-not-report`,`!document.querySelector('#positive')&&window.NATIVE_DOSSIERS['200'].native_document.native_report_version===null&&document.querySelector('#review').innerText.includes('native ReportVersion = null')`);
      await click('#open-evidence');
      await check(`${width}-${c}-main-source-click`,`(()=>{const x=window.NATIVE_DOSSIERS['${c}'],s=x.source;return document.querySelector('#evidence-panel > pre').textContent===s.quote&&document.querySelector('#evidence-panel').innerText.includes(s.citation.evidence_ref)&&document.querySelector('#evidence-panel').innerText.includes(s.capturedAt)&&document.activeElement.id==='evidence-panel'})()`);
      if(c==='200')await check(`${width}-200-no-fabricated-guard`,'document.querySelector("#evidence-panel").innerText.includes("没有 RA3B CTA binding / Guard claim")');
      await click('#raw-source summary');
      await check(`${width}-${c}-actual-body-bytes`,`(()=>{const s=window.NATIVE_DOSSIERS['${c}'].source,b=Uint8Array.from(atob(s.bodyBase64),x=>x.charCodeAt(0));return new TextDecoder().decode(b.slice(...s.byteRange))===s.quote&&document.querySelector('#raw-source pre').textContent===new TextDecoder().decode(b)})()`);
      // Full screenshot includes actual quote and original source, not just a top-of-page notice.
      await screenshot(`native-evidence-${c}-${width}.png`,true);
      await click('#return-issue');await check(`${width}-${c}-return-focus`,'document.activeElement.id==="open-evidence"');
      if(c==='404'){await key('Tab',{windowsVirtualKeyCode:9});await key(' ',{code:'Space',windowsVirtualKeyCode:32});await check(`${width}-keyboard-fact`,'document.querySelector("#check-fact").checked');for(const id of ['impact','action','verification','scope','preview','boundary'])await click('#check-'+id)}
      else for(const id of ['scope','preview','boundary'])await click('#check-'+id);
      await check(`${width}-${c}-additional-native-claims-required`,c==='404'?'document.querySelector("#positive").disabled':'document.querySelector("#ack-coverage").disabled');
      const claimCount=await ev(`window.NATIVE_DOSSIERS['${c}'].shownClaims.length`);
      for(let index=0;index<claimCount;index++){
        await click(`.claim-source[data-index="${index}"]`);
        await check(`${width}-${c}-claim-${index}-exact-native-source`,`(()=>{const item=window.NATIVE_DOSSIERS['${c}'].shownClaims[${index}],box=document.querySelector('#native-source-content');return document.querySelector('#native-source-dialog').open&&box.querySelector('pre').textContent===item.source.quote&&box.innerText.includes(item.claim.text)&&box.innerText.includes(item.claim.status)&&box.innerText.includes(item.claim.binding_ref)&&box.innerText.includes(item.source.citation.url)})()`);
        await check(`${width}-${c}-claim-${index}-visible-private-dialog`,`(()=>{const e=document.querySelector('.native-dialog-label'),r=e.getBoundingClientRect(),d=document.querySelector('#native-source-dialog');return document.activeElement.id==='source-title'&&d.scrollTop===0&&parseFloat(getComputedStyle(e).fontSize)>=12&&r.top>=0&&r.bottom<=innerHeight&&d.scrollWidth<=d.clientWidth&&e.innerText.includes('NOT APPROVED')})()`);
        if(index===0){const img=await call('Page.captureScreenshot',{format:'png'},sid);const b=Buffer.from(img.data,'base64'),file=`native-claim-dialog-${c}-${width}.png`;await writeFile(path.join(out,file),b);shots.push({file,sha256:sha(b),width,height})}
        await click('#close-native-source');await check(`${width}-${c}-claim-${index}-return`,'document.activeElement.classList.contains("claim-source")&&!document.querySelector("#native-source-dialog").open');
        await click(`.native-claim:nth-of-type(${index+1}) .native-ack`);
      }
      await click('#native-hashes summary');await check(`${width}-${c}-full-native-hashes`,`(()=>{const d=window.NATIVE_DOSSIERS['${c}'].native_document,t=document.querySelector('#native-hashes').innerText;return [d.html_sha256,d.editorial_content_sha256,d.renderer_asset_sha256,d.draft_ref,...d.pins.expected_guard_refs].every(x=>t.includes(x))})()`);
      await click('#native-preview summary');
      for(let i=0;i<100;i++){if(await ev(`!!document.querySelector('#native-preview iframe')`))break;await new Promise(r=>setTimeout(r,20))}
      await check(`${width}-${c}-exact-preview-file`,`document.querySelector('#native-preview iframe').getAttribute('src')===window.NATIVE_DOSSIERS['${c}'].native_html_path && document.querySelector('#native-preview iframe').getAttribute('sandbox')===''`);
      // Sandboxed file iframe may be a separate Chromium renderer target (OOPIF).
      // Prove the loaded URL AND actual private DOM, not just src/request or frame-tree membership.
      let preview,previewProof;
      for(let i=0;i<100;i++){
        const targets=await call('Target.getTargets');preview=targets.targetInfos.find(t=>t.type==='iframe'&&t.url.endsWith(`/dossiers/contact-${c}.html`));
        if(preview){const {sessionId:childSid}=await call('Target.attachToTarget',{targetId:preview.targetId,flatten:true});
          const r=await call('Runtime.evaluate',{expression:'({url:location.href,ready:document.readyState,text:document.body?.innerText,scripts:document.scripts.length,forms:document.forms.length})',returnByValue:true},childSid);previewProof=r.result.value;
          await call('Target.detachFromTarget',{sessionId:childSid});if(previewProof?.ready==='complete')break;}
        await new Promise(r=>setTimeout(r,25));
      }
      await check(`${width}-${c}-native-preview-actually-loaded`,previewProof?.url.endsWith(`/dossiers/contact-${c}.html`)&&previewProof?.text.includes('NOT APPROVED')&&previewProof?.scripts===0&&previewProof?.forms===0,previewProof);
      const before=await ev(`JSON.stringify(window.NATIVE_DOSSIERS['${c}'].native_document)`);
      await click(c==='404'?'#positive':'#ack-coverage');await check(`${width}-${c}-confirm-only`,'document.querySelector("#confirmation").open&&!document.querySelector(".result")');
      await click('#commit-simulation');await check(`${width}-${c}-native-immutable-and-unapproved`,await ev(`JSON.stringify(window.NATIVE_DOSSIERS['${c}'].native_document)===${JSON.stringify(before)}&&document.querySelector('.private-bar').innerText.includes('NOT APPROVED')&&document.querySelector('.result').innerText.includes(${JSON.stringify(c==='404'?'未形成真实 APPROVE':'仅内部')})`));
      await screenshot(`native-result-${c}-${width}.png`,true);
      const rows=await ev('document.querySelector("#events").innerText');await writeFile(path.join(out,`interaction-${c}-${width}.txt`),rows);
    }
    await check(`${width}-no-send-share-export`,'![...document.querySelectorAll("button,a")].some(e=>/分享|导出|发送/.test(e.textContent))');
    await call('Page.reload',{},sid);for(let i=0;i<200;i++){if(await ev('!!document.querySelector("#positive")'))break;await new Promise(r=>setTimeout(r,25))}
    await check(`${width}-reload-memory-only`,'!document.querySelector(".result")&&document.querySelector("#positive").disabled');
    await call('Target.closeTarget',{targetId});sid=null;
  }
  await check('zero-external-page-requests',network.filter(n=>!n.request.url.startsWith('file:')&&!n.request.url.startsWith('about:')).length===0);
  await check('zero-runtime-exceptions',exceptions.length===0);
}catch(e){infrastructureError={message:e.message,stack:e.stack};records.push({id:'execution-error',status:'ERROR',error:infrastructureError});console.error(e.stack);process.exitCode=1}
finally{
  const inputFiles={};for(const f of ['index.html','bridge.css','bridge-fixture.js','bridge-view.js','dossier-data.js','browser-test.mjs']){const b=await readFile(path.join(here,f));inputFiles[f]={sha256:sha(b),bytes:b.length}}
  const result={status:infrastructureError?'NOT_PASS':'OFFLINE_INTERACTION_PASS',scope:'NATIVE_READONLY_SYNTHETIC_UI_NOT_PRODUCTION',runId,browser:version,chromiumExecutable:chrome,chromiumArgs:args.map(a=>a.includes(profile)?a.replaceAll(profile,'<run-profile>'):a),inputs:inputFiles,counts:Object.fromEntries(['PASS','FAIL','ERROR','SKIP'].map(s=>[s,records.filter(r=>r.status===s).length])),assertions:records,screenshots:shots,observedExternalPageRequests:network.filter(n=>!n.request.url.startsWith('file:')&&!n.request.url.startsWith('about:')),runtimeExceptions:exceptions,infrastructureError};
  await writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2)+'\n');await writeFile(path.join(out,'network-events.json'),JSON.stringify(network,null,2)+'\n');await writeFile(path.join(out,'cdp-command-log.json'),JSON.stringify(commands,null,2)+'\n');await writeFile(path.join(out,'chromium-stderr.txt'),stderr);
  console.log(JSON.stringify({out,status:result.status,counts:result.counts,screenshots:shots.length}));
  if(ws?.readyState===1){await call('Browser.close').catch(()=>{});ws.close()}if(proc.exitCode===null)proc.kill();
}
