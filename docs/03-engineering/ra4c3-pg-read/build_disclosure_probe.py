"""Build a focused diagnostic from the retained exact-RED browser harness.

This does not replace the complete browser acceptance run. No database mutation.
"""
from pathlib import Path
import subprocess

own = Path(__file__).resolve().parent
source = subprocess.check_output(['git', 'show', '3009603:docs/03-engineering/ra4c3-pg-read/browser-test.mjs']).decode()
prefix = source[:source.index('  for(const width of [1280,375,320]){')]
prefix = prefix.replace("'browser-'+new Date()", "'disclosure-probe-'+new Date()")
tail = source[source.index('}catch(error){'):]
body = r'''
  for(const width of [320,375,1280]){
    const {targetId}=await call('Target.createTarget',{url:'about:blank'});({sessionId:sid}=await call('Target.attachToTarget',{targetId,flatten:true}));
    await call('Page.enable',{},sid);await call('Runtime.enable',{},sid);await call('Network.enable',{},sid);
    await call('Emulation.setDeviceMetricsOverride',{width,height:width===1280?1000:812,deviceScaleFactor:1,mobile:width<640},sid);
    await navigate(base+'tasks/task-200');await click('[data-key="review"]','/review?');await click('[data-key="target"]','/target?');await click('[data-key="proposal"]','/proposal?');
    await fill();await click('#preview-proposal','/proposal-preview');await formMetrics(`${width}-zero-preview-layout`);
    await writeFile(path.join(out,`before-${width}.html`),await ev('document.documentElement.outerHTML'));
    await click('#checked-command > summary');
    const state=await ev(`({outcome:document.querySelector('[data-outcome]').dataset.outcome,action:document.querySelector('#proposal-action').value,open:document.querySelector('#checked-command').open,text:document.querySelector('#checked-command').innerText,content:document.querySelector('#checked-command').textContent,scrollY,viewport:{width:innerWidth,height:innerHeight,visual:visualViewport.toJSON?.()},rect:document.querySelector('#checked-command > summary').getBoundingClientRect().toJSON()})`);
    state.predicates=[state.outcome==='CONTRACT_VALID_ONLY',state.action==='SIMULATED_INTERNAL_SCOPE_ACK',state.text.includes('COVERAGE_ACK_PROPOSAL')];
    await writeFile(path.join(out,`state-${width}.json`),JSON.stringify(state,null,2));
    await writeFile(path.join(out,`after-${width}.html`),await ev('document.documentElement.outerHTML'));
    await screenshot(`after-${width}.png`,true);
    records.push({id:`${width}-legacy-three-predicates`,pass:state.predicates.every(Boolean),observed:state.predicates});
    await writeFile(path.join(out,'assertions.json'),JSON.stringify(records,null,2));
    console.log(JSON.stringify({width,predicates:state.predicates,open:state.open}));
    await call('Target.closeTarget',{targetId});
  }
  if(records.some(r=>!r.pass))process.exitCode=1;
'''
(own / 'disclosure-probe.mjs').write_text(prefix + body + tail, encoding='utf-8')
