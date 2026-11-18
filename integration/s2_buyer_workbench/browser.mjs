import {spawn} from 'node:child_process';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const lines=createInterface({input:process.stdin});const iterator=lines[Symbol.asyncIterator]();
const config=JSON.parse((await iterator.next()).value);
const origin=config.origin,root=origin+'/b5a/l2/r/'+config.reportId,route=root+'/source-tasks';
async function login(subject){process.stdout.write(JSON.stringify({kind:'login',subject})+'\n');return JSON.parse((await iterator.next()).value).session;}
const profile=await mkdtemp(path.join(tmpdir(),'s2-buyer-browser-'));
const checks=[],shots=[],commands=[];const hash=b=>createHash('sha256').update(b).digest('hex');
let chrome,ws,sid,serial=0,tail='',exitObserved=false;
const pending=new Map();
function call(method,params={},sessionId=sid){return new Promise((resolve,reject)=>{const id=++serial;commands.push({id,method});
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method));},15000);
  pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'EVALUATION_FAILED');return r.result.value;}
async function check(name,condition){checks.push({name,pass:!!condition});assert(condition,name);}
async function nav(url){await call('Page.navigate',{url});for(let i=0;i<300;i++){
  if(await ev(`document.readyState==='complete'&&location.href===${JSON.stringify(url)}`))return;
  await new Promise(r=>setTimeout(r,30));}throw Error('NAVIGATION_TIMEOUT');}
async function click(selector){const p=await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);
  await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});}
