// Real Chromium and native pointer/keyboard operations. No bearer/secret logs.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import readline from 'node:readline';
import assert from 'node:assert/strict';
import {pointerPosition} from '../../docs/03-engineering/ra4c3-pg-read/browser-input.mjs';

const lines=readline.createInterface({input:process.stdin});
let initResolve,rpcId=0;const init=new Promise(r=>initResolve=r),rpcs=new Map();
lines.on('line',s=>{const m=JSON.parse(s);if(m.type==='init')initResolve(m);else{const p=rpcs.get(m.id);if(p){rpcs.delete(m.id);p.resolve(m.result)}}});
function rpc(kind,params={}){return new Promise(resolve=>{const id=++rpcId;rpcs.set(id,{resolve});process.stdout.write(JSON.stringify({id,kind,...params})+'\n')})}
const config=await init;
let base=config.base,origin=new URL(base).origin;
const root=()=>base+'r/'+(config.reportId||'l2-pump-maker');
const native=config.native===true,findingCount=Number(config.findingCount||11);
const reviseId=config.reviseId||'bp-rfq',customId=config.customId||'bp-custom';
const out=config.out;
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(out,'private-chrome-'));
const executable=process.env.L2_CHROMIUM||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':'/usr/bin/google-chrome');
const pending=new Map(),auth=new Map(),contexts=new Map(),records=[],shots=[],network=[],exceptions=[];
let chrome,ws,sid,serial=0,loaded=0,phase='start',version;
let stderr='';
const hash=b=>createHash('sha256').update(b).digest('hex');
function call(method,params={},sessionId=sid,timeout=30000){return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT_'+method))},timeout);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert(!r.exceptionDetails,'EVALUATION_FAILED');return r.result.value}
async function check(name,pass,metadata={}){records.push({name,pass:!!pass,metadata});await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2));assert(pass,name)}
async function nav(url){const before=loaded;await call('Page.navigate',{url});await waitLoad(before)}
async function waitLoad(before){for(let i=0;i<1500;i++){if(loaded>before&&await ev("document.readyState==='complete'"))return;await new Promise(r=>setTimeout(r,20))}throw Error('LOAD_TIMEOUT')}
async function click(selector,navigate=false){const p=await pointerPosition(ev,selector),before=loaded;await call('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await call('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});if(navigate)await waitLoad(before)}
async function key(key,code,n){await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:n,nativeVirtualKeyCode:n});await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:n,nativeVirtualKeyCode:n})}
async function select(selector,index){await click(selector);await key('Home','Home',36);for(let n=0;n<index;n++)await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13)}
async function fill(selector,text){await click(selector);await call('Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});await call('Input.insertText',{text})}
async function shot(name,{height=2100,scroll=false}={}){if(!scroll)await ev('scrollTo(0,0)');const width=await ev('innerWidth'),top=await ev('scrollY'),full=await ev('document.documentElement.scrollHeight');const h=Math.min(height,full-top);const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:top,width,height:h,scale:1}});const raw=Buffer.from(r.data,'base64');await writeFile(path.join(out,name),raw);shots.push({file:name,sha256:hash(raw),width,height:h,fullHeight:full,croppedOverview:h<full})}
async function context(name){if(contexts.has(name)){sid=contexts.get(name);return}const c=await call('Target.createBrowserContext',{},null);const t=await call('Target.createTarget',{url:'about:blank',browserContextId:c.browserContextId},null);const a=await call('Target.attachToTarget',{targetId:t.targetId,flatten:true},null);sid=a.sessionId;contexts.set(name,sid);await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});await call('Emulation.setDeviceMetricsOverride',{width:1280,height:950,deviceScaleFactor:1,mobile:false})}
async function redeem(subject,challenge){const bearer=await rpc('sign',{subject,nonce:challenge.nonce});auth.set(sid,{bearer,nonce:challenge.nonce,csrf:challenge.csrf});await nav(base+'session')}
async function login(subject){await context(subject);await nav(base);if(await ev("!!document.querySelector('form[action=\"/b5a/l2/challenge\"]')")){await click('button',true);const challenge=JSON.parse(await ev('document.body.innerText'));await redeem(subject,challenge)}await nav(root());}
async function review(action=1){await nav(root()+'/review');for(const selector of await ev("[...document.querySelectorAll('select[name^=\"item.\"]')].map(e=>'[name=\"'+e.name+'\"]')"))await select(selector,1);await select('[name=action]',action);await fill('[name=reason]','受控浏览器演练：逐项核对原文、证据范围、UNKNOWN与蓝图依赖；不是实际人审或客户交付。');await click('[name=attest]');}
async function getPins(){return ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)")}
async function pdf(name){const r=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});const data=Buffer.from(r.data,'base64');const pages=(data.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;await writeFile(path.join(out,name),data);await check(name+'-actual-multipage-A4',pages>1,{pages,sha256:hash(data),bytes:data.length})}
async function issue(){await nav(root()+'/access');await select('[name=recipient]',0);await click('[data-key=l2-issue-grant]',true);const g=await ev("({id:document.querySelector('[data-key=l2-created-grant]')?.textContent,token:document.querySelector('[data-key=l2-grant-token]')?.value})");assert(g.id&&g.token,'GRANT_NOT_CREATED');return g}
async function claim(g,subject){await login(subject);await nav(root()+'/claim/'+g.id);await fill('[name=token]',g.token);await click('[data-key=l2-claim]',true)}

