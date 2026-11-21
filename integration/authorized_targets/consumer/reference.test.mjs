// Synthetic contract fixtures only; fabricated REAL_PROVIDER metadata is not a real model receipt.
import test from 'node:test'
import assert from 'node:assert/strict'
import { projectResult, readDecision, retainView } from './reference.mjs'
import { projectPreviewResult } from './vf-preview-adapter.mjs'

const ref = 'aref-' + 'a'.repeat(32)
const page = { snapshot_ref: 'page-' + 'b'.repeat(64), url: 'https://example.org/products/wheel',
  observed_at: '2026-11-20T00:00:00Z', capture_status: 'FETCHED', http_status: 200 }
const taskIds = ['DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL']
const ruleIds = ['DISC-01', 'INFO-01', 'TRUST-01', 'CTA-01', 'SEO-01']

function factReviewFixture(measured=false) {
  const d=fixture('AI_UNAVAILABLE')
  Object.assign(d.deterministic_diagnosis,{expected_pack_ref:'ep-'+'d'.repeat(64),native_execution_ref:'ne-'+'e'.repeat(64)})
  d.fact_review={contract:'vrae.fact-review.v1',artifact_sha256:d.artifact_sha256,
    pack_ref:d.deterministic_diagnosis.expected_pack_ref,native_execution_ref:d.deterministic_diagnosis.native_execution_ref,
    review_ref:'frv-'+'f'.repeat(64),native_fact_admission:'NONE',unknown_is_defect:false,inquiry_submitted:false,
    browser_performance:'UNKNOWN',whole_site_coverage_known:false,
    trust:[{source_pointer:'/deterministic_diagnosis/buyer_tasks/2/rules/0/observations/0',context_facts:[],missing_prerequisites:[],identity_verified:false,materials_authenticated:false}],
    inquiry:[{snapshot_ref:page.snapshot_ref,state:'STATIC_DECLARATIONS_RECORDED',static_forms:{forms:[],coverage:{total:0,returned:0,truncated:false},nested_forms_excluded:0,unclosed_forms_excluded:0},absence_proven:false,delivery:'UNKNOWN'}],
    technical:[{snapshot_ref:page.snapshot_ref,source_ref:'src-'+'1'.repeat(64),source_locator:'/pages/0',capture_status:'FETCHED',http_status:200,response_body_bytes:1000,redirect_count:0,
      measurement:measured?{method:'PINNED_HTTP_MONOTONIC_V1',scope:'FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS',samples:1,connect_ms:10,stream_setup_ms:20,first_byte_after_send_ms:30,headers_after_send_ms:35,body_after_headers_ms:5,exchange_ms:80}:null,
      timing_state:measured?'MEASURED':'UNKNOWN',samples:measured?1:0,is_defect:false}]}
  d.customer_presentation.fact_review=structuredClone(d.fact_review)
  return d
}

test('P1 declarations and actual HTTP metrics survive AI failure without native promotion',()=>{
  for(const measured of [true,false]){
    const d=factReviewFixture(measured),out=projectPreviewResult(d,200,ref)
    assert.equal(out.buyerTasks[2].sourceFactReview[0].nativeResult,'UNKNOWN')
    assert.equal(out.buyerTasks[3].sourceFactReview[0].delivery,'UNKNOWN')
    assert.equal(out.reportView.tasks[4].sourceFactReview[0].timing_state,measured?'MEASURED':'UNKNOWN')
    assert.equal(out.insights.length,0)
  }
})

