// Same-task S2 product QA on original transport, signer, Worker and SSR.
export async function s2Journey(c) {
  const {ev,call,nav,click,select,check,screenshot,rpc,login,openNewReport,postForm,statusOf,writeFile,path,out,origin}=c;
  const base=origin+'/b5a/m2/';
  await nav(base);
  await check('S2-unsigned-task-submit-refused',await postForm(base+'create','case=p40&_csrf=unsigned-negative')===403);
  await login('404');await nav(base+'tasks');await select('[name=case]',2);await click('[data-key=m2-create]',true);
  const taskURL=await ev('location.href');
  const task=await ev("Object.fromEntries(['request_id','run_id','job_id','source_ref'].map(k=>[k,document.querySelector('[data-key=m2-'+k+']')?.textContent]))");
  await check('S2-new-actual-APP202',task.source_ref==='l2-industrial-p40-v3'&&await ev("document.querySelector('[data-app-status]')?.dataset.appStatus==='202'"),task);
  await screenshot('s2-app202.png');
  for(let i=0;i<90;i++){if(await ev("document.querySelector('[data-key=m2-job-state]')?.textContent==='TEST_ONLY_DONE'"))break;await new Promise(r=>setTimeout(r,250));await click('[data-key=m2-status-refresh]',true)}
  await check('S2-original-independent-worker-DONE',await ev("document.querySelector('[data-key=m2-job-state]')?.textContent==='TEST_ONLY_DONE'"));
  const worker=await rpc('result',{job:task.job_id});
  await check('S2-worker-commit-in-original-lease',['request_id','run_id','job_id'].every(k=>worker[k]===task[k])&&worker.lease_commit?.inside_original_lease===true,worker.lease_commit);
  async function sourceLogin(target=taskURL){await nav(target);await openNewReport();await nav(target);await click('[data-key=l2-native-task]',true);await click('[data-key=l2-produce-native]',true)}
  async function reviewLogin(){await call('Network.deleteCookies',{name:'b5a_l2_session',url:origin+'/b5a/l2/'});await nav(origin+'/b5a/l2/');if(await ev("!!document.querySelector('form[action=\"/b5a/l2/challenge\"]')")){await click('form button',true);await c.redeemL2(JSON.parse(await ev('document.body.innerText')))}await click('[data-key=l2-open-report]',true)}
  await sourceLogin();await reviewLogin();
  const root=await ev('location.href');
  const reportPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S2-new-task-original-professional-report',await ev("document.querySelectorAll('[data-source-mode=NATIVE_VERIFIED_PACK]').length>0&&document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('MP25')"));
  await screenshot('s2-original-report.png');
  let proof=await rpc('native-proof');
  await check('S2-same-pack-source-projection-not-native-rx',proof.pages.length===8&&proof.s2_source?.pack_ref===proof.pack_ref&&proof.s2_source.scope.run_id===task.run_id&&proof.s2_source.projection_ref.startsWith('s2p-')&&proof.s2_source.authority==='READ_ONLY_CANDIDATE_NOT_RX_OR_GUARD',proof.s2_source);
  const sourceURL=root+'/source-tasks';
  async function fresh(){await login('404',false);await sourceLogin();await reviewLogin()}
  for(const width of [1280,390,375,320]){
    await fresh();
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await nav(sourceURL);
    await check('S2-actual-five-source-dimensions-'+width,await ev("document.querySelectorAll('[data-task]').length===5&&!!document.querySelector('[data-key=s2-source-workbench]')&&document.body.innerText.includes('UNKNOWN')"));
    await check('S2-current-task-projection-binding-'+width,await ev(`document.body.textContent.includes(${JSON.stringify(proof.pack_ref)})&&document.body.textContent.includes(${JSON.stringify(proof.s2_source.projection_ref)})`));
    await check('S2-mobile-boundaries-and-real-targets-'+width,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0&&[...document.querySelectorAll('a.action,summary')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().height>=44)"));
    if(width===390){await call('DOM.enable');await call('CSS.enable');const d=await call('DOM.getDocument');const n=await call('DOM.querySelector',{nodeId:d.root.nodeId,selector:'h1'});const f=await call('CSS.getPlatformFontsForNode',{nodeId:n.nodeId});await check('S2-actual-chinese-glyphs',f.fonts.some(font=>font.glyphCount>0&&/CJK|YaHei|PingFang|SimSun|Heiti|Noto Sans SC|Source Han|WenQuanYi|DengXian|JhengHei/i.test(font.familyName)))}
    await screenshot('s2-five-source-'+width+'.png');
  }
  await fresh();await nav(sourceURL);await click('[data-key=s2-source-citation]',true);
  await check('S2-real-citation-not-executed-source-HTML',await ev("!!document.querySelector('[data-key=s2-original-citation]')&&document.body.innerText.includes('原始 UTF-8 字节')&&document.scripts.length===0"));
  await screenshot('s2-original-citation.png');
  await nav(root+'/blueprint');const packages=await ev('document.querySelectorAll(".l2-blueprint").length');
  await check('S2-original-seven-package-blueprint',packages===7);
  await screenshot('s2-blueprint.png');
  await fresh();await nav(root+'/review');
  for(const selector of await ev("[...document.querySelectorAll('select[name^=\"item.\"]')].map(x=>'[name=\"'+x.name+'\"]')"))await select(selector,1);
  await select('[name=action]',1);await click('[name=reason]');await call('Input.insertText',{text:'合成新任务S2阶段复核：来源候选不晋升原Guard事实；逐项核对原报告与UNKNOWN，仅内部演练。'});await click('[name=attest]');
  const staleReview=await ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
  await click('[data-key=l2-save-review]',true);
  await check('S2-original-controlled-current-review-saved',await ev("document.body.innerText.includes('受控演练决定已保存')"));
  await screenshot('s2-review-receipt.png');
  await fresh();await nav(root+'/brief');await click('[data-key=l2-save-brief]',true);
  await check('S2-real-PG-Brief-COMMIT',await ev("document.body.innerText.includes('PostgreSQL 回读')&&document.body.innerText.includes('费用未知')&&document.body.innerText.includes('尚未关联真实咨询')"));
  proof=await rpc('native-proof');
  await check('S2-full-single-task-source-review-Brief-chain',proof.brief_stored&&['request_id','run_id','job_id','source_ref'].every(k=>proof.task[k]===task[k])&&proof.brief.pins.native_pack_ref===proof.pack_ref&&proof.brief.pins.diagnosis_ref===proof.diagnosis_ref&&proof.brief.pins.report_sha256===reportPins.display_hash&&proof.s2_source.pack_ref===proof.pack_ref,proof.brief.pins);
  await screenshot('s2-internal-Brief.png');
  const before=proof;
  await fresh();
  for(const [suffix,name] of [['/report-print','s2-report-zh-A4.pdf'],['/blueprint-print','s2-blueprint-zh-A4.pdf']]){
    await nav(root+suffix);await check(name+'-actual-current-report',await ev("document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('L2_REQUEST_DENIED')"));
    const p=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});const raw=Buffer.from(p.data,'base64');const pages=(raw.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;await check(name+'-actual-PDF-pages',pages>0,{pages,bytes:raw.length});await writeFile(path.join(out,name),raw);
  }
  await fresh();await nav(root+'/brief');
  const badTenant=await ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
  await check('S2-browser-cannot-select-other-tenant',await postForm(root+'/brief',badTenant+'&tenant_id=tenant-other')===403);
  await nav(root+'/review');await check('S2-prior-signed-review-form-refused',await postForm(root+'/review',staleReview)===403);
  const restarted=await rpc('restart');await check('S2-real-PG-and-service-restart',Object.values(restarted).every(v=>v===true),restarted);
  await login('404',false);await sourceLogin();
  await nav(sourceURL);await check('S2-pre-restart-signed-session-denied',statusOf(sourceURL)===403&&!await ev("!!document.querySelector('[data-key=s2-source-workbench]')"));
  await reviewLogin();const afterPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S2-original-report-version-hash-survive-restart',afterPins.display_hash===reportPins.display_hash&&JSON.stringify(afterPins.report_version)===JSON.stringify(reportPins.report_version));
  await nav(sourceURL);await check('S2-same-source-projection-after-restart',await ev(`document.body.textContent.includes(${JSON.stringify(before.s2_source.projection_ref)})`));
  await nav(root+'/brief');const after=await rpc('native-proof');
  await check('S2-same-report-review-Brief-readback',after.brief_stored&&after.pack_ref===before.pack_ref&&after.diagnosis_sha256===before.diagnosis_sha256&&after.brief.content_sha256===before.brief.content_sha256&&after.brief.review.receipt_sha256===before.brief.review.receipt_sha256&&after.s2_source.projection_ref===before.s2_source.projection_ref);
  await screenshot('s2-restart-readback.png');
  await call('Network.deleteCookies',{name:'b5a_l2_session',url:origin+'/b5a/l2/'});await nav(sourceURL);
  await check('S2-unsigned-source-reader-refused',statusOf(sourceURL)===403&&!await ev("!!document.querySelector('[data-key=s2-source-workbench]')"));
  await writeFile(path.join(out,'s2-native-chain.json'),JSON.stringify({scope:'S2_P2_INDUSTRIAL_STAGE_NOT_FULL_S2_EXIT',task,worker,reportPins,before,after,formalHumanGold:false,modelCalls:0,externalDelivery:false},null,2));
}
