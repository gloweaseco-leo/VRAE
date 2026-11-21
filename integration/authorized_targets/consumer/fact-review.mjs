// Static declarations are neither a rule PASS nor a tested inquiry.
const fail=()=>{throw new Error('INVALID_DIAGNOSIS_DELIVERY')}
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b)
const integer=n=>Number.isInteger(n)&&n>=0
const numbers=['connect_ms','stream_setup_ms','first_byte_after_send_ms','headers_after_send_ms','body_after_headers_ms','exchange_ms']
export function factReview(body,pages,pointer) {
  const r=body.fact_review,d=body.deterministic_diagnosis
  if(r===undefined&&body.customer_presentation.fact_review===undefined)return null
  if(!r||!equal(r,body.customer_presentation.fact_review)||r.contract!=='vrae.fact-review.v1'||
    r.artifact_sha256!==body.artifact_sha256||r.pack_ref!==d.expected_pack_ref||r.native_execution_ref!==d.native_execution_ref||
    !/^frv-[0-9a-f]{64}$/.test(r.review_ref)||r.native_fact_admission!=='NONE'||r.unknown_is_defect!==false||
    r.inquiry_submitted!==false||r.browser_performance!=='UNKNOWN'||r.whole_site_coverage_known!==false||
    !Array.isArray(r.trust)||!Array.isArray(r.inquiry)||!Array.isArray(r.technical))fail()
  const all=new Map([...body.page_scope.failed_attempt_records,...pages.values()].filter(p=>p.snapshot_ref).map(p=>[p.snapshot_ref,p]))
  const seen=new Set(),bytes=new Map()
  for(const t of r.technical){
    const p=all.get(t.snapshot_ref)
    if(!p||seen.has(t.snapshot_ref)||t.capture_status!==p.capture_status||t.http_status!==p.http_status||
      !/^src-[0-9a-f]{64}$/.test(t.source_ref)||!/^\/pages\/\d+$/.test(t.source_locator)||
      !integer(t.response_body_bytes)||!integer(t.redirect_count)||t.is_defect!==false)fail()
    seen.add(t.snapshot_ref);bytes.set(t.snapshot_ref,t.response_body_bytes)
    const m=t.measurement
    if(m===null){if(t.timing_state!=='UNKNOWN'||t.samples!==0)fail()}
    else if(!m||t.http_status===null||t.timing_state!=='MEASURED'||t.samples!==1||m.samples!==1||
      m.method!=='PINNED_HTTP_MONOTONIC_V1'||m.scope!=='FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS'||
      Object.keys(m).length!==9||numbers.some(k=>!integer(m[k])||m[k]>600000)||
      m.first_byte_after_send_ms>m.headers_after_send_ms||m.headers_after_send_ms+m.body_after_headers_ms>m.exchange_ms||
      m.connect_ms+m.stream_setup_ms>m.exchange_ms)fail()
  }
  if(seen.size!==all.size)fail()
  const hashes=new Map()
  function binding(b,ref){
    if(!b||b.snapshot_ref!==ref||!pages.has(ref)||!/^ev-[0-9a-f]{64}$/.test(b.evidence_ref)||
      !/^[0-9a-f]{64}$/.test(b.content_sha256)||typeof b.locator!=='string'||
      !integer(b.byte_start)||!integer(b.byte_end)||b.byte_end<=b.byte_start||
      b.byte_end>bytes.get(ref)||b.byte_end>131072)fail()
    const identity=JSON.stringify([ref,b.locator,b.content_sha256])
    if(hashes.has(b.evidence_ref)&&hashes.get(b.evidence_ref)!==identity)fail()
    hashes.set(b.evidence_ref,identity)
  }
  function coverage(c,count,cap){if(!c||!integer(c.total)||c.returned!==count||count!==Math.min(c.total,cap)||c.truncated!==(c.total>count))fail()}
  const trustPointers=new Set()
  const expectedTrust=d.buyer_tasks.flatMap(t=>t.rules).filter(r=>r.rule_id==='TRUST-01').reduce((n,r)=>n+r.observations.length,0)
  const trust=r.trust.map(t=>{
    if(!t.source_pointer?.startsWith('/deterministic_diagnosis/buyer_tasks/'))fail()
    const row=pointer(body,t.source_pointer)
    if(trustPointers.has(t.source_pointer)||row.observation?.rule_id!=='TRUST-01'||!equal(t.context_facts,row.context_facts??[])||
      !equal(t.missing_prerequisites,row.missing_prerequisites??[])||t.identity_verified!==false||t.materials_authenticated!==false)fail()
    trustPointers.add(t.source_pointer)
    return {...t,nativeResult:row.observation.result}
  })
  if(trust.length!==expectedTrust)fail()
  const inquiries=new Set()
  for(const item of r.inquiry){
    if(!pages.has(item.snapshot_ref)||inquiries.has(item.snapshot_ref)||item.absence_proven!==false||item.delivery!=='UNKNOWN')fail()
    inquiries.add(item.snapshot_ref)
    if(item.state==='PARSER_UNSUPPORTED'){if(item.static_forms!==null)fail();continue}
    const s=item.static_forms
    if(item.state!=='STATIC_DECLARATIONS_RECORDED'||!s||!Array.isArray(s.forms)||!integer(s.nested_forms_excluded)||!integer(s.unclosed_forms_excluded))fail()
    coverage(s.coverage,s.forms.length,8)
    const ids=new Set()
    for(const f of s.forms){
      binding(f.binding,item.snapshot_ref)
      if(!/^form-[0-9a-f]{64}$/.test(f.form_ref)||ids.has(f.form_ref)||!Array.isArray(f.fields)||
        !['ACCOUNT_CANDIDATE','INQUIRY_CANDIDATE','SEARCH_CANDIDATE','UNRESOLVED'].includes(f.purpose)||
        !['GET','POST','UNKNOWN'].includes(f.method)||!['SAME_ORIGIN','EXTERNAL','UNRESOLVED'].includes(f.action_scope)||
        !integer(f.hidden_control_count)||typeof f.submit_control_observed!=='boolean'||f.visibility!=='UNKNOWN'||
        f.product_context_transfer!=='UNKNOWN'||f.submission_tested!==false||f.delivery!=='UNKNOWN'||f.native_fact_admission!=='NONE')fail()
      ids.add(f.form_ref);coverage(f.field_coverage,f.fields.length,32)
      const fields=new Set()
      for(const v of f.fields){
        binding(v.binding,item.snapshot_ref);if(v.label_binding!==null)binding(v.label_binding,item.snapshot_ref)
        if(!/^field-[0-9a-f]{64}$/.test(v.field_ref)||fields.has(v.field_ref)||
          !['NAME','EMAIL','COMPANY','PHONE','COUNTRY','SUBJECT','MESSAGE','PRODUCT','MODEL','QUANTITY','SEARCH','ACCOUNT_SECRET','UNKNOWN'].includes(v.kind)||
          !['text','email','tel','number','search','password','textarea','select','checkbox','radio','file','url','date','other'].includes(v.input_type)||
          !['SOURCE_LABEL','INPUT_TYPE','UNRESOLVED'].includes(v.label_basis)||
          ['required_attribute','disabled_attribute','readonly_attribute'].some(k=>typeof v[k]!=='boolean')||
          v.binding.evidence_ref!==f.binding.evidence_ref||
          v.binding.byte_start<f.binding.byte_start||v.binding.byte_end>f.binding.byte_end||
          (v.label_basis==='SOURCE_LABEL'&&!v.label_binding)||
          (v.label_binding&&(v.label_binding.evidence_ref!==f.binding.evidence_ref||
            v.label_binding.byte_start<f.binding.byte_start||v.label_binding.byte_end>f.binding.byte_end)))fail()
        fields.add(v.field_ref)
      }
      const kinds=new Set(f.fields.map(v=>v.kind))
      const purpose=kinds.has('ACCOUNT_SECRET')?'ACCOUNT_CANDIDATE':kinds.has('MESSAGE')&&['EMAIL','NAME','COMPANY','PHONE'].some(k=>kinds.has(k))?'INQUIRY_CANDIDATE':kinds.has('SEARCH')&&[...kinds].every(k=>['SEARCH','UNKNOWN'].includes(k))?'SEARCH_CANDIDATE':'UNRESOLVED'
      if(f.purpose!==purpose)fail()
    }
  }
  if(inquiries.size!==pages.size)fail()
  return {trust,inquiry:r.inquiry,technical:r.technical,browserPerformance:'UNKNOWN',reviewRef:r.review_ref}
}