test('P1 rejects false delivery, copied trust facts, changed HTTP status and invented timing',()=>{
  for(const mutate of [r=>r.inquiry[0].delivery='DELIVERED',r=>r.trust[0].context_facts=[{kind:'INVENTED'}],
    r=>r.technical[0].http_status=404,r=>r.technical[0].measurement.exchange_ms=1,
    r=>r.technical[0].measurement.connect_ms=true,r=>r.technical.push(r.technical[0]),
    r=>r.technical[0].snapshot_ref='page-'+'0'.repeat(64)]){
    const d=factReviewFixture(true);mutate(d.fact_review);d.customer_presentation.fact_review=structuredClone(d.fact_review)
    assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
  const d=factReviewFixture();d.customer_presentation.fact_review.trust=[]
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
})

test('P1 static forms preserve source bounds and reject false inquiry capability',()=>{
  const make=()=>{
    const d=factReviewFixture(),binding={evidence_ref:'ev-'+'2'.repeat(64),snapshot_ref:page.snapshot_ref,locator:'/pages/0/evidence',content_sha256:'3'.repeat(64),byte_start:0,byte_end:900}
    const form={form_ref:'form-'+'4'.repeat(64),binding,purpose:'SEARCH_CANDIDATE',method:'GET',action_scope:'SAME_ORIGIN',hidden_control_count:0,submit_control_observed:false,
      fields:[{field_ref:'field-'+'5'.repeat(64),kind:'SEARCH',input_type:'search',label_basis:'INPUT_TYPE',required_attribute:false,disabled_attribute:false,readonly_attribute:false,binding:{...binding,byte_start:10,byte_end:40},label_binding:null}],
      field_coverage:{total:1,returned:1,truncated:false},visibility:'UNKNOWN',product_context_transfer:'UNKNOWN',submission_tested:false,delivery:'UNKNOWN',native_fact_admission:'NONE'}
    d.fact_review.inquiry[0].static_forms={forms:[form],coverage:{total:1,returned:1,truncated:false},nested_forms_excluded:0,unclosed_forms_excluded:0}
    d.customer_presentation.fact_review=structuredClone(d.fact_review);return d
  }
  assert.equal(projectPreviewResult(make(),200,ref).buyerTasks[3].sourceFactReview[0].static_forms.forms[0].purpose,'SEARCH_CANDIDATE')
  for(const mutate of [f=>f.purpose='INQUIRY_CANDIDATE',f=>f.delivery='DELIVERED',f=>f.fields[0].binding.byte_end=950,
    f=>f.fields[0].required_attribute='true',f=>f.fields[0].binding.snapshot_ref='page-'+'0'.repeat(64),
    f=>f.fields[0].label_basis='SOURCE_LABEL']){
    const d=make();mutate(d.fact_review.inquiry[0].static_forms.forms[0]);d.customer_presentation.fact_review=structuredClone(d.fact_review)
    assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
})

function supplementalFixture(blocked=false){
  const d=factReviewFixture(),r=d.fact_review,target={...page,snapshot_ref:'page-'+'7'.repeat(64),url:'https://example.org/help/specs',
    capture_status:blocked?'ACCESS_BLOCKED':'FETCHED',http_status:blocked?null:200}
  if(blocked)d.page_scope.failed_attempt_records.push({...target,reason:'ROBOTS_DISALLOWED',http_response_observed:false})
  else {d.page_scope.visited_pages.push(target);d.capture_summary.fetched_pages=2
    r.inquiry.push({...structuredClone(r.inquiry[0]),snapshot_ref:target.snapshot_ref})}
  r.technical.push({...structuredClone(r.technical[0]),snapshot_ref:target.snapshot_ref,source_locator:'/pages/1',capture_status:target.capture_status,http_status:target.http_status,response_body_bytes:blocked?0:1000})
  r.supplemental=[{source_ref:r.technical[0].source_ref,policy:'SOURCE_LINK_GAPS_V1',max_supplemental_pages:2,
    stop_reason:'PAGE_LIMIT_REACHED',whole_site_coverage_known:false,decisions:[{source_snapshot_ref:page.snapshot_ref,target_snapshot_ref:target.snapshot_ref,
      purpose:'TECHNICAL_MATERIAL',trigger:'NO_STRUCTURED_PRODUCT_FIELDS_RECORDED',product_applicability:'UNKNOWN',gap_resolved:'UNKNOWN',is_defect:false,native_fact_admission:'NONE',
      source_binding:{evidence_ref:'ev-'+'2'.repeat(64),snapshot_ref:page.snapshot_ref,locator:'/pages/0/evidence',content_sha256:'3'.repeat(64),byte_start:10,byte_end:40}}]}]
  d.customer_presentation.fact_review=structuredClone(r);return d
}

test('P2 delivers actual captured or denied investigations without resolving procurement gaps',()=>{
  for(const blocked of [true,false]){
    const d=supplementalFixture(blocked),out=projectPreviewResult(d,200,ref),held=out.reportView.tasks[1].supplementalInvestigations[0]
    assert.equal(held.result,blocked?'NOT_CAPTURED':'CAPTURED')
    assert.equal(held.target.capture_status,blocked?'ACCESS_BLOCKED':'FETCHED')
    assert.equal(held.product_applicability,'UNKNOWN');assert.equal(held.gap_resolved,'UNKNOWN')
    assert.equal(out.insights.length,0)
  }
})

test('P2 rejects changed purpose, unvisited target, false applicability and broken source ordering',()=>{
  for(const mutate of [r=>r.supplemental[0].decisions[0].purpose='PROOF_CONTEXT',
    r=>r.supplemental[0].decisions[0].target_snapshot_ref='page-'+'8'.repeat(64),
    r=>r.supplemental[0].decisions[0].gap_resolved=true,
    r=>r.supplemental[0].decisions[0].source_binding.byte_end=1001,
    r=>r.technical[0].source_locator='/pages/2',r=>r.supplemental[0].decisions.push(r.supplemental[0].decisions[0])]){
    const d=supplementalFixture();mutate(d.fact_review);d.customer_presentation.fact_review=structuredClone(d.fact_review)
    assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
})
function fixture(state = 'AI_PENDING') {
  const groups = taskIds.map((task, i) => ({ task, rules: [{ rule_id: ruleIds[i], buyer_task: task,
    observations: [{ observation: { rule_id: ruleIds[i], observation_id: 'obs-' + String(i).repeat(64),
      result: i === 1 ? 'PASS' : 'UNKNOWN', statement: 'Synthetic source statement', evidence_ids: [] },
      reason: i === 1 ? 'BOUNDED_STATIC_PRODUCT_TEXT_RETAINED' : 'HTML_UNSUPPORTED_OR_AMBIGUOUS',
      citations: i === 1 ? [{ snapshot_ref: page.snapshot_ref }] : [] }] }] }))
  return { contract: 'vrae.automatic-diagnosis.v1', audit_ref: ref, state,
    diagnosis_complete: state === 'DIAGNOSED', formal_human_review: false, publication: 'UNPUBLISHED',
    artifact_sha256: 'c'.repeat(64), analysis_outcome: state === 'AI_UNAVAILABLE' ? 'PROVIDER_FAILED' : 'PENDING',
    deterministic_diagnosis: { buyer_tasks: groups }, claims: [], model: null,
    page_scope: { visited_pages: [page], failed_attempt_records: [], unvisited_candidates:
      Array.from({ length: 60 }, (_, i) => ({ url: 'https://example.org/candidate/' + i, is_defect: false })) },
    capture_summary: { fetched_pages: 1, unvisited_candidates: 60, candidate_urls: 61, unvisited_is_defect: false },
    customer_presentation: { contract: 'vrae.diagnosis-presentation.v1', is_report: false, formal_human_review: false,
      artifact_sha256: 'c'.repeat(64), rules_available: true, analysis_text: { zh: '测试状态', en: 'Test state' },
      tasks: groups.map((g, i) => ({ task: g.task, title: { zh: '测试维度', en: 'Test task' }, observations: [{
        rule_id: ruleIds[i], observation_id: g.rules[0].observations[0].observation.observation_id,
        result: i === 1 ? 'PASS' : 'UNKNOWN', text: { zh: '测试规则事实', en: 'Test rule fact' },
        status_text: { zh: '本次有限检查', en: 'Bounded check' },
        source_pointer: `/deterministic_diagnosis/buyer_tasks/${i}/rules/0/observations/0`,
      }] })) } }
}

test('VF adapter delivers five fact groups without AI and separates candidate links', () => {
  const dto = fixture('AI_UNAVAILABLE')
  dto.model = { failure_stage: 'PROVIDER' }
  const out = projectPreviewResult(dto, 200, ref)
  assert.equal(out.state, 'ai-unavailable')
  assert.deepEqual(out.buyerTasks.map(t => t.task), taskIds)
  assert.equal(out.buyerTasks[1].observations[0].result, 'PASS')
  assert.equal(out.buyerTasks[0].observations[0].result, 'UNKNOWN')
  assert.equal(out.buyerTasks[0].observations[0].text, '测试规则事实')
  assert.equal(out.buyerTasks[0].observations[0].reason, 'HTML_UNSUPPORTED_OR_AMBIGUOUS')
  assert.equal(out.insights.length, 0)
  assert.equal(out.pages.length, 1)
  assert.equal(out.pageScope.candidates.length, 60)
  assert.equal(out.analysisOutcome, 'PROVIDER_FAILED')
  assert.equal(out.modelFailureStage, 'PROVIDER')
})

test('pending and failed AI retain all five fact groups and real capture counts', () => {
  for (const state of ['AI_PENDING', 'AI_UNAVAILABLE']) {
    const dto = fixture(state)
    const out = projectResult(dto, state === 'AI_PENDING' ? 202 : 200, ref)
    assert.equal(out.facts.length, 5)
    assert.equal(out.facts[1].observations[0].result, 'PASS')
    assert.equal(out.facts[0].observations[0].result, 'UNKNOWN')
    assert.equal(out.captureSummary.fetched_pages, 1)
    assert.equal(out.pageScope.candidates.length, 60)
    assert.equal(out.pageScope.candidatesInitiallyCollapsed, true)
    assert.equal(out.pageScope.candidatesAreDefects, false)
    assert.equal(out.claims.length, 0)
  }
})

test('a genuine-shaped synthetic AI claim keeps citations and a distinct verification step', () => {
  const dto = fixture('DIAGNOSED')
  dto.analysis_outcome = 'COMPLETED'
  dto.model = { state: 'AI_CANDIDATES_FOR_HUMAN_REVIEW', verification_realm: 'REAL_PROVIDER', real_model_calls: 1,
    usage: { usage_origin: 'PROVIDER_REPORTED', prompt_version: 'qwen-evidence-buyer-1.2.1' } }
  dto.claims = [{ task: 'UNDERSTAND', explanation: '核对已记录的参数条件。', rebuild: ['将参数及适用条件放在一起。'],
    uncertainties: ['仅检查了本次保存的静态页面。'], questions: ['参数适用哪些工况？'],
    verification: '改动后按相同来源逐项核对参数与条件。', verification_status: 'PROPOSED_NOT_EXECUTED', refs: ['cf-test'], counter_refs: [],
    source_bindings: { 'cf-test': { type: 'GUARD_LITERAL', fact: { source: { citation: { snapshot_ref: page.snapshot_ref, url: page.url } } } } },
    status: 'HUMAN_REVIEW_REQUIRED', guard_semantic_approval: false }]
  const out = projectResult(dto, 200, ref)
  assert.equal(out.claims.length, 1)
  assert.equal(out.claims[0].sources[0].url, page.url)
  assert.equal(out.claims[0].verification, dto.claims[0].verification)
  assert.equal(out.claims[0].verificationIsPlan, true)
  assert.equal(out.formalHumanReview, false)
  delete dto.claims[0].verification
  const rejected = projectResult(dto, 200, ref)
  assert.equal(rejected.claims.length, 0)
  assert.equal(rejected.facts.length, 5)
  assert.equal(rejected.aiWarning, 'AI_OUTPUT_NOT_DISPLAYABLE')
})

test('protocol fakes and unbound AI never erase deterministic facts', () => {
  const dto = fixture('DIAGNOSED')
  dto.model = { state: 'AI_CANDIDATES_FOR_HUMAN_REVIEW', verification_realm: 'PROTOCOL_FAKE_NOT_REAL_API', real_model_calls: 0 }
  assert.equal(projectResult(dto, 200, ref).facts.length, 5)
  assert.equal(projectResult(dto, 200, ref).claims.length, 0)
  dto.model = { state: 'AI_CANDIDATES_FOR_HUMAN_REVIEW', verification_realm: 'REAL_PROVIDER', real_model_calls: 1,
    usage: { usage_origin: 'PROVIDER_REPORTED', prompt_version: 'qwen-evidence-buyer-1.2.1' } }
  dto.claims = [null, 'invalid', {}]
  assert.equal(projectResult(dto, 200, ref).facts.length, 5)
  assert.equal(projectResult(dto, 200, ref).claims.length, 0)
})

test('scoped AI from two product regions is withheld without removing five-task facts', () => {
  const dto = fixture('DIAGNOSED')
  dto.model = { state: 'AI_CANDIDATES_FOR_HUMAN_REVIEW', verification_realm: 'REAL_PROVIDER', real_model_calls: 1,
    usage: { usage_origin: 'PROVIDER_REPORTED', prompt_version: 'qwen-evidence-buyer-1.3.0' } }
  const binding = scope => ({ type: 'GUARD_LITERAL', fact: { rule_id: 'INFO-01', source: {
    citation: { snapshot_ref: page.snapshot_ref, url: page.url, product_scope_ref: 'ps-' + scope.repeat(64) } } } })
  dto.claims = [{ task: 'UNDERSTAND', explanation: 'Synthetic conditional product explanation.',
    rebuild: ['Keep the model and specification together.'], uncertainties: ['Identity unverified.'], questions: ['Which model?'],
    verification: 'Compare with the retained model source.', verification_status: 'PROPOSED_NOT_EXECUTED',
    refs: ['a', 'b'], counter_refs: [], source_bindings: { a: binding('a'), b: binding('b') },
    status: 'HUMAN_REVIEW_REQUIRED', guard_semantic_approval: false }]
  const invalid = projectResult(dto, 200, ref)
  assert.equal(invalid.claims.length, 0)
  assert.equal(invalid.facts.length, 5)
  assert.equal(invalid.aiWarning, 'AI_OUTPUT_NOT_DISPLAYABLE')
  dto.claims[0].refs = ['a']
  assert.equal(projectResult(dto, 200, ref).claims.length, 1)
})

test('stale pointers, cross-task facts and inflated visited counts are rejected', () => {
  const a = fixture()
  a.customer_presentation.tasks[1].observations[0].source_pointer = '/deterministic_diagnosis/buyer_tasks/0/rules/0/observations/0'
  assert.throws(() => projectResult(a, 202, ref), /INVALID_DIAGNOSIS_DELIVERY/)
  const b = fixture()
  b.capture_summary.fetched_pages = 24
  assert.throws(() => projectResult(b, 202, ref), /INVALID_DIAGNOSIS_DELIVERY/)
  assert.throws(() => projectResult(fixture(), 202, 'aref-' + 'd'.repeat(32)), /INVALID_DIAGNOSIS_DELIVERY/)
})

test('transient reads retry the same task within bounds and respect Retry-After', () => {
  assert.equal(readDecision({ status: 202 }).action, 'poll')
  for (const [n, expected] of [2000, 5000, 10000].entries()) {
    const d = readDecision({ status: n === 0 ? 0 : 503, consecutiveFailures: n })
    assert.equal(d.delayMs, expected)
    assert.equal(d.resubmit, false)
    assert.equal(d.keepTask, true)
  }
  assert.equal(readDecision({ status: 503, consecutiveFailures: 3 }).action, 'stop')
  assert.equal(readDecision({ status: 429, retryAfterSeconds: 90 }).delayMs, 90000)
  assert.equal(readDecision({ status: 429, retryAfterSeconds: 900 }).action, 'stop')
  for (const status of [403, 404, 409]) assert.equal(readDecision({ status }).action, 'stop')
})

test('temporary read errors retain same-session facts; denial or expiry clears them', () => {
  const previous = projectResult(fixture(), 202, ref)
  const options = { status: 503, auditRef: ref, now: 1000, sessionExpiresAt: 2000 }
  assert.equal(retainView(previous, options), previous)
  assert.equal(retainView(previous, { ...options, status: 403 }), null)
  assert.equal(retainView(previous, { ...options, sessionExpiresAt: 999 }), null)
  assert.equal(retainView(previous, { ...options, auditRef: 'different' }), null)
})

test('bound partial source facts survive UNKNOWN and cannot invent a rule PASS', () => {
  const dto = fixture('AI_UNAVAILABLE')
  const row = dto.deterministic_diagnosis.buyer_tasks[4].rules[0].observations[0]
  row.citations = [{ snapshot_ref: page.snapshot_ref, url: page.url, fact_role: 'TITLE' }]
  row.seo_signals = { title: { status: 'OBSERVED' } }
  const item = dto.customer_presentation.tasks[4].observations[0]
  item.context_facts = [{ kind: 'TITLE', citation_indexes: [0], is_rule_pass: false,
    text: { zh: '已记录首页标题。', en: 'A home title was retained.' } }]
  item.limit = { kind: 'PARTIAL_EVIDENCE', text: { zh: '已有部分来源观察。', en: 'Partial source observations exist.' } }
  const result = projectPreviewResult(dto, 200, ref)
  assert.equal(result.buyerTasks[4].observations[0].result, 'UNKNOWN')
  assert.equal(result.reportView.tasks[4].contextFacts[0].isRulePass, false)
  assert.equal(result.reportView.tasks[4].contextFacts[0].sources[0].url, page.url)
  assert.equal(result.buyerTasks[4].observations[0].limit.kind, 'PARTIAL_EVIDENCE')
  item.context_facts[0].citation_indexes = [99]
  assert.throws(() => projectPreviewResult(dto, 200, ref), /INVALID_DIAGNOSIS_DELIVERY/)
  item.context_facts[0].citation_indexes = [0]
  item.context_facts[0].kind = 'DESCRIPTION'
  assert.throws(() => projectPreviewResult(dto, 200, ref), /INVALID_DIAGNOSIS_DELIVERY/)
})

test('report groups repeated nav observations while retaining both proof pointers', () => {
  const dto = fixture('AI_UNAVAILABLE')
  const target = { ...page, snapshot_ref: 'page-'+'d'.repeat(64), url: 'https://example.org/products/' }
  dto.page_scope.visited_pages.push(target)
  dto.capture_summary.fetched_pages = 2
  const rows = dto.deterministic_diagnosis.buyer_tasks[0].rules[0].observations
  rows[0].observation.result = 'PASS'
  rows[0].citations = [{ snapshot_ref: page.snapshot_ref }]
  rows[0].homepage = page
  rows[0].target_response = target
  rows.push(structuredClone(rows[0]))
  rows[1].observation.observation_id = 'obs-'+'e'.repeat(64)
  const items = dto.customer_presentation.tasks[0].observations
  items[0].result = 'PASS'
  items.push({ ...items[0], observation_id: rows[1].observation.observation_id,
    source_pointer: '/deterministic_diagnosis/buyer_tasks/0/rules/0/observations/1' })
  const result = projectPreviewResult(dto, 200, ref)
  assert.equal(result.buyerTasks[0].observations.length, 2)
  assert.equal(result.reportView.tasks[0].observations.length, 1)
  assert.equal(result.reportView.tasks[0].observations[0].sourcePointers.length, 2)
  assert.equal(result.reportView.originalObservationCount, 6)
  assert.equal(result.reportView.displayObservationCount, 5)
  assert.equal(result.reportView.candidatePageCount, 60)
  assert.equal(result.reportView.printCandidateUrls, false)
  assert.equal(result.reportView.countsAreNotScoreOrDefectCount, true)
})

function procurementFixture() {
  const d = fixture('AI_UNAVAILABLE')
  const scope = 'ps-'+'d'.repeat(64)
  const row = d.deterministic_diagnosis.buyer_tasks[1].rules[0].observations[0]
  const cite = (fact_role, text, field_index = null) => ({ snapshot_ref: page.snapshot_ref, url: page.url,
    product_scope_ref: scope, fact_role, text, field_index })
  row.citations = [cite('NAME','Grinding wheel W100'), cite('SPEC_LABEL','Size',0), cite('SPEC_VALUE','100 mm',0)]
  const field = { key: 'dimensions', label: 'Size', value: '100 mm', citation_indexes: [1,2],
    normalization: {dimension:'length',value:'100',unit:'mm'} }
  const card = { observation_id: row.observation.observation_id, product_scope_ref: scope,
    name: {text:'Grinding wheel W100',citation_indexes:[0]}, declared_model:null,
    profile:{id:'abrasive_wheel',state:'SOURCE_LABEL_CANDIDATE',title:{zh:'磨轮采购资料候选',en:'Wheel information candidate'},citation_indexes:[0]},
    fields:[field],groups:[{key:'dimensions',title:{zh:'尺寸',en:'Dimensions'},state:'OBSERVED',field_indexes:[0],next_step:{zh:'核对资料',en:'Confirm the document'}},
      {key:'grit',title:{zh:'粒度',en:'Grit'},state:'NOT_OBSERVED_IN_CAPTURE',field_indexes:[],next_step:{zh:'核对其他资料，不判缺失',en:'Check other documents; absence is unproven'}}],
    state:'PARTIAL_SOURCE_INFORMATION',verified_sku:false,engineering_fit:'UNKNOWN',is_rule_pass:false }
  const review = {contract:'vrae.l2-procurement-review.v1',config_version:'1.0.0',configuration_ref:'pcfg-'+'e'.repeat(64),
    review_ref:'prv-'+'f'.repeat(64),pack_ref:'ep-'+'1'.repeat(64),execution_ref:'rx-'+'2'.repeat(64),products:[card],
    coverage:{eligible_products:1,reviewed_products:1,truncated:false},unknown_is_defect:false,formal_human_review:false,native_fact_admission:'NONE',semantic_approval:false}
  Object.assign(d.deterministic_diagnosis,{diagnostic_version:'l2-industrial-1.0.6',expected_pack_ref:review.pack_ref,
    native_execution_ref:review.execution_ref,procurement_review:review})
  d.customer_presentation.procurement_review = review
  return d
}

test('committed procurement cards survive AI failure and preserve source and UNKNOWN work', () => {
  const out = projectPreviewResult(procurementFixture(),200,ref)
  const card = out.reportView.tasks.find(t=>t.task==='UNDERSTAND').procurementCards[0]
  assert.equal(card.name,'Grinding wheel W100')
  assert.equal(card.declaredModel,null)
  assert.equal(card.fields[0].value,'100 mm')
  assert.equal(card.groups[1].state,'NOT_OBSERVED_IN_CAPTURE')
  assert.equal(card.isRulePass,false)
  assert.equal(card.unknownIsDefect,false)
  assert.equal(card.sources[0].url,page.url)
  assert.equal(out.insights.length,0)
})

test('procurement rejects forged values, conversions, groups and product bindings', () => {
  for (const mutate of [
    c=>c.fields[0].value='999 mm', c=>c.fields[0].normalization.value='999',
    c=>c.fields[0].citation_indexes=[0,2], c=>c.product_scope_ref='ps-'+'0'.repeat(64),
    c=>c.is_rule_pass=true, c=>c.groups[1].state='OBSERVED',
    c=>c.fields[0].normalization.unit='m', c=>c.declared_model=c.fields[0]
  ]) {
    const d = procurementFixture()
    mutate(d.deterministic_diagnosis.procurement_review.products[0])
    assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
})

test('new procurement profile requires the exact committed extension', () => {
  const d = procurementFixture()
  d.customer_presentation.procurement_review=structuredClone(d.customer_presentation.procurement_review)
  d.customer_presentation.procurement_review.products[0].fields[0].value='Forged'
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  delete d.customer_presentation.procurement_review
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
})

test('a product with all configured information groups does not erase the report', () => {
  const d = procurementFixture()
  const card = d.deterministic_diagnosis.procurement_review.products[0]
  for (const key of ['model','abrasive','bond','usage','revision','conditions','flow','head','power',
    'voltage','frequency','pressure','temperature','medium','bore','material','connection']) {
    card.groups.push({ ...structuredClone(card.groups[1]), key })
  }
  const out = projectPreviewResult(d,200,ref)
  assert.equal(out.reportView.tasks.find(t=>t.task==='UNDERSTAND').procurementCards[0].groups.length,19)
  assert.equal(out.buyerTasks.length,5)
})

function buyerReviewFixture() {
  const d = procurementFixture()
  const row = d.deterministic_diagnosis.buyer_tasks[0].rules[0].observations[0]
  row.source_page = page
  row.target_response = null
  const step = {rule_id:'DISC-01',observation_id:row.observation.observation_id,result:'UNKNOWN',
    source_page:page,target_response:null,citations:row.citations}
  const path = {journey_ref:'journey-'+'1'.repeat(64),steps:[step],complete:false,terminal_result:'UNKNOWN'}
  d.deterministic_diagnosis.buyer_journey = [path]
  const candidateRules = [['DISC-03'],['INFO-02'],['TRUST-02','TRUST-03'],[],['SEO-02','TECH-01']]
  const review = {contract:'vrae.buyer-review.v1',review_ref:'brv-'+'2'.repeat(64),
    artifact_sha256:d.artifact_sha256,pack_ref:d.deterministic_diagnosis.expected_pack_ref,
    native_execution_ref:d.deterministic_diagnosis.native_execution_ref,state:'AVAILABLE',
    s2_projection_ref:'s2p-'+'3'.repeat(64),industry_ref:'ip-'+'4'.repeat(64),
    native_fact_admission:'NONE',formal_human_review:false,unknown_is_defect:false,
    inquiry_submitted:false,product_context_transfer:'UNKNOWN',technical_material_route:'UNKNOWN',proof_route:'UNKNOWN',
    tasks:taskIds.map((task,i)=>({task,candidates:[],coverage:candidateRules[i].map(rule_id=>({rule_id,total:0,returned:0,truncated:false}))})),
    paths:[{journey_ref:path.journey_ref,steps:[{rule_id:'DISC-01',observation_id:step.observation_id,
      result:'UNKNOWN',source_pointer:'/deterministic_diagnosis/buyer_tasks/0/rules/0/observations/0'}],
      static_path_complete:false,terminal_result:'UNKNOWN',product_context_transfer:'UNKNOWN',inquiry_submitted:false}],
    path_coverage:{total:1,returned:1,truncated:false,whole_site_coverage_known:false}}
  review.tasks[4].candidates.push({observation_id:'obs-'+'5'.repeat(64),rule_id:'TECH-01',rule_version:'s2-static-1.0.0',
    source_version:'s2-source-1.0.0',candidate_result:'PASS',reason:'RETAINED_HTTP_200_RESPONSE',
    title:{zh:'保存的页面响应',en:'Retained response'},text:{zh:'有限证据，仍待复核',en:'Bounded evidence for review'},
    source_snapshot_refs:[page.snapshot_ref],evidence_bindings:[{evidence_ref:'ev-'+'6'.repeat(64),
      snapshot_ref:page.snapshot_ref,locator:'/pages/0/evidence/0',content_sha256:'7'.repeat(64),byte_start:0,byte_end:10}],
    native_fact_admission:'NONE',human_review_required:true})
  review.tasks[4].coverage[1]={rule_id:'TECH-01',total:1,returned:1,truncated:false}
  d.buyer_review=review
  d.customer_presentation.buyer_review=review
  return d
}

test('five-task review retains native unknowns and procurement when AI fails or is pending', () => {
  for (const state of ['AI_UNAVAILABLE','AI_PENDING']) {
    const d=buyerReviewFixture()
    d.state=state
    const out=projectPreviewResult(d,state==='AI_PENDING'?202:200,ref)
    assert.equal(out.buyerTasks[4].observations[0].result,'UNKNOWN')
    assert.equal(out.reportView.tasks[4].reviewCandidates[0].candidateResult,'PASS')
    assert.equal(out.reportView.tasks[4].reviewCandidates[0].isNativeFact,false)
    assert.equal(out.reportView.tasks[1].procurementCards.length,1)
    assert.equal(out.buyerReview.paths[0].staticPathComplete,false)
    assert.equal(out.buyerReview.paths[0].productContextTransfer,'UNKNOWN')
    assert.equal(out.insights.length,0)
  }
})

test('review refuses changed artifact, unvisited candidate evidence and invented completed journeys', () => {
  for (const mutate of [r=>r.artifact_sha256='0'.repeat(64),r=>r.native_fact_admission='PASS',
    r=>r.tasks[4].candidates[0].source_snapshot_refs=['page-'+'0'.repeat(64)],
    r=>r.tasks[4].candidates[0].evidence_bindings=[],r=>r.tasks[4].coverage[1].returned=0,
    r=>r.tasks[4].candidates[0].evidence_bindings[0].byte_end=-1,
    r=>r.paths[0].static_path_complete=true,r=>r.paths[0].steps[0].source_pointer='/deterministic_diagnosis/buyer_tasks/1/rules/0/observations/0',
    r=>r.paths[0].product_context_transfer='CONFIRMED',r=>r.paths[0].inquiry_submitted=true]) {
    const d=buyerReviewFixture()
    mutate(d.buyer_review)
    assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
})

test('unavailable S2 layer retains native paths and five-task facts', () => {
  const d=buyerReviewFixture(), r=d.buyer_review
  r.state='CANDIDATES_UNAVAILABLE'
  r.s2_projection_ref=null; r.industry_ref=null
  r.tasks[4].candidates=[];r.tasks[4].coverage[1]={rule_id:'TECH-01',total:0,returned:0,truncated:false}
  const out=projectPreviewResult(d,200,ref)
  assert.equal(out.buyerReview.state,'CANDIDATES_UNAVAILABLE')
  assert.equal(out.buyerTasks.length,5)
  assert.equal(out.buyerReview.paths.length,1)
  assert.equal(out.reportView.tasks[1].procurementCards.length,1)
  d.customer_presentation.buyer_review=structuredClone(r)
  d.customer_presentation.buyer_review.paths=[]
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
})

test('journey binding accepts canonical key ordering but rejects changed source content', () => {
  const d=buyerReviewFixture()
  const step=d.deterministic_diagnosis.buyer_journey[0].steps[0]
  step.source_page=Object.fromEntries(Object.entries(step.source_page).reverse())
  assert.equal(projectPreviewResult(d,200,ref).buyerReview.paths.length,1)
  step.source_page.url='https://example.org/unvisited'
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
})

test('only a connected captured product route links its procurement card', () => {
  const d=buyerReviewFixture()
  const makePage=(id,url)=>({...page,snapshot_ref:'page-'+id.repeat(64),url})
  const home=makePage('8','https://example.org/'), category=makePage('9','https://example.org/products'),
    contact=makePage('a','https://example.org/contact')
  d.page_scope.visited_pages.push(home,category,contact)
  d.capture_summary.fetched_pages=4
  const add=(ti,ri,rule,id,from,to)=>{
    const row={observation:{rule_id:rule,observation_id:'obs-'+id.repeat(64),result:'PASS'},
      source_page:from,target_response:to,citations:[{snapshot_ref:from.snapshot_ref}]}
    d.deterministic_diagnosis.buyer_tasks[ti].rules[ri]={rule_id:rule,observations:[row]}
    const copy={...d.customer_presentation.tasks[ti].observations[0],rule_id:rule,
      observation_id:row.observation.observation_id,result:'PASS',
      source_pointer:`/deterministic_diagnosis/buyer_tasks/${ti}/rules/${ri}/observations/0`}
    if(ri===0)d.customer_presentation.tasks[ti].observations[0]=copy
    else d.customer_presentation.tasks[ti].observations.push(copy)
    return [row,copy]
  }
  const rows=[add(0,0,'DISC-01','a',home,category),add(0,1,'DISC-02','b',category,page),
    add(3,1,'CTA-02','c',page,contact)]
  const original=d.deterministic_diagnosis.buyer_journey[0]
  original.steps=rows.map(([row])=>({rule_id:row.observation.rule_id,rule_version:'1.0.0',
    observation_id:row.observation.observation_id,result:'PASS',source_page:row.source_page,
    target_response:row.target_response,citations:row.citations}))
  original.complete=true;original.terminal_result='PASS'
  const path=d.buyer_review.paths[0]
  path.steps=rows.map(([row,copy])=>({rule_id:row.observation.rule_id,observation_id:row.observation.observation_id,
    result:'PASS',source_pointer:copy.source_pointer}))
  path.static_path_complete=true;path.terminal_result='PASS'
  const out=projectPreviewResult(d,200,ref)
  assert.equal(out.buyerReview.paths[0].staticPathComplete,true)
  assert.deepEqual(out.buyerReview.paths[0].productScopeRefs,[d.deterministic_diagnosis.procurement_review.products[0].product_scope_ref])
  assert.equal(out.buyerReview.paths[0].inquirySubmitted,false)
  // Changing both copies cannot turn disconnected edges into a continuous path.
  rows[1][0].source_page=home;original.steps[1].source_page=home
  assert.throws(()=>projectPreviewResult(d,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
})

function purchaseTaskFixture() {
  const d=procurementFixture(), card=d.deterministic_diagnosis.procurement_review.products[0]
  d.deterministic_diagnosis.diagnostic_version='l2-industrial-1.0.7'
  d.deterministic_diagnosis.procurement_review.config_version='1.1.0'
  card.purchase_tasks=['APPLICATION_SCREEN','SPECIFICATION_COMPARISON','OPTION_SELECTION'].map((task,i)=>({
    task,title:{zh:'采购任务',en:'Purchase task'},field_indexes:i===1?[0]:[],citation_indexes:i===1?[1,2]:[],
    state:i===1?'SOURCE_INFORMATION_AVAILABLE':'UNKNOWN',decision_readiness:i===1?'SUPPLIER_CONFIRMATION_REQUIRED':'UNKNOWN',
    buyer_requirements_known:false,engineering_fit:'UNKNOWN',relationships_verified:false,is_defect:false,
    next_step:{zh:'先核对已有资料，再请供方澄清。',en:'Check documents, then ask the supplier.'},
    question:{zh:'哪份资料支持该编码解释？',en:'Which document explains this code?'},
    verification:{zh:'核对原字段及供方确认资料。',en:'Compare original fields and supplier confirmation.'}}))
  card.inquiry_preparation={state:'UNKNOWN',path_observation_ids:[],available_input_field_indexes:[0],
    product_context_transfer:'UNKNOWN',inquiry_submitted:false}
  return d
}

test('purchase tasks use existing product fields without asserting fit or relationships',()=>{
  const d=purchaseTaskFixture(), out=projectPreviewResult(d,200,ref)
  assert.equal(out.buyerTasks[1].purchaseTasks[1].state,'SOURCE_INFORMATION_AVAILABLE')
  assert.equal(out.buyerTasks[1].purchaseTasks[1].relationshipsVerified,false)
  assert.equal(out.buyerTasks[3].inquiryPreparation[0].inquirySubmitted,false)
  for(const change of [c=>c.purchase_tasks[0].state='SOURCE_INFORMATION_AVAILABLE',
    c=>c.purchase_tasks[1].field_indexes=[],c=>c.inquiry_preparation.product_context_transfer='CONFIRMED']) {
    const forged=purchaseTaskFixture();change(forged.deterministic_diagnosis.procurement_review.products[0])
    assert.throws(()=>projectPreviewResult(forged,200,ref),/INVALID_DIAGNOSIS_DELIVERY/)
  }
})

test('successful zero-recommendation analysis retains facts without a false AI failure',()=>{
  const d=purchaseTaskFixture()
  d.state='DIAGNOSED';d.diagnosis_complete=true;d.analysis_outcome='COMPLETED_NO_RECOMMENDATIONS'
  d.model={state:'AI_CANDIDATES_FOR_HUMAN_REVIEW',reason:'NO_SUPPORTED_OPPORTUNITIES',verification_realm:'REAL_PROVIDER',real_model_calls:1,
    usage:{usage_origin:'PROVIDER_REPORTED',prompt_version:'qwen-purchase-clarification-1.5.0'}}
  const out=projectPreviewResult(d,200,ref)
  assert.equal(out.state,'diagnosed');assert.equal(out.aiWarning,null)
  assert.equal(out.insights.length,0);assert.equal(out.buyerTasks[1].purchaseTasks.length,3)
  d.model.verification_realm='PROTOCOL_FAKE_NOT_REAL_API';d.model.real_model_calls=0
  assert.equal(projectPreviewResult(d,200,ref).aiWarning,'AI_OUTPUT_NOT_DISPLAYABLE')
})

test('purchase AI cannot publish a free-form mapping action despite valid product references',()=>{
  const d=purchaseTaskFixture(), t=d.deterministic_diagnosis.procurement_review.products[0].purchase_tasks[1]
  d.state='DIAGNOSED';d.diagnosis_complete=true;d.analysis_outcome='COMPLETED'
  d.model={state:'AI_CANDIDATES_FOR_HUMAN_REVIEW',verification_realm:'REAL_PROVIDER',real_model_calls:1,
    usage:{usage_origin:'PROVIDER_REPORTED',prompt_version:'qwen-purchase-clarification-1.5.0'}}
  const c={task:'UNDERSTAND',purchase_task:'SPECIFICATION_COMPARISON',opportunity_kind:'CLARIFICATION',
    refs:['cf-label','cf-spec'],counter_refs:[],status:'HUMAN_REVIEW_REQUIRED',guard_semantic_approval:false,
    explanation:'100 mm may need comparison with supplier-confirmed drawings.',rebuild:[t.next_step.zh],
    questions:[t.question.zh],uncertainties:['其他资料尚未核对。'],verification:t.verification.zh,
    verification_status:'PROPOSED_NOT_EXECUTED',source_bindings:{'cf-label':{type:'GUARD_LITERAL',fact:{rule_id:'INFO-01',
      source:{citation:{...d.deterministic_diagnosis.buyer_tasks[1].rules[0].observations[0].citations[1]}}}},'cf-spec':{type:'GUARD_LITERAL',fact:{rule_id:'INFO-01',
      source:{citation:{...d.deterministic_diagnosis.buyer_tasks[1].rules[0].observations[0].citations[2]}}}}}}
  d.claims=[c]
  assert.equal(projectPreviewResult(d,200,ref).insights[0].opportunityKind,'CLARIFICATION')
  c.rebuild=['Publish all combinations of the separately listed options.']
  const out=projectPreviewResult(d,200,ref)
  assert.equal(out.insights.length,0);assert.equal(out.buyerTasks[1].procurementCards.length,1)
})

test('placeholder text remains visible without becoming actionable purchasing information',()=>{
  const d=purchaseTaskFixture(), card=d.deterministic_diagnosis.procurement_review.products[0]
  card.fields[0].value='N/A';card.fields[0].normalization=null
  d.deterministic_diagnosis.buyer_tasks[1].rules[0].observations[0].citations[2].text='N/A'
  const t=card.purchase_tasks[1]
  t.field_indexes=[];t.citation_indexes=[];t.state='UNKNOWN';t.decision_readiness='UNKNOWN'
  card.inquiry_preparation.available_input_field_indexes=[]
  const out=projectPreviewResult(d,200,ref)
  assert.equal(out.buyerTasks[1].procurementCards[0].fields[0].value,'N/A')
  assert.equal(out.buyerTasks[1].purchaseTasks[1].state,'UNKNOWN')
  assert.deepEqual(out.buyerTasks[3].inquiryPreparation[0].availableInputFieldIndexes,[])
})
