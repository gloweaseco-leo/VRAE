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
