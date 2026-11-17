// Real same-task S0 journey. No server, task fixture, report fixture or free flag.
export async function nativeJourney(c) {
  const {ev,call,nav,click,select,check,screenshot,rpc,login,openNewReport,postForm,statusOf,writeFile,path,out,origin}=c;
  const base=origin+'/b5a/m2/';
  async function keySelectAll(){await call('Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});await call('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65})}
  await nav(base);await check('S0-unsigned-native-form-refused-with-original-CSP',await postForm(base+'create','case=p40&_csrf=unsigned-negative')===403);
  await login('404'); await nav(base+'tasks');
  await select('[name=case]',2); await click('[data-key=m2-create]',true);
  const taskURL=await ev('location.href');
  const task=await ev("Object.fromEntries(['request_id','run_id','job_id','source_ref'].map(k=>[k,document.querySelector('[data-key=m2-'+k+']')?.textContent]))");
  await check('S0-new-industrial-APP202',task.source_ref==='l2-industrial-p40-v3'&&await ev("document.querySelector('[data-app-status]')?.dataset.appStatus==='202'"),task);
  await screenshot('s0-new-task.png');
  for(let i=0;i<90;i++) {if(await ev("document.querySelector('[data-key=m2-job-state]')?.textContent==='TEST_ONLY_DONE'"))break;await new Promise(r=>setTimeout(r,250));await click('[data-key=m2-status-refresh]',true)}
  await check('S0-original-worker-DONE',await ev("document.querySelector('[data-key=m2-job-state]')?.textContent==='TEST_ONLY_DONE'"));
  const worker=await rpc('result',{job:task.job_id});
  await check('S0-original-worker-real-locator', ['request_id','run_id','job_id'].every(k=>worker[k]===task[k]),worker);
  async function sourceLogin() {await nav(taskURL);await openNewReport();await nav(taskURL);await click('[data-key=l2-native-task]',true);await click('[data-key=l2-produce-native]',true)}
  await sourceLogin();
  async function c2Login(fresh=false){if(fresh)await call('Network.deleteCookies',{name:'b5a_l2_session',url:origin+'/b5a/l2/'});await nav(origin+'/b5a/l2/');if(await ev(`!!document.querySelector('form[action="/b5a/l2/challenge"]')`)){await click('form button',true);const q=JSON.parse(await ev('document.body.innerText'));await c.redeemL2(q)}await click('[data-key=l2-open-report]',true)}
  await c2Login(true);
  const root=await ev('location.href');
  let reportPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S0-native-report-not-example',await ev("document.querySelectorAll('[data-source-mode=NATIVE_VERIFIED_PACK]').length>0&&document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('MP25')"));
  await screenshot('s0-native-report.png');
  await nav(root+'/evidence');await screenshot('s0-source-evidence.png');
  await nav(root+'/blueprint');await screenshot('s0-rebuild-blueprint.png');
  const packages=await ev('document.querySelectorAll(".l2-blueprint").length');
  async function fillReview() {
    for(const selector of await ev(`[...document.querySelectorAll('select[name^="item."]')].map(x=>'[name="'+x.name+'"]')`))await select(selector,1);
    await select('[name=action]',1);await click('[name=reason]');await call('Input.insertText',{text:'实际新任务的工业合成内部审核：逐项核对证据、配置比较与UNKNOWN；不是工程认证、正式人审或外部交付。'});await click('[name=attest]');
  }
  async function review() {
    await nav(root+'/review');await fillReview();
    await click('[data-key=l2-save-review]',true);
    await check('S0-controlled-current-review-saved',await ev("document.body.innerText.includes('受控演练决定已保存')"));
  }
  await review();await screenshot('s0-controlled-receipt.png');
  // Fresh original M1 signature, SAME actual task/pack/report. No TTL extension.
  await login('404',false);await sourceLogin();await c2Login(true);
  await click('[data-key=l2-business-brief]',true);await click('[data-key=l2-save-brief]',true);
  await check('S0-actual-Brief-PG-COMMIT-and-readback',await ev("document.body.innerText.includes('PostgreSQL 回读')&&document.body.innerText.includes('费用未知')&&document.body.innerText.includes('尚未关联真实咨询')"));
  let proof=await rpc('native-proof');
  await check('S0-full-same-task-native-chain',proof.brief_stored&&proof.pages.length===8&&['request_id','run_id','job_id','source_ref'].every(k=>proof.task[k]===task[k])&&proof.brief.pins.native_pack_ref===proof.pack_ref&&proof.brief.pins.diagnosis_ref===proof.diagnosis_ref&&proof.brief.pins.report_sha256===reportPins.display_hash&&packages===proof.counts.blueprint,proof.brief.pins);
  await screenshot('s0-internal-brief.png');
  const initialProof=proof, audit=[];
  async function refresh() {await login('404',false);await sourceLogin();await c2Login(true)}
  async function brief() {await nav(root);await click('[data-key=l2-business-brief]',true)}
  for(const name of ['idempotent','wrong-task','pg-interruption','task-connection-loss','sqlite-unavailable','post-exit-review-change','concurrent-review','c2-revocation']) {
    await refresh();await brief();
    await check('S0-live-current-before-'+name,statusOf(root+'/brief')===200);
    await rpc('s0-audit-queue',{case:name});await click('[data-key=l2-save-brief]',true);
    const result=await rpc('s0-audit-result',{case:name});audit.push(result);
    await writeFile(path.join(out,'live-dual-authority.json'),JSON.stringify(audit,null,2));
    await check('S0-live-dual-authority-'+name,result.pass&&result.task.job_id===task.job_id&&result.detached_authority===false,result);
    if(name==='post-exit-review-change'||name==='concurrent-review') {await nav(root+'/brief');const current=await rpc('native-proof');await check('S0-stale-approved-Brief-not-current-'+name,!current.brief_stored&&current.brief.preparation_status==='REJECTED'&&current.brief.content_sha256!==initialProof.brief.content_sha256);await nav(root);await review()}
    if(name==='c2-revocation') {await nav(root+'/brief');await check('S0-revoked-current-review-refused',await ev("document.body.innerText.includes('L2_NATIVE_BUSINESS_DENIED')"));const r=await rpc('restart');await check('S0-new-boot-after-permanent-key-revocation',Object.values(r).every(v=>v===true));await refresh()}
  }
  // Actual native report revision: new version changes only the blueprint;
  // the original pack/run/evidence survive, and an UNUSED old form must fail.
  await refresh();await nav(root+'/review');await fillReview();
  await check('S0-unused-old-form-is-complete-and-valid',await ev("document.querySelector('form[method=post]').checkValidity()&&document.querySelector('[name=attest]').checked&&document.querySelector('[name=action]').value==='APPROVE'&&[...document.querySelectorAll('select[name^=\"item.\"]')].every(e=>e.value==='ACK')"));
  const staleForm=await ev(`new URLSearchParams(new FormData(document.querySelector('form[method="post"]'))).toString()`);
  await nav(root+'/blueprint');await click('.l2-editor > summary');await click('.l2-editor textarea');await keySelectAll();
  await call('Input.insertText',{text:'内部 S0 修订：企业确认型号、工况和合法资料版本后，按原证据边界实施并复验；UNKNOWN 不作为缺陷或工程认证。'});
  await click('[data-key=l2-revise]',true);await nav(root);
  const revised=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S0-real-version-append-same-task-source',revised.report_version.version===reportPins.report_version.version+1&&revised.display_hash!==reportPins.display_hash&&revised.producer.source_descriptor.task.job_id===task.job_id&&revised.producer.source_descriptor.pack_ref===proof.pack_ref);
  await check('S0-unused-old-version-form-refused',await postForm(root+'/review',staleForm)===409&&await ev("!!document.querySelector('[data-code=L2_STALE_VERSION]')"));
  await nav(root+'/brief');await check('S0-unreviewed-current-version-brief-refused',await ev("document.body.innerText.includes('L2_NATIVE_BUSINESS_DENIED')"));
  reportPins=revised;await refresh();await review();await brief();
  const briefForm=await ev(`new URLSearchParams(new FormData(document.querySelector('form[method="post"]'))).toString()`);
  await click('[data-key=l2-save-brief]',true);
  await check('S0-used-brief-action-nonce-refused',await postForm(root+'/brief',briefForm)===403);
  await brief();const wrongTenant=await ev(`new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()`);
  await check('S0-browser-cannot-select-another-tenant',await postForm(root+'/brief',wrongTenant+'&tenant_id=tenant-other')===403);
  await brief();proof=await rpc('native-proof');
  await check('S0-current-revised-Brief-same-native-origin',proof.brief_stored&&proof.brief.pins.report_version===String(revised.report_version.version)&&proof.pack_ref===initialProof.pack_ref&&proof.diagnosis_ref===initialProof.diagnosis_ref);
  await screenshot('s0-final-current-brief.png');
  // Reauthenticate the SAME task before printing; an expired 403 page is not a report.
  await refresh();await brief();proof=await rpc('native-proof');
  async function pdf(url,name){
    await nav(url);await check(name+'-native-print-content',await ev("document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('L2_REQUEST_DENIED')&&!document.body.innerText.includes('L2_NATIVE_BUSINESS_DENIED')"));
    const r=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
    const raw=Buffer.from(r.data,'base64'),pages=(raw.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;
    await check(name+'-actual-multipage-A4',pages>1,{pages,bytes:raw.length});await writeFile(path.join(out,name),raw);
  }
  await pdf(root+'/report-print','s0-report-zh-A4.pdf'); await pdf(root+'/blueprint-print','s0-blueprint-zh-A4.pdf');
  const restarted=await rpc('restart');await check('S0-real-PG-and-service-restart',Object.values(restarted).every(v=>v===true),restarted);
  await login('404',false); await sourceLogin(); await c2Login(true);
  const afterPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S0-report-version-and-display-survive-restart',afterPins.display_hash===reportPins.display_hash&&JSON.stringify(afterPins.report_version)===JSON.stringify(reportPins.report_version));
  await click('[data-key=l2-business-brief]',true);
  const after=await rpc('native-proof');
  await check('S0-same-report-receipt-Brief-after-restart',after.brief_stored&&after.pack_ref===proof.pack_ref&&after.diagnosis_sha256===proof.diagnosis_sha256&&after.brief.content_sha256===proof.brief.content_sha256&&after.brief.review.receipt_sha256===proof.brief.review.receipt_sha256);
  await screenshot('s0-restart-readback.png');
  await refresh();await brief();await check('S0-valid-current-before-access-negatives',statusOf(root+'/brief')===200);
  await nav(origin+'/b5a/l2/r/l2-native-not-this-task/brief');await check('S0-other-report-scope-refused',statusOf('/b5a/l2/r/l2-native-not-this-task/brief')===404&&await ev("!document.querySelector('.l2-finding')"));
  const cookies=await call('Network.getCookies',{urls:[origin+'/b5a/l2/']});
  const own=cookies.cookies.find(x=>x.name==='b5a_l2_session');
  await call('Network.setCookie',{name:own.name,value:'unassigned-user-session-00000000000000000000',url:origin+'/b5a/l2/',path:own.path,httpOnly:true,sameSite:'Strict'});
  await nav(root+'/brief');await check('S0-wrong-review-actor-cookie-refused',await ev("document.body.innerText.includes('L2_NATIVE_BUSINESS_DENIED')"));
  await call('Network.setCookie',{name:own.name,value:own.value,url:origin+'/b5a/l2/',path:own.path,httpOnly:true,sameSite:'Strict'});
  await brief();await check('S0-restored-valid-session-before-natural-expiry',statusOf(root+'/brief')===200);
  // Wait for the ORIGINAL current M1 session to expire; do not shorten/renew it.
  const began=Date.now();let expired=false;
  while(Date.now()-began<95000){await nav(root+'/brief');if(statusOf(root+'/brief')===403){expired=true;break}await new Promise(r=>setTimeout(r,1000))}
  await check('S0-original-task-timeout-refused',expired,{wait_ms:Date.now()-began,original_ttl_changed:false});
  await check('S0-expired-brief-offers-original-task-login',await ev("!!document.querySelector('[data-key=l2-task-login]')"));await click('[data-key=l2-task-login]',true);
  await refresh();await brief();const reauthorized=await rpc('native-proof');
  await check('S0-real-reauth-same-current-Brief-after-expiry',reauthorized.brief_stored&&reauthorized.brief.content_sha256===proof.brief.content_sha256);
  await writeFile(path.join(out,'native-chain.json'),JSON.stringify({task,worker,reportPins,initial:initialProof,liveAudit:audit,before:proof,after},null,2));
}
