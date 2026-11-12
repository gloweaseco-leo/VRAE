// Thin read-only projection/reconciliation UI. Reuses Phase0.5 unchanged.
'use strict';
(() => {
  const $=s=>document.querySelector(s),node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
  const data=window.NATIVE_DOSSIERS,acks=new Set();let activeCase='',returnFocus=null;
  const which=()=>document.querySelector('[data-scenario][aria-pressed="true"]').dataset.scenario==='coverage'?'200':'404';
  const decode=s=>{const b=Uint8Array.from(atob(s.bodyBase64),c=>c.charCodeAt(0));const quote=new TextDecoder('utf-8',{fatal:true}).decode(b.slice(...s.byteRange));if(quote!==s.quote)throw Error('BRIDGE_QUOTE_MISMATCH');return{quote,body:new TextDecoder('utf-8',{fatal:true}).decode(b)}};
  function details(x){const d=x.native_document;return{report_id:d.metadata.report_id,version:d.metadata.version,scope:d.scope,
    draft_ref:d.draft_ref,native_report_version:d.native_report_version,html_sha256:d.html_sha256,
    editorial_content_sha256:d.editorial_content_sha256,renderer_asset_sha256:d.renderer_asset_sha256,
    renderer_version:d.renderer_version,reporting_version:d.reporting_version,guard_refs:d.pins.expected_guard_refs,
    pack_ref:d.pins.expected_pack_ref,execution_ref:d.pins.expected_execution_ref,package_ref:d.pins.expected_package_ref,
    private:d.private,approval_status:d.approval_status,shareable:d.shareable}}
  function openSource(item,button){const r=decode(item.source),c=$('#native-source-content');c.replaceChildren();
    c.append(node('p',item.claim.text),node('p',`${item.claim.status} / ${item.claim.claim_type}`,'guard'),
      node('pre',r.quote),node('p',`UTF-8 [${item.source.byteRange.join(', ')}) · ${item.source.sourceSha256}`,'mono'),
      node('pre',JSON.stringify({documentPointer:item.documentPointer,guard_ref:item.claim.guard_ref,binding_ref:item.claim.binding_ref,
        claim_pointer:item.claim.pointer,source:item.source.citation},null,2)));
    const full=node('details');full.append(node('summary','完整已保留原文（惰性文本）'),node('pre',r.body));c.append(full);
    returnFocus=button;$('#native-source-dialog').showModal();$('#native-source-dialog').scrollTop=0;$('#source-title').focus({preventScroll:true});
    const li=node('li',`只读查阅原生 ${item.claim.binding_ref} / UTF-8 [${item.source.byteRange.join(', ')})`);$('#events').append(li)}
  function sync(){
    const c=which(),x=data[c],d=x.native_document;
    if(!$('#context').textContent)return;
    // Correct fixed illustrative labels while retaining all native content verbatim.
    $('#context p').textContent=`${d.metadata.report_id} · ${d.scope.tenant_id} · 原生 v${d.metadata.version} · 捕获 ${x.source.capturedAt}`;
    const result=$('.result p');if(result?.textContent.includes('没有真实决定、原生报告或分享授权'))result.textContent=`原生 native_report_version ${d.native_report_version?'保持 REVIEW_REQUIRED':'保持 null'}，原始内容和 NOT_APPROVED 不变；未产生新的报告版本、真实审批或分享授权。`;
    const raw=$('#raw-source summary');if(raw)raw.textContent='查看完整已保留原文（惰性文本）';
    for(const p of document.querySelectorAll('#evidence-panel p.muted'))if(p.textContent.includes('sim-*'))
      p.textContent='此处引用来自实际重放的 RA2 / C3 / RA3B；只证明固定合成内容一致，不证明企业真实性或真人审批。';
    const sourcePre=$('#evidence-panel > pre');if(sourcePre){const rawValue=decode(x.source);sourcePre.textContent=rawValue.quote;const full=$('#raw-source pre');if(full)full.textContent=rawValue.body;}
    if(c==='200'){const row=[...document.querySelectorAll('#evidence-panel dt')].find(e=>e.textContent.includes('source / binding'));
      if(row){row.textContent='原生 source / 规则 citation';row.nextElementSibling.textContent=x.source.sourceRef+' / '+x.source.evidenceRef+'；该 200 CTA PASS 没有 RA3B CTA binding / Guard claim（原生字段缺失，未伪造）。'}}
    const meta=$('#evidence-panel dl');if(meta&&!meta.querySelector('[data-native-locator]')){const dt=node('dt','原生 evidence / snapshot / locator');dt.dataset.nativeLocator='true';meta.append(dt,node('dd',`${x.source.citation.evidence_ref} / ${x.source.citation.snapshot_ref} / ${x.source.citation.locator}`));}
    const box=$('#native-dossier');
    if(activeCase!==c||!box.firstChild){activeCase=c;box.replaceChildren(node('h2','原生全文与逐条来源'),node('p','原始陈述保持原文。捕获字面事实不等于企业认证；中文候选编辑仍是 HUMAN_REVIEW_REQUIRED。','muted'));
      const h=node('details');h.id='native-hashes';h.append(node('summary','完整原生版本、来源与内容摘要'),node('pre',JSON.stringify(details(x),null,2)));box.append(h);
      if(c==='200')box.append(node('p','0 项问题；native_report_version=null。200 CTA 正向路径来自规则原始捕获行，不伪造 Guard claim；下列 INFO/SEO 原文有各自真实 Guard 绑定。','native-gap'));
      for(const [index,item] of x.shownClaims.entries()){const card=node('article',undefined,'native-claim');card.dataset.pointer=item.documentPointer;
        card.append(node('h3',`${index+1}. ${item.claim.claim_type==='OBJECTIVE_SOURCE_FACT'?'原文事实':'待人工核对的候选表述'}`),node('p',item.claim.text),
          node('span',`${item.claim.status} / ${item.claim.claim_type}`,'guard'));
        const refs=node('details');refs.append(node('summary','这条陈述的完整原生引用'),node('p',`${item.documentPointer}\n${item.claim.guard_ref}\n${item.claim.binding_ref}`,'native-refs'));card.append(refs);
        const b=node('button','回查这条陈述的原始字节');b.type='button';b.className='claim-source';b.dataset.index=index;b.addEventListener('click',()=>openSource(item,b));card.append(b);
        const label=node('label',undefined,'check');const check=node('input');check.type='checkbox';check.className='native-ack';check.checked=acks.has(c+':'+index);check.addEventListener('change',()=>{check.checked?acks.add(c+':'+index):acks.delete(c+':'+index);syncPositive()});label.append(check,node('span','仅演练：已核对此条原生陈述及其限定'));card.append(label);box.append(card)}
      const pages=node('details');pages.id='native-scope';pages.append(node('summary','实际覆盖、UNKNOWN 与未检查边界'));for(const p of d.examined_pages)pages.append(node('div',`${p.role} / ${p.http_status} / ${p.status} / ${p.url} / ${p.captured_at}`,'scope-row'));pages.append(node('pre',JSON.stringify(d.buyer_journey,null,2)),node('p','本包没有另外采集 403/WAF 样本。受限时须保留范围限制；不能生成缺陷或全站健康结论。','native-gap'));box.append(pages);
      const preview=node('details');preview.id='native-preview';preview.append(node('summary','查看原生精确 HTML（只读私有草稿）'));preview.addEventListener('toggle',()=>{if(preview.open&&!preview.querySelector('iframe')){const f=node('iframe');f.className='native-preview';f.title='原生精确私有 HTML / NOT APPROVED';f.setAttribute('sandbox','');f.src=x.native_html_path;preview.append(f)}});box.append(preview);
    }
    syncPositive();
  }
  function syncPositive(){const b=$('#positive')||$('#ack-coverage');if(!b)return;const c=which();const complete=[...document.querySelectorAll('#review input[type=checkbox]')].every(i=>i.checked)&&!!$('#return-issue')&&data[c].shownClaims.every((_,i)=>acks.has(c+':'+i));b.disabled=!complete;}
  new MutationObserver(sync).observe($('#context'),{childList:true});
  document.addEventListener('change',()=>queueMicrotask(syncPositive));
  document.addEventListener('click',event=>{if(event.target.closest('[data-scenario],#reset')){acks.clear();activeCase='';}queueMicrotask(syncPositive)},true);
  $('#close-native-source').addEventListener('click',()=>{$('#native-source-dialog').close();returnFocus?.focus()});
  sync();
})();
