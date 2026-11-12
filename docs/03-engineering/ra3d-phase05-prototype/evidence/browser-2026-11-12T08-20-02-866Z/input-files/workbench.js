/* UI SIMULATION ONLY. No identity, native report/decision, share, API, or persistence. */
'use strict';
(() => {
  const fixture=window.REVIEW_FIXTURE;
  const $=s=>document.querySelector(s);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const button=(id,text,fn,cls)=>{const b=el('button',text,cls);b.type='button';b.id=id;b.addEventListener('click',fn);return b};
  const copy=x=>JSON.parse(JSON.stringify(x));
  let state;
  function log(text){state.events.push(text);const li=el('li',`${String(state.events.length).padStart(2,'0')} · ${text}`);$('#events').append(li)}
  function say(text,warn=false){$('#live').textContent=text;$('#live').classList.toggle('warn',warn)}
  function allowed(){return state.access==='assigned'&&state.target.tenant===fixture.tenant&&state.target.guard!=='REJECTED'}
  function sameTarget(){return JSON.stringify(state.target)===state.openedTarget}
  function eligible(){return allowed()&&sameTarget()&&state.scenario!=='coverage'&&state.evidenceAvailable&&state.viewed&&Object.values(state.checks).every(Boolean)&&!state.result}
  function reset(scenario){
    if($('#confirmation').open)$('#confirmation').close();
    state={scenario,access:scenario==='denied'?'foreign':'assigned',target:copy(fixture.target),openedTarget:JSON.stringify(fixture.target),integrity:true,viewed:false,evidenceAvailable:true,checks:{fact:false,impact:false,action:false,verification:false,scope:false,preview:false,boundary:false},result:null,historyResult:null,events:[],pending:null,note:'',item:'impact'};
    $('#events').replaceChildren();
    document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===scenario)));
    render();log('打开固定合成场景；无真实主体或审批记录。');say('先打开原始证据，再逐项核对。所有模拟不会保存。');
    if(scenario==='denied')say('无权访问该审核内容。当前仅展示固定的拒绝视图。',true);
  }
  function checkbox(id,text,key){const l=el('label',undefined,'check');const i=el('input');i.type='checkbox';i.id=id;i.checked=state.checks[key];i.disabled=!!state.result||!sameTarget()||!allowed()||(key==='fact'&&!state.viewed);i.addEventListener('change',()=>{state.checks[key]=i.checked;log(`模拟核对：${text} → ${i.checked?'已核对':'撤销'}`);updateProgress()});l.append(i,el('span',text));return l}
  function makeCard(title){const c=el('section',undefined,'card');c.append(el('h2',title));return c}
  function render(){
    $('#context').replaceChildren();$('#review').replaceChildren();$('#inspector').replaceChildren();
    if(!allowed())return renderDenied();
    const context=el('div',undefined,'context');const info=el('div');info.append(el('h2',state.scenario==='coverage'?'0 项可报告问题 · 内部范围摘要':'联系路径 · 一个有来源支持的问题'),el('p',`${fixture.reportId} · ${fixture.tenant} · 模拟 v${state.target.version} · 2026-11-12 固定捕获`));context.append(info,el('span','PRIVATE / NOT APPROVED','pill'));$('#context').append(context);
    const c=makeCard(state.scenario==='coverage'?'检查范围，不替网站背书':'01 / 逐项核对这份材料');
    if(state.scenario==='coverage')renderCoverage(c);else renderIssue(c);
    $('#review').append(c);
    renderInspector();renderActions();
    if(state.scenario==='stale')renderMutations();
    updateProgress();
  }
  function renderIssue(c){
    const head=el('div',undefined,'card-header');head.append(el('span','采购任务 / 从产品走向联系','pill'),el('h3','联系入口的目标返回 404'));c.append(head);
    c.append(el('p','观察事实','section-label'),el('p',fixture.claims.fact),el('span','原 Guard：SOURCE_FACT_BINDING_VERIFIED · 仅字面与响应事实','guard'),button('open-evidence','查看原始证据 ↗',openEvidence),checkbox('check-fact','已对照原文、href 和捕获响应核对事实','fact'));
    const h=el('div',undefined,'hypothesis');h.append(el('p','可能影响 / 假设','section-label'),el('p',fixture.claims.impact),el('span','原 Guard：HUMAN_REVIEW_REQUIRED · 不升级为已证实事实','guard'),checkbox('check-impact','保留为假设，不声称实际丢单或收入损失','impact'));c.append(h);
    for(const [key,title,check]of [['action','建议行动 / 候选','接受为候选建议，不代表授权执行'],['verification','重新验证方法','已核对重新验证的授权边界']])c.append(el('p',title,'section-label'),el('p',fixture.claims[key]),el('span','原 Guard：HUMAN_REVIEW_REQUIRED','guard'),checkbox('check-'+key,check,key));
    appendScope(c);
  }
  function appendScope(c){const box=el('div',undefined,'rule');box.append(el('h3','必须一起阅读的范围与边界'));const list=el('ul',undefined,'limits');fixture.limits.forEach(t=>list.append(el('li',t)));box.append(list,checkbox('check-scope','已核对覆盖与未知信息；受限不等于缺陷','scope'),checkbox('check-preview','已阅读本页全文及版本信息','preview'),checkbox('check-boundary','确认仅内部模拟，不授权外发、执行或报价','boundary'));c.append(box)}
  function renderCoverage(c){const empty=el('div',undefined,'empty');empty.append(el('strong','0'),el('h3','没有足够依据的问题，就不写问题。'),el('p','固定合成联系目标响应为 HTTP 200。仅说明该次路径响应，不证明表单有效、邮件送达或全站健康。'),el('p','native ReportVersion = null · 不模拟正式报告或批准','mono'));c.append(empty,button('open-evidence','核对 200 捕获与原文 ↗',openEvidence));appendScope(c)}
  function renderInspector(){const c=makeCard('证据 / 原文与定位');c.id='evidence-panel';c.tabIndex=-1;c.append(el('p','点击问题中的证据入口，在这里核对固定捕获。不会访问原网站。','muted'));
    const meta=el('dl');for(const [key,value]of [['原始页面 URL',fixture.source.sourceUrl],['href → 目标',fixture.source.href+' → '+fixture.source.targetUrl],['捕获时刻',fixture.source.capturedAt],['HTTP 响应',`来源 200 / 联系目标 ${state.scenario==='coverage'?200:404}（合成固定记录）`],['原文 UTF-8 字节定位',`[${fixture.source.byteRange[0]}, ${fixture.source.byteRange[1]}) · 半开区间`],['source / binding / Guard 引用',fixture.source.sourceRef+' / '+fixture.source.bindingRef+' / '+fixture.source.guardRef]])meta.append(el('dt',key),el('dd',value));c.append(meta);
    if(state.viewed&&state.evidenceAvailable){c.append(el('h3','原始引文 / 惰性文本'),el('pre',fixture.source.quote));const d=el('details');d.id='raw-source';d.append(el('summary','查看完整合成原文（含惰性攻击片段）'),el('pre',fixture.source.source));c.append(d,el('p','这些 sim-* 引用是原型标签，不是生产 RA-2/Guard 证明。字节和摘要对应本地合成夹具。','muted'),button('return-issue','← 返回原问题',()=>{log('从原始证据返回原问题，焦点已恢复。');$('#open-evidence').focus();$('#open-evidence').scrollIntoView({block:'center'})}));}
    else c.append(el('p',state.evidenceAvailable?'原文尚未查阅；事实核对暂不可选。':'证据缺失，不能完成正向模拟。','notice'));
    const hashes=el('details');hashes.id='target-details';hashes.append(el('summary','完整来源摘要与模拟版本绑定'),el('p','SHA-256 / 原始合成来源','section-label'),el('p',fixture.source.sourceSha256,'hash'),el('pre',JSON.stringify(state.target,null,2)),el('p','目标按完整对象比较；浏览器侧计算/比较没有权威性。没有真实 ReviewTarget、签名或决策摘要。','muted'));c.append(hashes);$('#inspector').append(c);
  }
  function openEvidence(){if(!allowed()||!sameTarget()||!state.evidenceAvailable||state.result)return say('证据不可用或版本已变化，正向模拟被阻断。',true);state.viewed=true;log(`打开原始证据：${fixture.source.sourceId}，UTF-8 [${fixture.source.byteRange.join(', ')})；${state.scenario==='coverage'?'200':'404'} 捕获。`);render();$('#evidence-panel').focus();$('#evidence-panel').scrollIntoView({block:'start'});say('原文已打开。查阅不等于核实商业解释，也不形成审批。')}
  function renderActions(){const c=makeCard('本次模拟操作');c.id='decision-panel';
    if(state.result){const r=el('div',undefined,'result');r.append(el('strong',state.result.title),el('p',state.result.detail));c.append(r);}
    else if(!sameTarget())c.append(el('p','内容或版本已变化，旧核对全部失效。请打开新模拟版本并整份重新核对。','notice'));
    else{
      c.append(el('p','尚未完成核对','progress'));c.lastChild.id='progress';
      if(state.scenario==='coverage'){c.append(button('ack-coverage','模拟确认检查范围（仅内部）',()=>prepare('coverage'),'primary'));}
      else{c.append(button('positive','检查正向模拟前提',()=>prepare('positive'),'primary'));const l=el('label','意见对应条目','field');l.htmlFor='note-item';const select=el('select');select.id='note-item';for(const[k,v]of [['fact','观察事实'],['impact','可能影响'],['action','建议行动'],['verification','验证方法'],['scope','覆盖与限制']]){const o=el('option',v);o.value=k;select.append(o)}select.value=state.item;select.addEventListener('change',()=>state.item=select.value);const nl=el('label','退回 / 拒绝理由（1–2000 字，仅内存）','field');nl.htmlFor='review-note';const area=el('textarea');area.id='review-note';area.maxLength=2000;area.value=state.note;area.placeholder='例如：可能影响仍需明确标为假设，请勿写成实际丢单。';area.addEventListener('input',()=>state.note=area.value);c.append(l,select,nl,area);const actions=el('div',undefined,'actions');actions.append(button('request-changes','模拟退回修改',()=>prepare('changes')),button('reject','模拟拒绝此版本',()=>prepare('reject'),'danger'));c.append(actions)}
    }
    c.append(el('p','原草稿始终 NOT_APPROVED。不会创建 native decision、真实审核侧车或分享标志。','muted'));$('#review').append(c);
  }
  function updateProgress(){const n=Object.values(state.checks).filter(Boolean).length;const p=$('#progress');if(p)p.textContent=state.scenario==='coverage'?`范围核对 ${['scope','preview','boundary'].filter(k=>state.checks[k]).length}/3 · ${state.viewed?'原文已查阅':'请先查阅原文'}`:`逐项核对 ${n}/7 · ${state.viewed?'原文已查阅':'请先查阅原文'}`;if($('#positive'))$('#positive').disabled=!eligible();if($('#ack-coverage'))$('#ack-coverage').disabled=!(state.viewed&&['scope','preview','boundary'].every(k=>state.checks[k])&&sameTarget()&&!state.result)}
  function prepare(action){if(!allowed()||!sameTarget()||state.result)return say('当前上下文不可操作，模拟已阻断。',true);if(action==='positive'&&!eligible())return say('来源或逐项核对不完整。',true);if(action==='coverage'&&!(state.scenario==='coverage'&&state.viewed&&['scope','preview','boundary'].every(k=>state.checks[k])))return say('范围尚未核对。',true);if(['changes','reject'].includes(action)&&(!state.note.trim()||state.note.length>2000||/[\u202a-\u202e\u2066-\u2069]/u.test(state.note)))return say('请填写 1–2000 字的具体理由，不接受方向控制字符。',true);
    state.pending={action,target:JSON.stringify(state.target),note:state.note,item:state.item};const box=$('#confirm-body');box.replaceChildren(el('p',`合成任务 ${fixture.reportId} / v${state.target.version}`),el('p',action==='positive'?'仅检查模拟前提；未形成真实 APPROVE。':action==='coverage'?'只确认内部检查范围，不形成报告或批准。':`仅模拟${action==='changes'?'退回修改':'拒绝'}，关闭本轮演练。`),el('pre',state.pending.target),el('p','没有真人签署、持久提交或 Owner 分享授权。', 'notice'));if(state.note)box.append(el('p',`条目 ${state.item}：${state.note}`));$('#confirmation').showModal();$('#cancel-confirm').focus();log('打开二次确认，锁定当前模拟版本。')}
  function commit(){const p=state.pending;if(!p||!allowed()||!sameTarget()||p.target!==JSON.stringify(state.target)||state.result||(p.action==='positive'&&!eligible())){$('#confirmation').close();state.pending=null;return say('确认期间上下文变化，旧操作已阻断。',true)}
    const titles={positive:'模拟满足审核条件，未形成真实 APPROVE',coverage:'模拟范围已核对 · 仅内部',changes:'模拟已退回修改 · 本轮关闭',reject:'模拟已拒绝此版本 · 本轮关闭'};
    state.result={kind:p.action,title:titles[p.action],detail:['changes','reject'].includes(p.action)?`条目 ${p.item}：${p.note}。原文未改；继续须创建新模拟版本并重新核对。`:'原始机器状态、NOT_APPROVED 与未知范围不变；没有真实决定、原生报告或分享授权。',target:p.target};state.pending=null;$('#confirmation').close();log(state.result.title);render();say(state.result.title);$('#decision-panel').scrollIntoView({block:'center'})}
  function mutate(key){if(!allowed())return;const old=state.result;state.target[key]=key==='version'?state.target.version+1:key==='tenant'?'sim-tenant-b':state.target[key]+'-changed';if(['html','citation','source'].includes(key))state.integrity=false;state.historyResult=old||state.historyResult;state.result=null;state.viewed=false;Object.keys(state.checks).forEach(k=>state.checks[k]=false);log(`模拟 ${key} 变化：旧核对/正向结果当前失效，不复用。`);render();say('版本绑定已变化，旧操作全部阻断；需打开新版本重新核对。',true)}
  function renderMutations(){const c=makeCard('版本变化实验');c.append(el('p','选择一个变化：即使页脚或布局变了，也必须重新审核。','muted'));const label=el('label','模拟变化类型','field');label.htmlFor='mutation-type';const select=el('select');select.id='mutation-type';for(const[k,t]of [['version','报告版本 v1 → v2'],['html','HTML 内容'],['citation','引用 / 字节定位'],['summary','报告摘要'],['footer','页脚'],['layout','布局 / CSS'],['source','来源对象'],['tenant','租户上下文']]){const o=el('option',t);o.value=k;select.append(o)}c.append(label,select,button('mutate','模拟所选变化',()=>mutate(select.value)));if(!sameTarget()&&allowed()&&state.integrity)c.append(el('p','旧记录保留；未产生新审核。新版只是固定夹具的内存演练，不是生产重新验证。','diff'),button('open-new-version','打开新模拟版本（重新核对）',()=>{state.target.version=Math.max(2,state.target.version);state.openedTarget=JSON.stringify(state.target);state.result=null;state.pending=null;log('打开新模拟版本；所有勾选为空，不继承旧结果。');render();say('新模拟版本已打开，请重新核对。')}));if(!state.integrity)c.append(el('p','原文 / 引用 / HTML 完整性已变化，本场景不能自行重哈希后继续；请重置固定夹具。生产需独立来源重放。','notice'));if(state.historyResult)c.append(el('p',`历史模拟结果：${state.historyResult.title} / 当前失效`,'diff'));$('#inspector').append(c);
    if(sameTarget()&&!state.result)c.append(button('missing-evidence','模拟原始证据缺失',()=>{state.evidenceAvailable=false;state.viewed=false;state.checks.fact=false;log('模拟证据缺失：正向操作已阻断。');render();say('证据缺失；不得仅凭全局引用继续。',true)}));}
  function renderDenied(){const c=makeCard('无权访问该审核内容');c.classList.add('blocked');c.append(el('p','这是固定的离线拒绝场景，不是真实租户鉴权。合成夹具随原型公开可读，UI 隐藏不能构成安全隔离。'),el('p','拒绝视图不显示被拒任务的标题、id、租户、版本、hash 或 quote。','muted'));
    const l=el('label','选择固定拒绝情形（非身份切换）','field');l.htmlFor='denial-type';const s=el('select');s.id='denial-type';for(const[k,t]of [['foreign','跨租户'],['unassigned','未分配任务'],['guard','Guard REJECTED']]){const o=el('option',t);o.value=k;s.append(o)}s.value=state.access;s.addEventListener('change',()=>{state.access=s.value;state.target.guard=state.access==='guard'?'REJECTED':fixture.target.guard;state.viewed=false;state.result=null;render();$('#denial-type').focus();log('切换固定拒绝视图；不读取受限事实。');say('无权访问该审核内容。没有正向操作。',true)});c.append(l,s,el('p',state.access==='guard'?'该陈述未通过来源校验。需移除或新版本重验；没有人工覆盖入口。':'当前上下文被拒绝。未展示任务内容。','notice'));$('#review').append(c);$('#inspector').append(makeCard('受限内容未展示'));}
  document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>reset(b.dataset.scenario)));
  $('#reset').addEventListener('click',()=>reset(state.scenario));$('#cancel-confirm').addEventListener('click',()=>{$('#confirmation').close();state.pending=null;say('已返回核对，未进行模拟操作。')});$('#confirmation').addEventListener('cancel',()=>state.pending=null);$('#commit-simulation').addEventListener('click',commit);
  reset('contact');
})();