try{
  const args=[...(!config.interactive?['--headless=new']:[]),'--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints','--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'];
  chrome=spawn(executable,args,{windowsHide:!config.interactive,stdio:['ignore','pipe','pipe']});
  const endpoint=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CHROME_START_TIMEOUT')),30000);chrome.on('error',()=>reject(Error('CHROME_START_FAILED')));chrome.stderr.on('data',d=>{stderr+=d;const m=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);if(m){clearTimeout(timer);resolve(m[0])}})});
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',()=>reject(Error('CDP_CONNECT_FAILED')),{once:true})});
  ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('CDP_COMMAND_FAILED')):p.resolve(m.result)}}if(m.method==='Page.loadEventFired'&&m.sessionId===sid)loaded++;if(m.method==='Runtime.exceptionThrown')exceptions.push('BROWSER_EXCEPTION');if(m.method==='Network.responseReceived'){const r=m.params.response;network.push({path:new URL(r.url).pathname,status:r.status,fromDiskCache:r.fromDiskCache||false})}if(m.method==='Fetch.requestPaused')void(async()=>{const p=m.params,u=new URL(p.request.url);if(u.origin!==origin){await call('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'},m.sessionId);return}const a=auth.get(m.sessionId);if(u.pathname==='/b5a/l2/session'&&a){auth.delete(m.sessionId);await call('Fetch.continueRequest',{requestId:p.requestId,method:'POST',postData:Buffer.from('{}').toString('base64'),headers:[{name:'Origin',value:origin},{name:'Content-Type',value:'application/json'},{name:'Authorization',value:a.bearer},{name:'X-L2-Nonce',value:a.nonce},{name:'X-L2-CSRF',value:a.csrf}]},m.sessionId)}else await call('Fetch.continueRequest',{requestId:p.requestId},m.sessionId)})().catch(()=>exceptions.push('TRANSPORT_FAILED'))});
  version=await call('Browser.getVersion',{},null);
  if(config.interactive){await login('owner-demo');process.stdout.write(JSON.stringify({kind:'interactive-ready'})+'\n');for(;;){await new Promise(r=>setTimeout(r,500));if(await ev("location.pathname==='/b5a/l2/challenge'&&document.readyState==='complete'")){const challenge=JSON.parse(await ev('document.body.innerText'));await redeem('owner-demo',challenge)}}}
  phase='unsigned';await context('anonymous');await nav(root());await check('unsigned-report-denied',await ev("!document.querySelector('.l2-finding')&&document.body.innerText.includes('L2_REQUEST_DENIED')"));
  phase='depth';await login('reviewer-demo');
  await check('five-buyer-tasks-and-source-bound-depth',await ev(`document.querySelectorAll('.l2-journey article').length===5&&document.querySelectorAll('.l2-finding').length===${findingCount}&&document.body.innerText.includes('UNKNOWN')&&${native?"document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('MP25')":"document.body.innerText.includes('性能曲线下载实际返回 HTML 占位页')"}`));
  const initialPins=await getPins();
  if(config.s2_ui){
    await click('[data-key=l2-buyer-tasks]',true);
    await check('s2-same-signed-report-five-dimensions',await ev(`JSON.stringify([...document.querySelectorAll('.l2-buyer-dimension')].map(x=>x.dataset.task))===JSON.stringify(['DISCOVER','UNDERSTAND','TRUST','INQUIRE','SEARCH_TECHNICAL'])&&document.querySelectorAll('[data-rule]').length===16&&document.querySelector('.l2-buyer-overview').dataset.reportSha===${JSON.stringify(initialPins.display_hash)}&&document.querySelector('.l2-buyer-overview').dataset.reportVersion===${JSON.stringify(initialPins.report_version.report_version_id)}`));
    await check('s2-evidence-and-unknown-not-invented-fifth-dimension',await ev("document.body.innerText.includes('分母 UNKNOWN')&&document.body.innerText.includes('没有SEO评分')&&document.querySelectorAll('[data-key=buyer-evidence]').length>0&&!document.querySelector('[data-key=l2-issue-grant]')"));
    for(const width of [1280,390,375,320]){
      await call('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:false});
      await nav(root()+'/buyer-tasks');
      await check('s2-buyer-reading-no-overflow-'+width,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0"));
      await shot('s2-five-dimensions-'+width+'.png',{height:1600});
    }
    await call('Emulation.setDeviceMetricsOverride',{width:1280,height:950,deviceScaleFactor:1,mobile:false});
    await nav(root()+'/buyer-tasks');
    await ev("document.getElementById('buyer-UNDERSTAND').scrollIntoView()");await shot('s2-understand-evidence.png',{height:1500,scroll:true});
    await ev("document.getElementById('buyer-INQUIRE').scrollIntoView()");await shot('s2-inquiry-context.png',{height:1500,scroll:true});
    await ev("document.getElementById('buyer-SEARCH_TECHNICAL').scrollIntoView()");await shot('s2-search-boundaries.png',{height:1500,scroll:true});
    await click('[data-key=buyer-evidence]',true);
    await check('s2-real-evidence-route-from-reading',await ev("location.pathname.includes('/evidence/')&&document.body.innerText.includes('记录时间')"));
    await nav(root());
  }
  await check('no-invented-approval-or-business-loss',await ev(native?"document.body.innerText.includes('非正式人审')&&document.body.innerText.includes('工况比较不是已证实的网站故障')&&document.querySelectorAll('[data-source-mode=NATIVE_VERIFIED_PACK]').length>0":"document.body.innerText.includes('非正式人审')&&document.body.innerText.includes('实际点击率、送达和损失均未测')&&document.querySelectorAll('[data-source-mode=SYNTHETIC_OFFLINE]').length>0"));
  await shot('deep-report-overview.png');
  await click('[data-key=l2-blueprint]',true);
  await check('actionable-blueprint-workpackages',await ev(`document.querySelectorAll('.l2-blueprint').length===${Number(config.blueprintCount||6)}&&document.body.innerText.includes('需定制评估')&&document.body.innerText.includes('需要企业补充或确认')&&document.body.innerText.includes('如何复验改善结果')`));
  await shot('rebuild-blueprint-overview.png');
  await ev(`document.getElementById(${JSON.stringify(customId)}).scrollIntoView()`);await shot('rebuild-custom-boundary.png',{height:1100,scroll:true});
  await click('[data-key=l2-evidence]',true);
  await check('actual-evidence-quotes-and-snapshot-scope',await ev(native?"document.body.innerText.includes('P40')&&document.body.innerText.includes('18 bar')&&document.body.innerText.includes('2026-11-15T12:00:00')":"document.body.innerText.includes('Document coming soon')&&document.body.innerText.includes('text/html')&&document.body.innerText.includes('2026-11-15T12:00:00Z')"));
  await shot('source-evidence.png',{height:1600});
  phase='review';await review();await shot('review-operable.png',{height:1700});
  await ev("document.querySelector('[name=version]').value='999'");await click('[data-key=l2-save-review]',true);
  await check('stale-version-real-submit-rejected',await ev("document.body.innerText.includes('L2_STALE_VERSION')"));
  await review();await click('[data-key=l2-save-review]',true);
  await check('actual-persistent-attributed-controlled-decision',await ev("document.body.innerText.includes('受控演练决定已保存')&&document.body.textContent.includes('reviewer-demo')&&document.body.textContent.includes('CONTROLLED_REVIEW_SIMULATION')&&document.body.textContent.includes('formal_human_review')"));
  await shot('review-saved-not-formal.png',{height:1400});
  await click('[data-key=l2-primary-report]',true);await check('receipt-leads-back-to-diagnosis',await ev(`document.querySelectorAll('.l2-finding').length===${findingCount}`));
  await nav(root()+'/access');await check('reviewer-cannot-issue-grants',await ev("document.body.innerText.includes('L2_REQUEST_DENIED')&&!document.querySelector('[name=recipient]')"));
  phase='directed';await login('owner-demo');const g=await issue();
  await check('owner-issued-directed-controlled-grant',!!g.id&&g.token.length===43,{grant_id:g.id});
  await claim(g,'recipient-b');await check('same-secret-wrong-signed-recipient-denied',await ev("document.body.innerText.includes('L2_DIRECTED_ACCESS_DENIED')&&!document.querySelector('.l2-finding')"));
  await claim(g,'recipient-a');await check('right-signed-recipient-reads-bound-report',await ev(`document.querySelectorAll('.l2-finding').length===${findingCount}`));
  const recipientPins=await getPins();await check('grant-binds-exact-version-and-full-content',recipientPins.display_hash===initialPins.display_hash);
  await context('owner-demo');await nav(root()+'/access');await shot('directed-access-management.png',{height:1600});await click('[data-key=l2-revoke-grant]',true);
  await context('recipient-a');await nav(root());await check('revocation-denies-next-real-read',await ev("!document.querySelector('.l2-finding')&&document.body.innerText.includes('L2_REQUEST_DENIED')"));await shot('revoked-access-denial.png',{height:1000});
  await context('owner-demo');const stale=await issue();
  phase='revision';await nav(root()+'/blueprint');await click('#'+reviseId+' .l2-editor > summary');
  const original=await ev(`document.getElementById(${JSON.stringify(reviseId)}).querySelector('textarea').value`);await fill('#'+reviseId+' textarea',original+' 补充：收件核验只在已获准的测试收件箱中进行，并记录责任人与结果。');await click('#'+reviseId+' [data-key=l2-revise]',true);
  const revised=await getPins();await check('real-append-version-full-hash-changes',revised.report_version.version===2&&revised.display_hash!==initialPins.display_hash&&revised.source_bundle_sha256===initialPins.source_bundle_sha256);
  await claim(stale,'recipient-a');await check('new-version-does-not-inherit-old-grant',await ev("!document.querySelector('.l2-finding')"));
  await context('owner-demo');await nav(root()+'/history');await check('history-keeps-old-decision-and-both-versions',await ev("document.querySelectorAll('[data-key=l2-version]').length===2&&document.body.innerText.includes('reviewer')===false&&document.body.innerText.includes('受控专业审阅员')"));await shot('versioned-decisions.png',{height:1600});
  phase='restart';const restarted=await rpc('restart');base=restarted.base;origin=new URL(base).origin;
  await nav(root());await check('actual-restart-old-cookie-is-not-authority',await ev("!document.querySelector('.l2-finding')"),{actualProcessExit:restarted.actual_ssr_process_exit,durableFile:restarted.same_sqlite_file_preserved,newKey:restarted.new_issuer_key});
  await login('owner-demo');const restored=await getPins();await check('restart-reads-same-current-version-and-hash',restored.display_hash===revised.display_hash&&restored.report_version.version===2);
  if(config.s2_ui){await nav(root()+'/buyer-tasks');await check('s2-restart-current-version-two-same-hash',await ev(`document.querySelector('.l2-buyer-overview').dataset.reportSha===${JSON.stringify(restored.display_hash)}&&document.querySelector('.l2-buyer-overview').dataset.reportVersion===${JSON.stringify(restored.report_version.report_version_id)}`));}
  await nav(root()+'/history');await check('restart-reads-attributed-review-history',await ev("document.body.innerText.includes('受控专业审阅员')&&document.querySelectorAll('[data-key=l2-version]').length===2"));
  phase='final-review';await review();await click('[data-key=l2-save-review]',true);await check('new-version-has-its-own-decision',await ev("document.body.innerText.includes('版本 2')&&document.body.innerText.includes('不是正式人审')"));
  await nav(root()+'/report-print');await pdf('l2-deep-report.pdf');await shot('deep-report-print-view.png',{height:1600});
  await nav(root()+'/blueprint-print');await pdf('l2-rebuild-blueprint.pdf');
  phase='mobile';await call('Emulation.setDeviceMetricsOverride',{width:375,height:900,deviceScaleFactor:1,mobile:false});await nav(root());await check('mobile-real-report-no-horizontal-overflow',await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0"));await shot('deep-report-mobile.png',{height:1800});await nav(root()+'/blueprint');await check('mobile-real-blueprint-no-horizontal-overflow',await ev("document.documentElement.scrollWidth<=innerWidth"));await shot('rebuild-blueprint-mobile.png',{height:1800});
  await check('no-browser-exceptions',exceptions.length===0);
  await writeFile(path.join(out,'browser.json'),JSON.stringify({kind:native?'L2_NATIVE_C2_COMPONENT_BROWSER_NOT_APP202_E2E':'L2_ACTUAL_SIGNED_SSR_CONTROLLED_BROWSER_PASS',version,records,shots,network,exceptions,formalHumanReviewsClaimed:0,realExternalCustomers:0},null,2));
  process.stdout.write(JSON.stringify({kind:'done',pass:true,checks:records.length,shots:shots.length})+'\n');
}catch(error){await writeFile(path.join(out,'browser-failure.json'),JSON.stringify({code:error.message,phase,records,network,exceptions},null,2));process.stdout.write(JSON.stringify({kind:'done',pass:false,code:error.message})+'\n');process.exitCode=1}
finally{
  try{if(ws?.readyState===WebSocket.OPEN)await call('Browser.close',{},null,5000)}catch{}
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('BROWSER_CLOSED'))}pending.clear();ws?.close();
  if(chrome&&chrome.exitCode===null&&chrome.signalCode===null)await new Promise(resolve=>{const timer=setTimeout(()=>{chrome.kill();resolve()},3000);chrome.once('exit',()=>{clearTimeout(timer);resolve()})});
  await writeFile(path.join(out,'browser-cleanup.json'),JSON.stringify({exitObserved:!!chrome&&(chrome.exitCode!==null||chrome.signalCode!==null)}));lines.close()
}
