// Supplemental observation only. Never consumed as frozen-test PASS metadata.
// CDP method reference: https://chromedevtools.github.io/devtools-protocol/
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(here,'ui-supplement');
const source=JSON.parse(fs.readFileSync(path.join(out,'source.json'),'utf8'));
if(fs.existsSync(path.join(out,'browser-observations.json')))throw Error('Preserve existing observations');
const chrome='C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'vrae-ra3c-independent-'));
const args=['--headless=new','--remote-debugging-pipe','--no-first-run','--no-default-browser-check',
  '--disable-background-networking','--disable-component-update','--disable-domain-reliability',
  '--disable-default-apps','--disable-sync','--metrics-recording-only','--no-proxy-server',
  '--host-resolver-rules=MAP * ~NOTFOUND','--safebrowsing-disable-auto-update',
  '--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication,Translate',
  '--user-data-dir='+profile,'about:blank'];
const child=spawn(chrome,args,{stdio:['ignore','pipe','pipe','pipe','pipe'],windowsHide:true});
let stderr='',buffer=Buffer.alloc(0),serial=0;
const pending=new Map(),requests=[],exceptions=[];
let activeUrl='',closing=false;
child.stderr.on('data',b=>{stderr=(stderr+b.toString()).slice(-1000000);});
function call(method,params={},sessionId){
  return new Promise((resolve,reject)=>{
    const id=++serial;
    const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT:'+method));},15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
}
child.on('error',error=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(error);}pending.clear();});
child.on('exit',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error(closing?'BROWSER_CLOSED':'BROWSER_EXIT'));}pending.clear();});
child.stdio[4].on('data',chunk=>{
  buffer=Buffer.concat([buffer,chunk]);
  while(buffer.includes(0)){
    const end=buffer.indexOf(0),raw=buffer.subarray(0,end).toString();
    buffer=buffer.subarray(end+1);
    if(!raw)continue;
    const message=JSON.parse(raw);
    if(message.id){
      const p=pending.get(message.id);if(!p)continue;
      pending.delete(message.id);clearTimeout(p.timer);
      if(message.error)p.reject(Error(JSON.stringify(message.error)));else p.resolve(message.result||{});
    }else if(message.method==='Fetch.requestPaused'){
      const url=message.params.request.url;
      const allowed=url===activeUrl||url===activeUrl+'#report';
      requests.push({url,allowed,session:message.sessionId});
      call(allowed?'Fetch.continueRequest':'Fetch.failRequest',
        {requestId:message.params.requestId,...(allowed?{}:{errorReason:'BlockedByClient'})},message.sessionId)
        .catch(e=>exceptions.push('INTERCEPTION:'+e.message));
    }else if(message.method==='Network.requestWillBeSent'){
      if(!message.params.request.url.startsWith('file:')&&!message.params.request.url.startsWith('about:'))
        exceptions.push('NON_LOCAL_REQUEST:'+message.params.request.url);
    }else if(message.method==='Runtime.exceptionThrown')exceptions.push(JSON.stringify(message.params.exceptionDetails));
  }
});
async function evaluate(session,expression){
  const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},session);
  if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function ready(session){
  for(let i=0;i<80;i++){
    if(await evaluate(session,'document.readyState === "complete"')){
      await evaluate(session,'document.fonts.ready.then(()=>true)');return;
    }
    await new Promise(r=>setTimeout(r,50));
  }
  throw Error('DOCUMENT_NOT_READY');
}
async function screenshot(session,filename){
  const metrics=await call('Page.getLayoutMetrics',{},session);
  const size=metrics.cssContentSize||metrics.contentSize;
  const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
    clip:{x:0,y:0,width:size.width,height:size.height,scale:1}},session);
  const raw=Buffer.from(shot.data,'base64');fs.writeFileSync(path.join(out,filename),raw);
  return {file:filename,sha256:sha(raw)};
}
const record={...source,capture_tool:'Codex1 CDP pipe; cached Chromium; fresh hidden headless process',
  started_at:new Date().toISOString(),not_customer_approval:true,views:[],
  caveat:'Candidate-produced artifact independently rendered; not own frozen-input output or 64-case visual PASS.'};