async function key(key,code,virtual){for(const type of ['keyDown','keyUp'])await call('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual});}
async function select(selector,index){await click(selector);await key('Home','Home',36);for(let i=0;i<index;i++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13);}
async function shot(name){await ev('window.scrollTo(0,0)');const r=await call('Page.captureScreenshot',{format:'png'});const b=Buffer.from(r.data,'base64');await writeFile(path.join(config.out,name),b);shots.push({file:name,sha256:hash(b)});}
async function session(subject){const token=await login(subject);const {targetId}=await call('Target.createTarget',{url:'about:blank'},null);({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true},null));
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Network.setCookie',{name:'b5a_l2_session',value:token,url:origin,path:'/b5a/l2/',httpOnly:true,sameSite:'Strict'});}
try{
  const executable=process.env.RA4C0_CHROMIUM||'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
  chrome=spawn(executable,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  chrome.once('exit',()=>{exitObserved=true;});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROME_START_TIMEOUT')),30000);chrome.once('error',()=>{clearTimeout(timer);reject(Error('CHROME_START_FAILED'));});
    chrome.stderr.on('data',b=>{tail=(tail+b.toString()).slice(-4096);const m=tail.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0]);}});});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result);}});
  await session('reviewer-demo');
  for(const width of [393,375,320,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});await nav(route);
    await check('signed-five-dimensions-'+width,await ev(`document.querySelectorAll('[data-task]').length===5&&document.querySelectorAll('[data-key=s2-source-candidate]').length>=5&&document.body.innerText.includes('UNKNOWN')`));
    await check('viewport-and-permission-'+width,await ev(`document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0&&!document.cookie.includes('b5a_l2_session')&&[...document.querySelectorAll('a[href]')].every(e=>!e.href.startsWith('http')||e.href.startsWith(location.origin+'/'))`));
    await check('actual-touch-targets-'+width,await ev("[...document.querySelectorAll('a.action,summary')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().height>=44)"));
    await check('two-readonly-buyer-cards-'+width,await ev(`document.querySelectorAll('[data-key=buyer-task-card][data-buyer-authority=READ_ONLY_REVIEW_CANDIDATE]').length===2&&document.querySelector('[data-buyer-candidate-ref]').dataset.buyerCandidateRef===${JSON.stringify(config.buyerCandidateRef)}`));
    await check('four-procurement-questions-on-first-screen-'+width,await ev("(()=>{const e=document.querySelector('[data-key=buyer-first-screen]');return e.getBoundingClientRect().bottom<=innerHeight&&['看到什么','采购帮助','还不知道','下一步向企业索取'].every(t=>e.innerText.includes(t))})()"));
    if(width===393){await call('DOM.enable');await call('CSS.enable');const d=await call('DOM.getDocument');const n=await call('DOM.querySelector',{nodeId:d.root.nodeId,selector:'h1'});const f=await call('CSS.getPlatformFontsForNode',{nodeId:n.nodeId});await check('actual-chinese-glyphs',f.fonts.some(font=>font.glyphCount>0&&/CJK|YaHei|PingFang|SimSun|Heiti|Noto Sans SC|Source Han|WenQuanYi|DengXian|JhengHei/i.test(font.familyName)));}
    await shot('source-tasks-'+width+'.png');
  }
  await call('Emulation.setDeviceMetricsOverride',{width:393,height:900,deviceScaleFactor:1,mobile:false});
  if(config.ctaAvailable){
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});await nav(route);
    await check('two-scoped-cta-candidates',await ev("document.querySelectorAll('[data-key=cta-review-candidates] article[data-admission=READ_ONLY_REVIEW_CANDIDATE]').length===2&&document.querySelector('[data-key=cta-review-candidates]').innerText.includes('UNKNOWN')"));
    await click('[data-key=cta-jump]');await shot('cta-inquire-390.png');
    for(const [scenario,width] of [['hidden',390],['covered',375],['overflow',320]]){
      await nav(root+'/source-tasks/cta/'+scenario+'/'+width);
      await check('cta-source-scope-'+scenario,await ev("!!document.querySelector('[data-key=cta-source-detail]')&&document.body.innerText.includes('synthetic.invalid')&&document.body.innerText.includes('/rfq')&&document.body.innerText.includes('UNKNOWN')"));
      await shot('cta-detail-'+scenario+'-'+width+'.png');
      await click('[data-key=cta-original-image]');
      for(let i=0;i<100&&!await ev("document.contentType==='image/png'");i++)await new Promise(r=>setTimeout(r,30));
      await check('protected-source-screenshot-'+scenario,await ev(`document.contentType==='image/png'&&document.images[0]?.naturalWidth===${width}`));
    }
    await call('Emulation.setDeviceMetricsOverride',{width:393,height:900,deviceScaleFactor:1,mobile:false});
  }
  for(const index of [0,1]){
    await nav(route);await click('[href="/b5a/l2/r/'+config.reportId+'/source-tasks/buyer-cite/'+index+'"]');
    for(let i=0;i<100&&!await ev("!!document.querySelector('[data-key=s2-original-citation]')");i++)await new Promise(r=>setTimeout(r,30));
    await check('verified-buyer-card-original-bytes-'+index,await ev("!!document.querySelector('[data-buyer-authority=READ_ONLY_REVIEW_CANDIDATE]')&&document.body.innerText.includes('原始 UTF-8 字节')&&!document.querySelector('table,script')"));
    await shot('buyer-card-source-'+index+'-393.png');
  }
  await nav(route);
  await click('[data-key=s2-source-citation]');for(let i=0;i<100&&!await ev("!!document.querySelector('[data-key=s2-original-citation]')");i++)await new Promise(r=>setTimeout(r,30));
  await check('actual-citation-navigation',await ev("document.body.innerText.includes('原始 UTF-8 字节')&&document.body.innerText.includes('<th>Record type</th>')&&!document.querySelector('table')"));await shot('source-citation-393.png');
  await nav(route);await click('[data-key=s2-blueprint]');for(let i=0;i<100&&!await ev("location.pathname.endsWith('/blueprint')&&document.readyState==='complete'");i++)await new Promise(r=>setTimeout(r,30));
  await check('original-rebuild-blueprint',await ev("document.querySelectorAll('.l2-blueprint').length>0"));await shot('original-blueprint-393.png');
  await nav(root+'/review');
  for(const name of await ev("[...document.querySelectorAll('select[name^=\"item.\"]')].map(e=>e.name)"))await select('[name="'+name+'"]',1);
  await select('[name=action]',3);await click('[name=reason]');await call('Input.insertText',{text:'受控演练：核对来源声明、买方待补工况与 UNKNOWN 边界；不构成正式人审。'});await click('[name=attest]');await shot('original-review-393.png');
  await click('[data-key=l2-save-review]');for(let i=0;i<200&&!await ev("document.body.innerText.includes('受控演练决定已保存')");i++)await new Promise(r=>setTimeout(r,30));
  await check('original-control-review-real-submit',await ev("document.body.innerText.includes('受控演练决定已保存')&&document.body.textContent.includes('CONTROLLED_REVIEW_SIMULATION')"));await shot('original-decision-393.png');
  await nav(route);await check('same-report-hash-after-review',await ev(`document.body.textContent.includes(${JSON.stringify(config.displayHash)})`));
  await session('other-tenant');await nav(route);await check('actual-browser-cross-tenant-denied',await ev("!document.querySelector('[data-key=s2-source-workbench]')"));
  await session('recipient-a');await nav(route);await check('actual-browser-unclaimed-reader-denied',await ev("!document.querySelector('[data-key=s2-source-workbench]')"));
  if(config.ctaAvailable){await nav(root+'/source-tasks/cta/covered/390/image');await check('unclaimed-reader-cannot-read-source-png',await ev("document.contentType!=='image/png'&&!document.querySelector('[data-key=cta-source-detail]')"));}
}finally{
  ws?.close();if(chrome&&!exitObserved)chrome.kill('SIGTERM');
  for(let i=0;i<100&&chrome&&!exitObserved;i++)await new Promise(r=>setTimeout(r,20));
  if(chrome&&!exitObserved){chrome.kill('SIGKILL');for(let i=0;i<100&&!exitObserved;i++)await new Promise(r=>setTimeout(r,20));}
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'));}
  await writeFile(path.join(config.out,'browser.json'),JSON.stringify({checks,shots,commands,chromeExitObserved:exitObserved,formalHumanReview:false,externalDelivery:false},null,2)+'\n');
  await rm(profile,{recursive:true,force:true,maxRetries:3});lines.close();
}
assert(exitObserved);process.stdout.write(JSON.stringify({kind:'done',checks:checks.length,shots:shots.length})+'\n');
