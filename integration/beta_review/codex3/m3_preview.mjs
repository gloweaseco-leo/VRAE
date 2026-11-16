// Authorized local M1 bytes only. This is a diagnostic view, never M2 approval.
import {spawn} from 'node:child_process';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const [input,expected,out]=process.argv.slice(2);
const interactive=process.argv.includes('--interactive');
const raw=await readFile(input);
assert(createHash('sha256').update(raw).digest('hex')===expected,'M3_HTML_SHA_MISMATCH');
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(path.resolve(out),'chrome-'));
let ws,sid,serial=0;
const pending=new Map();
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
 ...(!interactive?['--headless=new']:[]),'--disable-gpu','--no-first-run','--no-default-browser-check',
 '--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions',
 '--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1',
 '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1',
 '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank',
],{windowsHide:true,stdio:['ignore','ignore','pipe']});
function call(method,params={},sessionId=sid){
 return new Promise((resolve,reject)=>{
  const id=++serial;
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},30000);
  pending.set(id,{resolve,reject,timer});
  ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
 });
}
async function ev(expression){
 const result=await call('Runtime.evaluate',{expression,returnByValue:true});
 assert(!result.exceptionDetails,'M3_BROWSER_EVALUATION');
 return result.result.value;
}
try{
 let stderr='';
 const endpoint=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('CHROME_START_DEADLINE')),30000);
  chrome.on('error',()=>reject(Error('CHROME_START_FAILED')));
  chrome.stderr.on('data',d=>{
   stderr+=d.toString();const match=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);
   if(match){clearTimeout(timer);resolve(match[0])}
  });
 });
 ws=new WebSocket(endpoint);
 await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
 ws.addEventListener('message',event=>{
  const m=JSON.parse(event.data);
  if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}}
 });
 const target=await call('Target.createTarget',{url:'about:blank'},null);
 sid=(await call('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
 await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*']});
 await call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 const url=pathToFileURL(path.resolve(input)).href;
 await call('Page.navigate',{url});
 let ready=false;
 for(let i=0;i<600;i++){
  if(await ev('document.readyState==="complete"&&location.href==='+JSON.stringify(url))){ready=true;break}
  await new Promise(r=>setTimeout(r,50));
 }
 assert(ready,'M3_GENERATED_DOCUMENT_NOT_READY');
 const facts=await ev('({text:document.body.innerText,scripts:document.scripts.length,height:document.documentElement.scrollHeight})');
 assert(facts.scripts===0&&facts.text.includes('PRIVATE')&&(facts.text.includes('NOT APPROVED')||facts.text.includes('NOT_APPROVED')),'M3_PRIVATE_UNAPPROVED_REPORT_REQUIRED');
 const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1280,height:facts.height,scale:1}});
 const png=Buffer.from(shot.data,'base64');
 await writeFile(path.join(out,'generated-report.png'),png);
 const result={scope:'AUTHORIZED_M1_DIAGNOSTIC_NOT_M2',pass:true,html_sha256:expected,
   screenshot_sha256:createHash('sha256').update(png).digest('hex'),external_network_blocked:true,scripts:0};
 await writeFile(path.join(out,'browser.json'),JSON.stringify(result));
 process.stdout.write(JSON.stringify(result)+'\n');
 if(interactive)await new Promise(resolve=>chrome.once('exit',resolve));
}finally{
 try{if(ws?.readyState===WebSocket.OPEN)await call('Browser.close',{},null)}catch{}
 ws?.close();
 if(chrome.exitCode===null&&chrome.signalCode===null)chrome.kill();
 await new Promise(resolve=>{
  if(chrome.exitCode!==null||chrome.signalCode!==null){resolve();return}
  const timer=setTimeout(resolve,3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()});
 });
 await writeFile(path.join(out,'cleanup.json'),JSON.stringify({exit_observed:chrome.exitCode!==null||chrome.signalCode!==null}));
 for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}
 pending.clear();
}
