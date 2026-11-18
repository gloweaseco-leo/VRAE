// Hooks on the original browser transport. No extra page/server/auth issuer.
export function hooks() {
  const receipt={scope:'S5_S2_S3_S4_REAL_SAME_TASK_INTERNAL_ASSEMBLY',formalHuman:false,realProvider:false};
  async function result(c,mode,root,reportPins){
    await c.nav(root+'/s3');
    await c.select('[name=mode]',mode==='NO_MODEL'?0:1);
    await c.click('[data-key=s5-run]',true);
    let data;
    for(let i=0;i<30;i++){
      data=await c.ev("(()=>{const e=document.querySelector('[data-key=s5-result]');return e?{...e.dataset}:null})()");
      if(data?.mode===mode)break;
      await new Promise(r=>setTimeout(r,400));
      await c.click('[data-key=s5-refresh]',true);
    }
    await c.check('S5-'+mode+'-original-session-current-report',data?.mode===mode&&data.contentHash===reportPins.report_version.content_hash&&data.contextRef.startsWith('s3ctx-')&&data.receiptRef.startsWith('s3receipt-'),data||{});
    await c.check('S5-'+mode+'-truthful-state',data.status===(mode==='NO_MODEL'?'NOT_RUN':'CANDIDATES_FOR_HUMAN_REVIEW'));
    await c.check('S5-'+mode+'-five-readable-tasks-and-UNKNOWN',await c.ev("document.querySelectorAll('[data-s5-task]').length===5&&document.body.innerText.includes('UNKNOWN')&&document.scripts.length===0"));
    await c.screenshot('s5-'+mode.toLowerCase()+'.png');
    return data;
  }
  return {
    async before(c,{root,task,reportPins,fresh}){
      receipt.task=task;receipt.reportPins=reportPins;
      await fresh();await c.nav(root+'/s3');
      await c.check('S5-offline-entry-same-original-SSR',await c.ev("!!document.querySelector('[data-key=s5-offline]')&&!!document.querySelector('[data-key=s5-original-report]')&&!!document.querySelector('[data-key=s5-summary][href$=\"/executive\"]')&&!!document.querySelector('[data-key=s5-brief][href$=\"/brief\"]')"));
      const form=await c.ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
      await c.check('S5-browser-cannot-submit-task-or-report-pins',await c.postForm(root+'/s3',form+'&report_hash='+'0'.repeat(64))===403);
      await fresh();await c.nav(root+'/s3');
      const refForm=await c.ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
      await c.check('S5-browser-forged-context-ref-denied',await c.postForm(root+'/s3',refForm+'&context_ref=s3ctx-forged')===403);
      await fresh();
      receipt.noModel=await result(c,'NO_MODEL',root,reportPins);
      await fresh();
      receipt.fixture=await result(c,'FIXTURE',root,reportPins);
      await c.check('S5-mode-change-preserves-original-report-hash',receipt.noModel.contentHash===receipt.fixture.contentHash);
      for(const width of [1280,390,375,320]){
        await c.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
        await c.check('S5-procurement-explanation-readable-'+width,await c.ev("document.documentElement.scrollWidth<=innerWidth&&document.querySelectorAll('[data-s5-task]').length===5&&[...document.querySelectorAll('a.action,summary,button')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().height>=44)"));
        await c.screenshot('s5-procurement-'+width+'.png');
      }
      await c.nav(root);
    },
    async after(c,{root,task,reportPins}){
      await c.nav(root+'/s3');
      await c.check('S5-restart-history-is-not-current-AI-authority',await c.ev("!!document.querySelector('[data-key=s5-history]')&&!document.querySelector('[data-key=s5-result]')"));
      await c.check('S5-same-receipt-refs-retained-without-redispatch',await c.ev(`document.body.textContent.includes(${JSON.stringify(receipt.noModel.receiptRef)})&&document.body.textContent.includes(${JSON.stringify(receipt.fixture.receiptRef)})`));
      const form=await c.ev("new URLSearchParams(new FormData(document.querySelector('form[method=post]'))).toString()");
      await c.check('S5-restart-cannot-reset-fixture-ledger',await c.postForm(root+'/s3',form.replace('mode=NO_MODEL','mode=FIXTURE'))===403);
      await c.nav(root);const pins=await c.ev("JSON.parse(document.querySelector('.l2-technical pre').textContent)");
      await c.check('S5-original-report-version-hash-unchanged',pins.display_hash===reportPins.display_hash&&JSON.stringify(pins.report_version)===JSON.stringify(reportPins.report_version));
      receipt.afterTask=task;receipt.actualS4='OWNER_MERGED_S4_SAME_TASK_EXECUTIVE_AND_INDEPENDENT_SYNTHETIC_ACK';receipt.aiHistory='METADATA_ONLY_NOT_A_DURABLE_CANDIDATE_STORE';
      await c.screenshot('s5-restart-history.png');
      await c.writeFile(c.path.join(c.out,'s5-offline-proof.json'),JSON.stringify(receipt,null,2));
    }
  };
}
