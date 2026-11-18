// Original signed SSR in real Chrome; no keys, customer network or RFQ sends.
import {spawn} from 'node:child_process';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const lines=createInterface({input:process.stdin}),iterator=lines[Symbol.asyncIterator]();
const config=JSON.parse((await iterator.next()).value),origin=config.origin,root=origin+'/b5a/l2/r/'+config.reportId;
const profile=await mkdtemp(path.join(tmpdir(),'l2-executive-'));
const checks=[],shots=[],pending=new Map();let chrome,ws,sid,serial=0,tail='',exitObserved=false;
const hash=b=>createHash('sha256').update(b).digest('hex');
function call(method,params={},sessionId=sid){return new Promise((resolve,reject)=>{const id=++serial;
 const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},15000);
 pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'EVALUATION_FAILED');return r.result.value;}
async function check(name,value){checks.push({name,pass:!!value});assert(value,name);}
async function wait(expression){for(let i=0;i<300;i++){if(await ev(expression))return;await new Promise(r=>setTimeout(r,30))}throw Error('PAGE_WAIT_TIMEOUT');}
async function nav(url){await call('Page.navigate',{url});await wait(`document.readyState==='complete'&&location.href===${JSON.stringify(url)}`);}
async function click(selector){const p=await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});}
async function shot(name){await ev('scrollTo(0,0)');const r=await call('Page.captureScreenshot',{format:'png'});const raw=Buffer.from(r.data,'base64');await writeFile(path.join(config.out,name),raw);shots.push({file:name,sha256:hash(raw)});}
async function receiver(state){process.stdout.write(JSON.stringify({kind:'receiver',state})+'\n');const response=JSON.parse((await iterator.next()).value);assert(response.state===state);await nav(root+'/brief');}
try{
 const executable=process.env.L2_CHROMIUM||(process.platform==='win32'?'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe':'/usr/bin/google-chrome');
 chrome=spawn(executable,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-features=MediaRouter,OptimizationHints','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
 chrome.once('exit',()=>{exitObserved=true});
 const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROME_START_TIMEOUT')),30000);chrome.once('error',reject);chrome.stderr.on('data',b=>{tail=(tail+b.toString()).slice(-4096);const m=tail.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
 ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
 ws.addEventListener('message',e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}});
 const {targetId}=await call('Target.createTarget',{url:'about:blank'},null);({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true},null));await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
 await call('Network.setCookie',{name:'b5a_l2_session',value:config.session,url:origin,path:'/b5a/l2/',httpOnly:true,sameSite:'Strict'});
 for(const width of [1280,393,375,320]){
  await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});await nav(root+'/executive');
  await check('summary-six-groups-'+width,await ev("document.querySelectorAll('[data-group]').length===6&&document.querySelectorAll('.executive-coverage li').length===5"));
  await check('zero-native-website-faults-'+width,await ev("document.querySelector('[data-key=executive-obstacles]').innerText.includes('0 项')&&document.body.innerText.includes('SERVICE_CATALOG_PENDING')"));
  await check('signed-responsive-no-script-'+width,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0&&!document.cookie.includes('b5a_l2_session')"));
  await shot('executive-'+width+'.png');
 }
 await nav(root+'/executive-document');await check('document-readable-fallback',await ev("document.body.innerText.includes('摘要 SHA256')&&document.body.innerText.includes('非正式人审')&&document.body.innerText.includes('UNKNOWN')"));
 const pdf=Buffer.from((await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true})).data,'base64');
 const pages=(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;
 await writeFile(path.join(config.out,'executive.pdf'),pdf);await check('actual-one-or-two-page-summary',pages>=1&&pages<=2);checks.push({name:'pdf-page-count',pass:true,pages,sha256:hash(pdf)});
 await nav(root+'/brief');await check('brief-preview-no-premature-intake',await ev("!document.querySelector('[data-key=vf-submit]')&&document.body.innerText.includes('先用下方原按钮保存')"));
 await click('[data-key=l2-save-brief]');await wait("document.readyState==='complete'&&!!document.querySelector('[data-key=vf-submit]')");
 await check('actual-pg-brief-and-four-books',await ev("document.querySelectorAll('[data-cost-book]').length===4&&document.body.innerText.includes('PostgreSQL 回读')&&document.body.innerText.includes('UNRECONCILED')"));await shot('vf-ready-320.png');
 await click('[data-key=vf-submit]');await wait("document.querySelector('[data-key=vf-intake-state]')?.innerText.includes('WAITING_ACK')");await check('producer-only-waits',true);
 await receiver('REJECTED');await check('receiver-returned',await ev("!!document.querySelector('[data-key=vf-retry]')"));
 await click('[data-key=vf-retry]');await wait("document.querySelector('[data-key=vf-intake-state]')?.innerText.includes('WAITING_ACK')");
 await receiver('RETRYABLE_FAILED');await click('[data-key=vf-retry]');await wait("document.querySelector('[data-key=vf-intake-state]')?.innerText.includes('WAITING_ACK')");
 await receiver('ACKNOWLEDGED');await check('independent-ack-does-not-upgrade-rights',await ev("document.querySelector('[data-key=vf-intake-state]').innerText.includes('ACKNOWLEDGED')&&document.body.innerText.includes('客户确认、E2/E3、正式人审、外发及素材授权均未成立')"));await shot('vf-ack-internal-only.png');
 await click('[data-key=vf-revoke]');await wait("document.querySelector('[data-key=vf-intake-state]')?.innerText.includes('REVOKED')");await check('revoked-no-resubmit',await ev("!document.querySelector('[data-key=vf-submit]')&&!document.querySelector('[data-key=vf-retry]')"));
 await nav(root+'/history');await check('original-attributed-review-receipt',await ev("document.body.innerText.includes('合成内部审阅员')"));await shot('original-review-receipt.png');
 await call('Network.clearBrowserCookies');await nav(root+'/executive-document');await check('unsigned-document-denied',await ev("!document.querySelector('.l2-executive')"));
}finally{
 ws?.close();if(chrome&&!exitObserved)chrome.kill('SIGTERM');for(let i=0;i<100&&chrome&&!exitObserved;i++)await new Promise(r=>setTimeout(r,20));
 if(chrome&&!exitObserved)chrome.kill('SIGKILL');for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}
 await writeFile(path.join(config.out,'browser.json'),JSON.stringify({scope:'CONTROLLED_C1_C2_SSR_REAL_PG_DETACHED_TASK_NOT_APP202_E2E',checks,shots,chromeExitObserved:exitObserved,formalHumanReview:false,externalDelivery:false},null,2));
 await rm(profile,{recursive:true,force:true,maxRetries:3});lines.close();
}
assert(exitObserved);process.stdout.write(JSON.stringify({kind:'done',checks:checks.length,shots:shots.length})+'\n');
