// Pure reference for the trusted VF BFF; no HTTP, credentials, storage or UI.
// Keep existing mTLS, source-SHA, media, no-store, session and CSRF checks first.
const tasks = ['DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL']
const states = new Set(['CAPTURE_PENDING', 'AI_PENDING', 'CAPTURE_FAILED', 'DIAGNOSED', 'AI_UNAVAILABLE'])
const outcomes = new Set(['PASS', 'FAIL_WITH_EVIDENCE', 'UNKNOWN', 'ACCESS_BLOCKED', 'NOT_APPLICABLE'])
const object = value => value && typeof value === 'object' && !Array.isArray(value)
const list = value => Array.isArray(value) ? value : []
const fail = () => { throw new Error('INVALID_DIAGNOSIS_DELIVERY') }
const text = value => typeof value === 'string' && value.trim().length > 0 && value.length <= 600
const sourceUrl = value => {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash
  } catch { return false }
}

function pointer(body, path) {
  if (typeof path !== 'string' || !/^\/deterministic_diagnosis\/buyer_tasks\/\d+\/rules\/\d+\/observations\/\d+$/.test(path)) fail()
  return path.slice(1).split('/').reduce((value, key) => {
    if (!object(value) && !Array.isArray(value) || !Object.hasOwn(value, key)) fail()
    return value[key]
  }, body)
}

export function projectResult(body, status, auditRef, language = 'zh') {
  if (!object(body) || !/^aref-[0-9a-f]{32}$/.test(auditRef) || body.audit_ref !== auditRef ||
      body.contract !== 'vrae.automatic-diagnosis.v1' || !states.has(body.state) ||
      body.formal_human_review !== false || body.publication !== 'UNPUBLISHED' ||
      !['zh', 'en'].includes(language) || ![200, 202].includes(status) ||
      (status === 202) !== ['CAPTURE_PENDING', 'AI_PENDING'].includes(body.state) ||
      body.diagnosis_complete !== (body.state === 'DIAGNOSED')) fail()
  const p = body.customer_presentation
  if (!object(p) || p.contract !== 'vrae.diagnosis-presentation.v1' || p.is_report !== false ||
      p.formal_human_review !== false || p.artifact_sha256 !== (body.artifact_sha256 ?? null) ||
      p.rules_available !== Boolean(body.deterministic_diagnosis)) fail()
  const visited = list(body.page_scope?.visited_pages)
  if (visited.some(page => !sourceUrl(page.url) || page.capture_status !== 'FETCHED' || page.http_status !== 200)) fail()
  const pages = new Map(visited.map(page => [page.snapshot_ref, page]))
  const groups = list(p.tasks)
  if (p.rules_available && (groups.length !== 5 || groups.some((g, i) => g.task !== tasks[i]))) fail()
  if (!p.rules_available && groups.length) fail()
  const facts = groups.map((group, ti) => ({
    task: group.task, title: group.title[language],
    observations: list(group.observations).map(item => {
      if (!item.source_pointer?.startsWith(`/deterministic_diagnosis/buyer_tasks/${ti}/`)) fail()
      const row = pointer(body, item.source_pointer)
      if (row.observation?.observation_id !== item.observation_id ||
          row.observation?.rule_id !== item.rule_id || row.observation?.result !== item.result ||
          !outcomes.has(item.result) || !text(item.text?.[language])) fail()
      const sources = [...new Set(list(row.citations).map(c => c.snapshot_ref))]
        .filter(ref => pages.has(ref)).map(ref => pages.get(ref))
      // A factual PASS/FAIL must keep an actually visited source, never an inventory URL.
      if (['PASS', 'FAIL_WITH_EVIDENCE'].includes(item.result) && !sources.length) fail()
      return { rule: item.rule_id, observationId: item.observation_id, result: item.result,
        text: item.text[language], statusText: item.status_text[language], sources,
        sourcePointer: item.source_pointer }
    }),
  }))
  const claims = []
  let aiWarning = null
  const model = body.model
  const genuine = body.state === 'DIAGNOSED' && model?.verification_realm === 'REAL_PROVIDER' &&
    model.real_model_calls === 1 && model.state === 'AI_CANDIDATES_FOR_HUMAN_REVIEW' &&
    model.usage?.usage_origin === 'PROVIDER_REPORTED'
  if (body.state === 'DIAGNOSED' && !genuine) aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
  if (genuine) for (const claim of list(body.claims)) {
    if (!object(claim)) {
      aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
      continue
    }
    const bindings = claim.source_bindings
    const refs = [...list(claim.refs), ...list(claim.counter_refs)]
    const sources = refs.map(ref => bindings?.[ref]).filter(binding => {
      const c = binding?.fact?.source?.citation
      return binding?.type === 'GUARD_LITERAL' && pages.has(c?.snapshot_ref) &&
        pages.get(c.snapshot_ref).url === c.url
    }).map(binding => pages.get(binding.fact.source.citation.snapshot_ref))
    const modern = model.usage.prompt_version === 'qwen-evidence-buyer-1.2.1'
    if (!tasks.includes(claim.task) || claim.status !== 'HUMAN_REVIEW_REQUIRED' ||
        claim.guard_semantic_approval !== false || !text(claim.explanation) || !sources.length ||
        !list(claim.rebuild).length || !claim.rebuild.every(text) ||
        refs.some(ref => !object(bindings) || !Object.hasOwn(bindings, ref)) ||
        modern && (!text(claim.verification) || claim.verification_status !== 'PROPOSED_NOT_EXECUTED')) {
      aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
      continue // AI failure never erases established rule facts.
    }
    claims.push({ task: claim.task, explanation: claim.explanation, rebuild: [...claim.rebuild],
      uncertainties: list(claim.uncertainties).filter(text), questions: list(claim.questions).filter(text),
      verification: text(claim.verification) ? claim.verification : null, verificationIsPlan: true,
      sources: [...new Map(sources.map(p => [p.snapshot_ref, p])).values()], humanReviewRequired: true })
  }
  if (genuine && !claims.length) aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
  const summary = body.capture_summary
  if (summary && (summary.fetched_pages !== visited.length || summary.unvisited_is_defect !== false)) fail()
  return { auditRef, state: body.state, analysisOutcome: body.analysis_outcome,
    analysisText: p.analysis_text[language], facts, claims, aiWarning,
    captureSummary: summary ?? null,
    pageScope: { visited, failed: list(body.page_scope?.failed_attempt_records),
      candidates: list(body.page_scope?.unvisited_candidates),
      candidatesAreDefects: false, candidatesInitiallyCollapsed: true }, formalHumanReview: false }
}

