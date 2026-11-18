// Additive CTA read-only checks on the accepted same-task browser and signer.
export async function ctaJourney(c,root,fresh) {
  const {ev,call,nav,click,check,screenshot,statusOf}=c;
  await fresh();
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:false});
  await nav(root+'/source-tasks');
  await check('CTA-main-two-scoped-cards',await ev("document.querySelectorAll('[data-key=cta-review-candidates] [data-admission=READ_ONLY_REVIEW_CANDIDATE]').length===2&&document.body.innerText.includes('转化结果')&&document.body.innerText.includes('UNKNOWN')"));
  await click('[data-key=cta-jump]');
  await check('CTA-main-real-pointer-jump-to-inquiry',await ev("location.hash==='#INQUIRE'&&document.getElementById('INQUIRE').getBoundingClientRect().top>=0&&document.getElementById('INQUIRE').getBoundingClientRect().top<innerHeight"));
  await screenshot('cta-main-inquire-390.png');
  for(const [scenario,width] of [['clean',390],['hidden',390],['covered',375],['overflow',320]]) {
    await fresh();
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    const url=root+'/source-tasks/cta/'+scenario+'/'+width;
    await nav(url);
    await check('CTA-main-evidence-obstacle-repair-'+scenario,statusOf(url)===200&&await ev("!!document.querySelector('[data-key=cta-source-detail]')&&document.querySelectorAll('[data-target]').length===2&&!!document.querySelector('[data-key=cta-buyer-obstacle]')&&!!document.querySelector('[data-key=cta-rebuild-advice]')&&document.body.innerText.includes('synthetic.invalid')&&document.body.innerText.includes('/rfq')&&document.body.innerText.includes('UNKNOWN')"));
    await check('CTA-main-console-actual-viewport-'+scenario,await ev("document.documentElement.scrollWidth<=innerWidth&&document.scripts.length===0&&[...document.querySelectorAll('a.action,summary')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().height>=44)"));
    await screenshot('cta-main-'+scenario+'-'+width+'.png');
    await click('[data-key=cta-original-image]');
    await check('CTA-main-protected-original-PNG-'+scenario,await ev(`document.contentType==='image/png'&&document.images[0]?.naturalWidth===${width}`));
  }
  await fresh();await nav(root+'/source-tasks');
}

export async function ctaAfterRevision(c,root) {
  const {ev,nav,check,statusOf}=c;
  await nav(root+'/source-tasks');
  await check('CTA-main-revision-preserves-original-S2-sources',statusOf(root+'/source-tasks')===200&&await ev("document.querySelectorAll('[data-key=buyer-task-card]').length===2&&document.querySelectorAll('[data-task]').length===5&&!document.querySelector('[data-key=cta-review-candidates]')"));
  for(const suffix of ['', '/image']) {
    const url=root+'/source-tasks/cta/covered/375'+suffix;
    await nav(url);await check('CTA-main-old-version-reference-denied'+suffix,statusOf(url)===403&&await ev("document.contentType!=='image/png'&&!document.querySelector('[data-key=cta-source-detail]')"));
  }
}
