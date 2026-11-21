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
