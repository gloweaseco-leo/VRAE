// Shape adapter for accepted Phase0.5 only; no native object is changed.
'use strict';
(() => {
  const data=window.NATIVE_DOSSIERS;
  function target(x){const d=x.native_document;return{version:d.metadata.version,tenant:d.scope.tenant_id,
    guard:d.issues[0]?.fact_claim.status??'NO_CTA_GUARD_CLAIM',source:d.pins.expected_pack_ref,html:d.html_sha256,
    citation:JSON.stringify(x.source.citation),summary:d.editorial_content_sha256,footer:d.approval_status,
    layout:d.renderer_asset_sha256,draft_ref:d.draft_ref,native_content_hash:d.native_report_version?.content_hash??null}}
  for(const c of ['404','200']){const x=data[c],d=x.native_document;
    if(d.draft_ref!==x.held.expected_draft_ref||d.html_sha256!==x.held.expected_html_sha256||
      !d.private||d.shareable||d.approval_status!=='NOT_APPROVED'||d.issues.length!==x.held.expected_issue_count)
      throw Error('BRIDGE_DISPLAY_PIN_REFUSAL');
    for(const item of x.shownClaims){const b=Uint8Array.from(atob(item.source.bodyBase64),c=>c.charCodeAt(0));
      if(new TextDecoder('utf-8',{fatal:true}).decode(b.slice(...item.source.byteRange))!==item.source.quote)
        throw Error('BRIDGE_DISPLAY_BYTE_REFUSAL')}
  }
  const d=data['404'].native_document,i=d.issues[0];
  if(i.finding.buyer_task!=='INQUIRE'||i.fact_claim.status!=='SOURCE_FACT_BINDING_VERIFIED'||
    Object.values(i.proposals).some(p=>p.status!=='HUMAN_REVIEW_REQUIRED')||data['200'].native_document.native_report_version!==null)
    throw Error('BRIDGE_DISPLAY_TYPE_REFUSAL');
  window.REVIEW_FIXTURE={reportId:d.metadata.report_id,tenant:d.scope.tenant_id,source:data['404'].source,
    claims:{fact:i.fact_claim.text,impact:i.proposals.impact.text,action:i.proposals.action.text,verification:i.proposals.recheck.text},
    limits:d.limitations,target:target(data['404']),scenarios:{
      contact:{reportId:d.metadata.report_id,source:data['404'].source,target:target(data['404'])},
      coverage:{reportId:data['200'].native_document.metadata.report_id,source:data['200'].source,target:target(data['200'])}}};
})();
