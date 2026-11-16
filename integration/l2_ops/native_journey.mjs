// Real same-task S0 journey. No server, task fixture, report fixture or free flag.
export async function nativeJourney(c) {
  const {ev,call,nav,click,select,check,screenshot,rpc,login,openNewReport,writeFile,path,out,origin}=c;
  const base=origin+'/b5a/m2/';
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
  async function c2Login(){await nav(origin+'/b5a/l2/');if(await ev(`!!document.querySelector('form[action="/b5a/l2/challenge"]')`)){await click('form button',true);const q=JSON.parse(await ev('document.body.innerText'));await c.redeemL2(q)}await click('[data-key=l2-open-report]',true)}
  await c2Login();
  const root=await ev('location.href');
  const reportPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S0-native-report-not-example',await ev("document.querySelectorAll('[data-source-mode=NATIVE_VERIFIED_PACK]').length>0&&document.body.innerText.includes('P40')&&document.body.innerText.includes('V25')&&!document.body.innerText.includes('MP25')"));
  await screenshot('s0-native-report.png');
  await nav(root+'/evidence');await screenshot('s0-source-evidence.png');
  await nav(root+'/blueprint');await screenshot('s0-rebuild-blueprint.png');
  const packages=await ev('document.querySelectorAll(".l2-blueprint").length');
  await nav(root+'/review');
  for(const s of await ev(`[...document.querySelectorAll('select[name^="item."]')].map(x=>'[name="'+x.name+'"]')`))await select(s,1);
  await select('[name=action]',1);await click('[name=reason]');await call('Input.insertText',{text:'实际新任务的工业合成内部审核：逐项核对证据、配置比较与UNKNOWN；不是工程认证、正式人审或外部交付。'});await click('[name=attest]');
  await click('[data-key=l2-save-review]',true);
  await check('S0-controlled-current-review-saved',await ev("document.body.innerText.includes('受控演练决定已保存')"));
  await screenshot('s0-controlled-receipt.png');
  // Fresh original M1 signature, SAME actual task/pack/report. No TTL extension.
  await login('404',false);await sourceLogin();await c2Login();
  await click('[data-key=l2-business-brief]',true);await click('[data-key=l2-save-brief]',true);
  await check('S0-actual-Brief-PG-COMMIT-and-readback',await ev("document.body.innerText.includes('PostgreSQL 回读')&&document.body.innerText.includes('费用未知')&&document.body.innerText.includes('尚未关联真实咨询')"));
  const proof=await rpc('native-proof');
  await check('S0-full-same-task-native-chain',proof.brief_stored&&proof.pages.length===8&&['request_id','run_id','job_id','source_ref'].every(k=>proof.task[k]===task[k])&&proof.brief.pins.native_pack_ref===proof.pack_ref&&proof.brief.pins.diagnosis_ref===proof.diagnosis_ref&&proof.brief.pins.report_sha256===reportPins.display_hash&&packages===proof.counts.blueprint,proof.brief.pins);
  await screenshot('s0-internal-brief.png');
  async function pdf(url,name){await nav(url);const r=await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});await writeFile(path.join(out,name),Buffer.from(r.data,'base64'))}
  await pdf(root+'/report-print','s0-report-zh-A4.pdf'); await pdf(root+'/blueprint-print','s0-blueprint-zh-A4.pdf');
  const restarted=await rpc('restart');await check('S0-real-PG-and-service-restart',Object.values(restarted).every(v=>v===true),restarted);
  await login('404',false); await sourceLogin(); await c2Login();
  const afterPins=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
  await check('S0-report-version-and-display-survive-restart',afterPins.display_hash===reportPins.display_hash&&JSON.stringify(afterPins.report_version)===JSON.stringify(reportPins.report_version));
  await click('[data-key=l2-business-brief]',true);
  const after=await rpc('native-proof');
  await check('S0-same-report-receipt-Brief-after-restart',after.brief_stored&&after.pack_ref===proof.pack_ref&&after.diagnosis_sha256===proof.diagnosis_sha256&&after.brief.content_sha256===proof.brief.content_sha256&&after.brief.review.receipt_sha256===proof.brief.review.receipt_sha256);
  await screenshot('s0-restart-readback.png');
  await writeFile(path.join(out,'native-chain.json'),JSON.stringify({task,worker,reportPins,before:proof,after},null,2));
}
