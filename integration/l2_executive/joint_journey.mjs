// S4 extension of the accepted same-task S2 journey, using its original ports.
export function executiveJourney(c) {
  const {ev,call,nav,click,select,check,screenshot,rpc,postForm,statusOf,writeFile,path,out}=c;
  const records=[];let root,before,reportPins;
  async function privateOperation(operation,extra={},expected=true){
    await rpc('s4-queue',{operation,...extra});await nav(root+'/brief');
    const result=await rpc('s4-result');
    const reason=extra.negative==='signature'?'S4_RECEIVER_SIGNATURE_DENIED':extra.negative==='old_attempt'?'S4_RECEIPT_STALE_OR_CROSS_TASK':'S4_RECEIVER_UNAVAILABLE_OR_REVOKED';
    await check('S4-private-'+operation+'-'+(extra.negative||extra.state||'current'),result.ok===expected&&(expected||result.code===reason),{denial_code:result.code||null});
    records.push({operation,...extra,ok:result.ok,denial_code:result.code||null,row:result.row});return result.row;
  }
  async function read(){return privateOperation('read')}
  function internalOnly(row){return ['customer_approval','counts_as_e2','counts_as_e3','quote_allowed','external_delivery_allowed','material_authorization'].every(k=>row[k]===false)}
  return {
    async summary(url,pins,fresh){
      root=url;reportPins=pins;
      for(const width of [1280,390,375,320]){
        await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});await nav(root+'/executive');
        await check('S4-same-task-six-groups-and-five-denominators-'+width,await ev("document.querySelectorAll('[data-group]').length===6&&document.querySelectorAll('.executive-coverage li').length===5&&document.body.innerText.includes('0 项')&&document.body.innerText.includes('SERVICE_CATALOG_PENDING')"));
        const current=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
        await check('S4-summary-does-not-change-original-version-'+width,current.display_hash===pins.display_hash&&JSON.stringify(current.report_version)===JSON.stringify(pins.report_version));
        await check('S4-mobile-source-boundary-'+width,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0&&document.body.innerText.includes('UNKNOWN')"));
        await screenshot('s4-executive-'+width+'.png');
      }
      await fresh();await nav(root+'/executive-document');
      await check('S4-PDF-is-current-summary-not-denial',statusOf(root+'/executive-document')===200&&await ev("!!document.querySelector('.l2-executive')&&document.body.innerText.includes('SERVICE_CATALOG_PENDING')"));
      const raw=Buffer.from((await call('Page.printToPDF',{preferCSSPageSize:true,printBackground:true})).data,'base64');
      const pages=(raw.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length;
      await check('S4-same-task-actual-one-two-page-summary',pages>=1&&pages<=2,{pages,bytes:raw.length});
      await writeFile(path.join(out,'s4-executive.pdf'),raw);
    },
    async intake(proof,fresh){
      before=proof;await fresh();await nav(root+'/brief');
      await check('S4-four-books-original-PG',await ev("document.querySelectorAll('[data-cost-book]').length===4&&document.body.innerText.includes('PostgreSQL 回读')"));
      await privateOperation('configure');
      await click('[data-key=vf-submit]',true);let row=await read();
      await check('S4-producer-cannot-self-ACK',row.state==='WAITING_ACK'&&internalOnly(row));
      await fresh();await nav(root+'/brief');
      await privateOperation('receive',{state:'ACKNOWLEDGED',negative:'signature'},false);
      await check('S4-forged-receiver-signature-denied',statusOf(root+'/brief')===403);
      await fresh();await nav(root+'/brief');
      row=await privateOperation('receive',{state:'REJECTED'});await check('S4-independent-return',row.state==='REJECTED');
      await fresh();await nav(root+'/brief');await click('[data-key=vf-retry]',true);row=await read();
      await check('S4-retry-original-brief-next-attempt',row.state==='WAITING_ACK'&&row.attempt===2&&row.brief_sha256===before.brief.content_sha256);
      await privateOperation('receive',{negative:'old_attempt'},false);
      await check('S4-old-attempt-receipt-denied',statusOf(root+'/brief')===403);
      await fresh();await nav(root+'/brief');
      row=await privateOperation('receive',{state:'RETRYABLE_FAILED'});await check('S4-independent-retryable-failure',row.state==='RETRYABLE_FAILED');
      await fresh();await nav(root+'/brief');await click('[data-key=vf-retry]',true);await read();
      await fresh();await nav(root+'/brief');
      row=await privateOperation('receive',{state:'ACKNOWLEDGED'});
      await check('S4-independent-ACK-only-internal',row.state==='ACKNOWLEDGED'&&row.attempt===3&&internalOnly(row)&&row.brief_sha256===before.brief.content_sha256);
      const after=await rpc('native-proof');
      await check('S4-ACK-keeps-same-task-PG-and-original-report',after.brief.content_sha256===before.brief.content_sha256&&after.task.job_id===before.task.job_id&&after.pack_ref===before.pack_ref&&after.brief.pins.report_sha256===reportPins.display_hash);
      await screenshot('s4-VF-ACK-internal-only.png');
    },
    async restarted(proof){
      await nav(root+'/brief');
      await check('S4-ACK-is-not-PG-persistence',await ev("document.querySelector('[data-key=vf-intake-state]').innerText.includes('NOT_SUBMITTED')"));
      await privateOperation('configure');const row=await read();
      await check('S4-restart-forgets-volatile-ACK-preserves-PG',row===null&&proof.brief.content_sha256===before.brief.content_sha256&&proof.brief.review.receipt_sha256===before.brief.review.receipt_sha256);
      await screenshot('s4-restart-PG-brief-no-ACK.png');
    },
    async finish(fresh){
      await fresh();await nav(root+'/brief');await click('[data-key=vf-submit]',true);await read();
      await fresh();await nav(root+'/brief');
      await click('[data-key=vf-revoke]',true);let row=await read();
      await check('S4-explicit-revocation',row.state==='REVOKED'&&internalOnly(row));
      await fresh();await nav(root+'/brief');
      await privateOperation('receive',{state:'ACKNOWLEDGED'},false);
      await check('S4-revoked-receipt-denied',statusOf(root+'/brief')===403);
      await fresh();await nav(root+'/brief');
      await rpc('s0-audit-queue',{case:'wrong-task'});await click('[data-key=l2-save-brief]',true);
      const tenant=await rpc('s0-audit-result',{case:'wrong-task'});
      await check('S4-live-original-tenant-run-job-denials',tenant.pass&&Object.keys(tenant.refused).length===3,tenant);
      await fresh();await nav(root+'/brief');
      await rpc('s0-audit-queue',{case:'c2-revocation'});await click('[data-key=l2-save-brief]',true);
      const revoked=await rpc('s0-audit-result',{case:'c2-revocation'});
      await check('S4-live-original-key-revocation',revoked.pass,revoked);
      for(const suffix of ['/source-tasks','/executive','/brief']){await nav(root+suffix);await check('S4-revoked-original-key-denies-'+suffix,statusOf(root+suffix)===403)}
      const restarted=await rpc('restart');await check('S4-original-restart-after-revocation',Object.values(restarted).every(x=>x===true));
      await fresh();await nav(root+'/brief');const restored=await rpc('native-proof');
      await check('S4-key-rotation-preserves-same-PG-Brief',restored.brief.content_sha256===before.brief.content_sha256&&restored.task.job_id===before.task.job_id);
      const began=Date.now();let expired=false;
      while(Date.now()-began<130000){await nav(root+'/executive');if(statusOf(root+'/executive')===403){expired=true;break}await new Promise(r=>setTimeout(r,1000))}
      await check('S4-original-task-natural-expiry',expired,{wait_ms:Date.now()-began,original_ttl_changed:false});
      for(const suffix of ['/source-tasks','/executive-document','/brief']){await nav(root+suffix);await check('S4-expired-original-task-denies-'+suffix,statusOf(root+suffix)===403)}
      await fresh();await nav(root+'/brief');const renewed=await rpc('native-proof');
      await check('S4-original-reauth-same-report-and-PG',renewed.brief.content_sha256===before.brief.content_sha256&&renewed.task.job_id===before.task.job_id);
      await nav(root+'/review');
      for(const selector of await ev("[...document.querySelectorAll('select[name^=\"item.\"]')].map(x=>'[name=\"'+x.name+'\"]')"))await select(selector,1);
      await select('[name=action]',1);await click('[name=reason]');await call('Input.insertText',{text:'受控联合验收的完整旧版本表单；逐项核对，不构成正式人审。'});await click('[name=attest]');
      const old=await ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
      await nav(root+'/blueprint');await click('.l2-editor > summary');await click('.l2-editor textarea');
      await call('Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});
      await call('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',modifiers:2,windowsVirtualKeyCode:65});
      await call('Input.insertText',{text:'联合验收受控修订：企业确认当前资料与权利后按原证据边界复验；不自动外发或改写事实。'});
      await click('[data-key=l2-revise]',true);await nav(root);
      const revised=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
      await check('S4-explicit-revision-keeps-original-task-pack',revised.report_version.version===reportPins.report_version.version+1&&revised.producer.source_descriptor.task.job_id===before.task.job_id&&revised.producer.source_descriptor.pack_ref===before.pack_ref);
      await check('S4-old-version-review-denied',await postForm(root+'/review',old)===409);
      await nav(root+'/brief');await check('S4-old-approved-Brief-not-current-after-revision',statusOf(root+'/brief')===403);
      await nav(root+'/executive');
      const summary=await ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
      await check('S4-summary-displays-only-current-version',summary.display_hash===revised.display_hash&&summary.report_version.version===revised.report_version.version);
      await writeFile(path.join(out,'s4-native-chain.json'),JSON.stringify({scope:'S2_S4_SAME_REAL_APP202_WORKER_PG_SSR_CHAIN',task:before.task,pack_ref:before.pack_ref,originalPins:reportPins,brief_sha256:before.brief.content_sha256,receiver_separate_process:true,receipts:records,tenant,revoked,revisedPins:revised,formalHumanReview:false,externalDelivery:false},null,2));
    }
  };
}
