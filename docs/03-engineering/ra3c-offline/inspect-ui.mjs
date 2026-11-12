// Local-only Chromium CDP acceptance. Node built-ins; no dependency or CI edits.
import {spawn} from 'node:child_process';
import {mkdir, mkdtemp, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';

const here = path.dirname(fileURLToPath(import.meta.url));
const chrome = process.env.RA3C_CHROMIUM || 'C:/Users/liu/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe';
const out = path.join(here, 'ui');
await mkdir(out, {recursive:true});
const profileBase = path.join(here, '.browser-profile');
await mkdir(profileBase, {recursive:true});
const profile = await mkdtemp(path.join(profileBase, 'run-'));
const proc = spawn(chrome, ['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps',
  '--disable-extensions','--disable-domain-reliability','--disable-features=MediaRouter,OptimizationHints',
  '--disable-crash-reporter','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=<-loopback>',
  '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost','--remote-debugging-address=127.0.0.1',
  '--remote-debugging-port=0',`--user-data-dir=${profile}`,`--disk-cache-dir=${profile}/cache`,'about:blank'],
  {windowsHide:true, stdio:['ignore','pipe','pipe']});
let stderr='';
const endpoint = await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('LOCAL_CHROMIUM_START_TIMEOUT')),20000);
  proc.once('error',e=>{clearTimeout(timer);reject(e)});
  proc.once('exit',code=>{clearTimeout(timer);reject(new Error(`LOCAL_CHROMIUM_EARLY_EXIT_${code}`))});
  proc.stderr.on('data',d=>{stderr+=d.toString();const m=stderr.match(/ws:\/\/127\.0\.0\.1:\d+\/devtools\/browser\/[\w-]+/);
    if(m){clearTimeout(timer);resolve(m[0])}});
});
const ws=new WebSocket(endpoint);
await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
let serial=0;const pending=new Map();const network=[];const exceptions=[];
ws.addEventListener('message',event=>{
  const m=JSON.parse(event.data);
  if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result)}}
  if(m.method==='Network.requestWillBeSent')network.push({url:m.params.request.url,type:m.params.type});
  if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails.text);
});
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{
  const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP_TIMEOUT_${method}`))},20000);
  pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
})}
async function evaluate(expression,sid){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sid);
  assert(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value}
const results=[];
try{
  const version=await call('Browser.getVersion');
  for(const mode of ['404','410','200','403','xss','multi']) for(const width of [1280,375]){
    const height=width===375?812:1000;
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});
    const {sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true});
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);
    await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*','ftp://*']},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width===375},sid);
    const htmlPath=path.join(here,'preview',`contact-${mode}.html`);
    const html=await readFile(htmlPath);
    await call('Page.navigate',{url:pathToFileURL(htmlPath).href},sid);
    for(let i=0;i<100;i++){
      if(await evaluate('document.readyState',sid)==='complete')break;
      await new Promise(r=>setTimeout(r,30));
    }
    await evaluate('document.fonts.ready.then(()=>true)',sid);
    const metrics=await evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      height:document.documentElement.scrollHeight,lang:document.documentElement.lang,
      issues:document.querySelectorAll('article.issue').length,headline:document.querySelector('h1').innerText,
      scripts:document.scripts.length,forms:document.forms.length,
      activeButtons:[...document.querySelectorAll('button')].filter(b=>!b.disabled).length,
      externalLinks:[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).filter(h=>!h.startsWith('#')),
      externalAssets:[...document.querySelectorAll('[src],[srcset],[action],[formaction]')].length,
      eventAttributes:[...document.querySelectorAll('*')].flatMap(e=>e.getAttributeNames().filter(n=>/^on/i.test(n))),
      privateLabel:document.querySelector('.private-bar').innerText,xssMarker:typeof window.PWNED,
      proposals:[...document.querySelectorAll('.review-pill')].map(e=>e.innerText),
      anchorCount:document.querySelectorAll('a.cite').length}))()`,sid);
    assert(metrics.width===width&&metrics.scrollWidth<=width+1,JSON.stringify(metrics));
    assert(metrics.issues===(mode==='multi'?3:['404','410','xss'].includes(mode)?1:0));
    assert(metrics.lang==='zh-CN'&&metrics.privateLabel.includes('不可客户外发'));
    assert(metrics.scripts===0&&metrics.forms===0&&metrics.activeButtons===0&&metrics.externalAssets===0);
    assert(metrics.externalLinks.length===0&&metrics.eventAttributes.length===0);
    assert(metrics.xssMarker==='undefined');
    let printProof=null;
    if(width===1280){
      const pdf=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true},sid);
      const bytes=Buffer.from(pdf.data,'base64');
      const pages=[...bytes.toString('latin1').matchAll(/\/Type\s*\/Page\b/g)].length;
      if(pages!==1){
        await writeFile(path.join(out,`print-red-${mode}.pdf`),bytes);
        await call('Emulation.setEmulatedMedia',{media:'print'},sid);
        await call('Emulation.setDeviceMetricsOverride',{width:718,height:1047,deviceScaleFactor:1,mobile:false},sid);
        const debug=await evaluate(`(()=>Object.fromEntries(['.private-bar','.sheet','.masthead','.hero','.site-line','.journey','.body-grid','.issue','aside','.closing-grid','.footer'].map(s=>{const e=document.querySelector(s);if(!e)return[s,null];const r=e.getBoundingClientRect(),c=getComputedStyle(e);return[s,{x:r.x,y:r.y,width:r.width,height:r.height,grid:c.gridTemplateColumns,font:c.fontSize,display:c.display}]})))()`,sid);
        await writeFile(path.join(out,`print-red-${mode}.json`),JSON.stringify(debug,null,2)+'\n');
        console.log('PRINT_DIAGNOSTIC',JSON.stringify(debug));
      }
      assert(pages===1,`ONE_PAGE_PRINT_REQUIRED_${mode}_ACTUAL_${pages}`);
      await writeFile(path.join(out,`contact-${mode}-A4.pdf`),bytes);
      printProof={pages,pdf_sha256:createHash('sha256').update(bytes).digest('hex'),paper:'A4_CSS'};
    }
    const screenshot=`contact-${mode}-${width}.png`;
    const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
      clip:{x:0,y:0,width,height:metrics.height,scale:1}},sid);
    await writeFile(path.join(out,screenshot),Buffer.from(image.data,'base64'));
    const anchors=await evaluate(`[...document.querySelectorAll('a.cite')].map(a=>a.getAttribute('href'))`,sid);
    for(const anchor of anchors){
      const target=await evaluate(`(()=>{const a=[...document.querySelectorAll('a.cite')].find(a=>a.getAttribute('href')===${JSON.stringify(anchor)});a.scrollIntoView({block:'center'});const r=a.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`,sid);
      await call('Input.dispatchMouseEvent',{type:'mousePressed',x:target.x,y:target.y,button:'left',clickCount:1},sid);
      await call('Input.dispatchMouseEvent',{type:'mouseReleased',x:target.x,y:target.y,button:'left',clickCount:1},sid);
      const actual=await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(anchor.slice(1))});return{hash:location.hash,display:getComputedStyle(e).display,text:e.innerText}})()`,sid);
      assert(actual.hash===anchor&&actual.display==='block');
      assert(actual.text.includes('Observation')&&actual.text.includes('EvidencePack')&&actual.text.includes('字节区间'));
      if(mode==='404'&&anchor===anchors[0]){
        const shot=await call('Page.captureScreenshot',{format:'png'},sid);
        await writeFile(path.join(out,`evidence-404-${width}.png`),Buffer.from(shot.data,'base64'));
      }
      await evaluate(`document.querySelector(${JSON.stringify(anchor+' a')}).click()`,sid);
      assert(await evaluate('location.hash',sid)==='#report');
    }
    results.push({case:mode,viewport:{width,height},html_sha256:createHash('sha256').update(html).digest('hex'),
      screenshot,metrics,printProof,evidence_anchors_clicked:anchors.length});
    await call('Target.closeTarget',{targetId});
  }
  const externalRequests=network.filter(r=>!r.url.startsWith('file:')&&!r.url.startsWith('about:'));
  assert(externalRequests.length===0&&exceptions.length===0,JSON.stringify({externalRequests,exceptions}));
  await writeFile(path.join(out,'browser-acceptance.json'),JSON.stringify({status:'LOCAL_OFFLINE_UI_PASS',
    browser:version,results,external_requests:externalRequests,runtime_exceptions:exceptions,
    source_navigation:'LOCAL_FILE_ONLY',network_blocking:'CSP_NONE_AND_CDP_BLOCKLIST_AND_LOOPBACK_BLACKHOLE_PROXY'},null,2)+'\n');
  console.log(JSON.stringify({status:'LOCAL_OFFLINE_UI_PASS',views:results.length,
    anchors_clicked:results.reduce((n,r)=>n+r.evidence_anchors_clicked,0),external_requests:externalRequests.length}));
}finally{
  await call('Browser.close').catch(()=>{});ws.close();
  await Promise.race([new Promise(r=>proc.once('exit',r)),new Promise(r=>setTimeout(r,4000))]);
  if(proc.exitCode===null)proc.kill();
}
