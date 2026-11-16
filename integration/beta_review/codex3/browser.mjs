// Real sandboxed Chromium. Private cookie input comes from actual signed HTTP login.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import assert from 'node:assert/strict';

const [input,out]=process.argv.slice(2);
const interactive=process.argv[4]==='--interactive';
const sessions=JSON.parse(await readFile(input,'utf8'));
await mkdir(out,{recursive:true});
const pending=new Map(); let serial=0, ws, sessionId;
const shots=[], measurements=[], blocked=[];
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
  ...(!interactive?['--headless=new']:[]),'--disable-gpu','--no-first-run','--no-default-browser-check',
  '--disable-background-networking','--disable-component-update','--disable-sync',
  '--disable-default-apps','--disable-extensions','--disable-domain-reliability',
  '--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter',
  '--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1',
  '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1',
  '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
  '--user-data-dir='+path.join(path.resolve(out),'chrome-profile'),'about:blank'],
  {windowsHide:true,stdio:['ignore','ignore','pipe']});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function call(method,params={},sid=sessionId){
  return new Promise((resolve,reject)=>{
    const id=++serial;
    const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_DEADLINE'))},20000);
    pending.set(id,{resolve,reject,timer});
    ws.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}));
  });
}
async function ev(expression){
 const v=await call('Runtime.evaluate',{expression,returnByValue:true});
 assert(!v.exceptionDetails,'BROWSER_EVALUATION');
 return v.result.value;
}
try{
 const endpoint=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('CHROME_START_DEADLINE')),30000);
   chrome.on('error',()=>reject(Error('CHROME_START_FAILED')));
   chrome.stderr.on('data',d=>{
     const m=d.toString().match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);
     if(m){clearTimeout(timer);resolve(m[0])}
   });
 });
 ws=new WebSocket(endpoint);
 await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
 ws.addEventListener('message',event=>{
   const m=JSON.parse(event.data);
   if(m.id){
     const p=pending.get(m.id);
     if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}
   }
   if(m.method==='Fetch.requestPaused'){
     const u=new URL(m.params.request.url);
     const allowed=sessions.some(s=>u.origin===s.origin);
     if(!allowed)blocked.push(u.protocol);
     void call(allowed?'Fetch.continueRequest':'Fetch.failRequest',
       {requestId:m.params.requestId,...(!allowed?{errorReason:'BlockedByClient'}:{})},m.sessionId)
       .catch(()=>{});
   }
 });
 const {targetId}=await call('Target.createTarget',{url:'about:blank'},null);
 ({sessionId}=await call('Target.attachToTarget',{targetId,flatten:true},null));
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
 await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
 for(const s of sessions){
   await call('Network.clearBrowserCookies');
   await call('Network.setCookies',{cookies:Object.entries(s.cookies).map(([name,value])=>({
     name,value,url:s.origin+'/b5a/',path:'/b5a/',httpOnly:true,sameSite:'Strict',secure:false}))});
   for(const width of [1280,375,320]){
     await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
     const url=s.origin+s.path;
     await call('Page.navigate',{url});
     let loaded=false;
     for(let n=0;n<300;n++){
       if(await ev('document.readyState==="complete" && location.href==='+JSON.stringify(url))){loaded=true;break}
       await delay(50);
     }
     assert(loaded,'ACTUAL_SSR_LOAD_DEADLINE');
     const v=await ev(`({width:innerWidth,scroll:document.documentElement.scrollWidth,
       scripts:document.scripts.length,text:document.body.innerText,
       height:document.documentElement.scrollHeight})`);
     const visible=s.entry_kind==='B5P0_SEALED_INTERNAL_INTENT'
       ? await ev("!!document.querySelector('#proposal-form')&&!!document.querySelector('#save-rehearsal')")
       : v.text.includes('Reviewer');
     assert(visible && (v.text.includes('NOT_APPROVED')||v.text.includes('NOT APPROVED')),'SIGNED_PG_ORIGINAL_NOT_DISPLAYED');
     assert(v.scripts===0 && v.scroll<=v.width,'SSR_LAYOUT_OR_SCRIPT_RED');
     const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
       clip:{x:0,y:0,width,height:v.height,scale:1}});
     const raw=Buffer.from(shot.data,'base64'), file=s.case+'-'+width+'.png';
     await writeFile(path.join(out,file),raw);
     shots.push({file,sha256:createHash('sha256').update(raw).digest('hex')});
     measurements.push({case:s.case,width,scroll:v.scroll,scripts:v.scripts,
       signed_original_visible:true});
   }
 }
 await writeFile(path.join(out,'metrics.json'),JSON.stringify(measurements,null,2));
 const result={status:'PASS',widths:[1280,375,320],cases:sessions.length,screenshots:shots,
    remote_requests_blocked:blocked.length,sandbox_disabled:false,scope:sessions.every(s=>s.entry_kind==='B5P0_SEALED_INTERNAL_INTENT')?'SIGNED_SEALED_INTERNAL_INTENT_NOT_WORKER_OUTPUT':'SIGNED_READ_ONLY_NOT_APPROVAL'};
 process.stdout.write(JSON.stringify(result));
 if(interactive){await call('Emulation.clearDeviceMetricsOverride');await new Promise(resolve=>chrome.once('exit',resolve))}
}finally{
 if(ws?.readyState===WebSocket.OPEN){try{await call('Browser.close',{},null)}catch{}ws.close()}
 chrome.kill();
 for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}
}