try{
  record.browser=await call('Browser.getVersion');
  for(const name of Object.keys(source.artifacts)){
    const htmlPath=path.join(out,name+'.html');
    if(sha(fs.readFileSync(htmlPath))!==source.artifacts[name].html_sha256)throw Error('HTML_HASH_MISMATCH');
    const document=JSON.parse(fs.readFileSync(path.join(out,name+'.draft.json'),'utf8'));
    for(const width of [375,1280]){
      const {targetId}=await call('Target.createTarget',{url:'about:blank'});
      const {sessionId}=await call('Target.attachToTarget',{targetId,flatten:true});
      for(const method of ['Page.enable','Runtime.enable','Network.enable'])await call(method,{},sessionId);
      await call('Network.setBypassServiceWorker',{bypass:true},sessionId);
      await call('Network.setCacheDisabled',{cacheDisabled:true},sessionId);
      await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*','ftp://*']},sessionId);
      await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]},sessionId);
      await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
      activeUrl=pathToFileURL(htmlPath).href;
      await call('Page.navigate',{url:activeUrl},sessionId);await ready(sessionId);
      const observations=await evaluate(sessionId,`(()=>{
        const privacy=document.querySelector('.private-bar'),r=privacy.getBoundingClientRect();
        return {width:innerWidth,scroll_width:document.documentElement.scrollWidth,client_width:document.documentElement.clientWidth,
          body_font_px:parseFloat(getComputedStyle(document.body).fontSize),main_heading_count:document.querySelectorAll('main h1').length,
          visible_layer_labels:document.querySelectorAll('.issue .fact .label,.issue .proposal .label').length,
          privacy_above_fold:r.top>=0&&r.bottom<=innerHeight,privacy_font_px:parseFloat(getComputedStyle(privacy).fontSize),
          heading:document.querySelector('h1').innerText,private_text:privacy.innerText,main_text:document.querySelector('main').innerText,
          links:[...document.querySelectorAll('main a.cite')].map(a=>a.getAttribute('href'))};})()`);
      const shot=await screenshot(sessionId,name+'-'+width+'.png');
      const clicks=[];
      for(const href of [...new Set(observations.links)]){
        if(!href.startsWith('#'))throw Error('NON_INTERNAL_CITATION');
        await call('Page.navigate',{url:activeUrl+'#report'},sessionId);await ready(sessionId);
        const xy=await evaluate(sessionId,`(()=>{const a=[...document.querySelectorAll('main a.cite')].find(a=>a.getAttribute('href')===${JSON.stringify(href)});a.scrollIntoView({block:'center'});const r=a.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
        await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...xy},sessionId);
        await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...xy},sessionId);
        const actual=await evaluate(sessionId,`(()=>{const n=document.querySelector(${JSON.stringify(href)});return {hash:location.hash,visible:!!n&&getComputedStyle(n).display!=='none',quote:n?.querySelector('pre')?.textContent};})()`);
        const nativeClaims=[...document.issues.flatMap(i=>[i.fact_claim,...Object.values(i.proposals)]),...document.positive_source_claims];
        const claim=nativeClaims.find(c=>'#ev-'+c.binding_ref.slice(3)===href);
        clicks.push({href,actual_hash:actual.hash,resolved:actual.visible&&actual.hash===href,
          quote_matches_companion_document:!!claim&&actual.quote===claim.fact.source.quote});
        if(!clicks.at(-1).resolved||!clicks.at(-1).quote_matches_companion_document)throw Error('CITATION_CLICK_MISMATCH');
        if(clicks.length===1)await screenshot(sessionId,name+'-'+width+'-first-evidence.png');
      }
      const sessionRequests=requests.filter(r=>r.session===sessionId);
      record.views.push({name,width,html_sha256:source.artifacts[name].html_sha256,...observations,
        screenshot:shot,citation_clicks:clicks,requests:sessionRequests,
        external_requests:sessionRequests.filter(r=>!r.url.startsWith('file:'))});
      await call('Target.closeTarget',{targetId});
    }
  }
  record.exceptions=exceptions;
  if(exceptions.length||requests.some(r=>!r.allowed))throw Error('UNEXPECTED_BROWSER_REQUEST_OR_EXCEPTION');
  record.finished_at=new Date().toISOString();record.status='OBSERVATIONS_CAPTURED_NOT_ACCEPTANCE';
}catch(error){record.status='CAPTURE_ERROR_NOT_VISUAL_PASS';record.error=error.stack;throw error;}
finally{
  fs.writeFileSync(path.join(out,'browser-observations.json'),JSON.stringify(record,null,2)+'\n');
  closing=true;try{await call('Browser.close');}catch{}child.kill();
  fs.writeFileSync(path.join(out,'chromium-stderr.log'),stderr);
}
console.log(JSON.stringify({status:record.status,views:record.views.length,
  actual_citation_clicks:record.views.reduce((n,v)=>n+v.citation_clicks.length,0),frozen_visual_pass:false}));