export function readDecision({ status, consecutiveFailures = 0, elapsedMs = 0, retryAfterSeconds }) {
  const stop = reason => ({ action: 'stop', reason, keepTask: true, resubmit: false })
  if (!Number.isInteger(consecutiveFailures) || consecutiveFailures < 0 || !Number.isFinite(elapsedMs) || elapsedMs < 0) return stop('INVALID_RETRY_STATE')
  if (status === 200) return stop('RESULT_AVAILABLE')
  if (status === 202) return { action: 'poll', delayMs: 10000, keepTask: true, resubmit: false }
  if ([403, 404, 409].includes(status)) return stop('ACCESS_OR_INTENT_DENIED')
  if (![0, 429, 503].includes(status)) return stop('QUERY_UNAVAILABLE')
  if (consecutiveFailures >= 3 || elapsedMs >= 120000) return stop('QUERY_UNAVAILABLE')
  const delayMs = status === 429
    ? (Number.isInteger(retryAfterSeconds) && retryAfterSeconds >= 1 && retryAfterSeconds <= 900
      ? retryAfterSeconds : 60) * 1000
    : [2000, 5000, 10000][consecutiveFailures]
  if (delayMs > 120000 - elapsedMs) return stop('QUERY_UNAVAILABLE')
  return { action: 'retry', delayMs, keepTask: true, resubmit: false }
}

export function retainView(previous, { status, auditRef, now, sessionExpiresAt }) {
  if (!previous || previous.auditRef !== auditRef || !Number.isFinite(now) ||
      !Number.isFinite(sessionExpiresAt) || sessionExpiresAt <= now || [403, 404, 409].includes(status)) return null
  return [0, 429, 503].includes(status) ? previous : null
}
