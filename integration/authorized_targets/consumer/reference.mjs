// Pure reference for the trusted VF BFF; no HTTP, credentials, storage or UI.
// Keep existing mTLS, source-SHA, media, no-store, session and CSRF checks first.
import { procurementCards } from './procurement.mjs'
import { buyerReview } from './buyer-review.mjs'
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

function contextFacts(item, row, pages, language) {
  return list(item.context_facts).map(fact => {
    const indexes = list(fact.citation_indexes)
    if (fact.is_rule_pass !== false || !text(fact.text?.[language]) || !indexes.length ||
        new Set(indexes).size !== indexes.length || indexes.some(i => !Number.isInteger(i) || i < 0 || i >= list(row.citations).length)) fail()
    const citations = indexes.map(i => row.citations[i])
    let bound = false
    if (row.observation.rule_id === 'TRUST-01') bound = list(row.context_facts).some(f =>
      f.kind === fact.kind && JSON.stringify(f.citation_indexes) === JSON.stringify(indexes))
    if (row.observation.rule_id === 'CTA-01') bound = fact.kind === 'STATIC_CONTACT_LINK' && row.static_href_presence === 'OBSERVED'
    if (row.observation.rule_id === 'SEO-01') bound = ['TITLE', 'DESCRIPTION', 'CANONICAL'].includes(fact.kind) &&
      row.seo_signals?.[fact.kind.toLowerCase()]?.status === 'OBSERVED' && citations.every(c => c.fact_role === fact.kind)
    if (row.observation.rule_id === 'INFO-01') {
      bound = fact.kind === 'PRODUCT_NAME' && citations.length === 1 && citations[0].fact_role === 'NAME' &&
        /^ps-[0-9a-f]{64}$/.test(citations[0].product_scope_ref) ||
        fact.kind === 'PRODUCT_FIELD' && citations.length === 2 && citations[0].fact_role === 'SPEC_LABEL' &&
        citations[1].fact_role === 'SPEC_VALUE' && citations[0].field_index === citations[1].field_index &&
        /^ps-[0-9a-f]{64}$/.test(citations[0].product_scope_ref) && citations[0].product_scope_ref === citations[1].product_scope_ref
    }
    if (!bound || citations.some(c => !pages.has(c.snapshot_ref) || pages.get(c.snapshot_ref).url !== c.url)) fail()
    return { kind: fact.kind, text: fact.text[language], isRulePass: false,
      productScopeRef: citations[0].product_scope_ref ?? null,
      citationIndexes: indexes, sourcePointer: item.source_pointer,
      sources: [...new Map(citations.map(c => [c.snapshot_ref, pages.get(c.snapshot_ref)])).values()] }
  })
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
      const from = row.source_page ?? row.homepage
      const to = row.target_response
      const endpoint = meta => meta && pages.has(meta.snapshot_ref) && pages.get(meta.snapshot_ref).url === meta.url
        ? pages.get(meta.snapshot_ref) : null
      const limit = item.limit
      if (limit && (item.result !== 'UNKNOWN' || !text(limit.text?.[language]) ||
          !['NOT_IMPLEMENTED', 'APPLICABILITY_UNRESOLVED', 'HUMAN_REVIEW_REQUIRED', 'PARTIAL_EVIDENCE',
            'VISIBILITY_OR_DELIVERY_UNVERIFIED', 'SOURCE_UNAVAILABLE', 'PARSER_UNSUPPORTED'].includes(limit.kind))) fail()
      return { rule: item.rule_id, observationId: item.observation_id, result: item.result,
        text: item.text[language], statusText: item.status_text[language], sources,
        reason: typeof row.reason === 'string' ? row.reason : null,
        contextFacts: contextFacts(item, row, pages, language), path: { from: endpoint(from), to: endpoint(to) },
        limit: limit ? { kind: limit.kind, text: limit.text[language] } : null,
        sourcePointer: item.source_pointer }
    }),
  }))
  const procurement = procurementCards(body, pages, pointer, language)
  const review = buyerReview(body, pages, pointer, language)
  if (review) for (const path of review.paths) {
    const productPages = new Set(path.steps.flatMap(step => step.rule === 'DISC-02'
      ? [step.to?.snapshot_ref] : step.rule === 'CTA-02' ? [step.from?.snapshot_ref] : []))
    path.productScopeRefs = procurement.filter(card => card.sources.some(p=>productPages.has(p.snapshot_ref)))
      .map(card=>card.productScopeRef)
  }
  for (const group of facts) {
    group.procurementCards = group.task === 'UNDERSTAND' ? procurement : []
    group.procurementCoverage = group.task === 'UNDERSTAND' ? p.procurement_review?.coverage ?? null : null
    const reviewTask = review?.tasks.find(t=>t.task === group.task)
    group.reviewCandidates = reviewTask?.candidates ?? []
    group.reviewCoverage = reviewTask?.coverage ?? []
    group.recordedFacts=group.observations.flatMap(o=>o.contextFacts)
    group.purchaseTasks=group.task==='UNDERSTAND'?procurement.flatMap(c=>c.purchaseTasks.map(t=>({...t,productScopeRef:c.productScopeRef,sourcePointer:c.sourcePointer}))):[]
    group.inquiryPreparation=group.task==='INQUIRE'?procurement.filter(c=>c.inquiryPreparation).map(c=>({
      ...c.inquiryPreparation,productScopeRef:c.productScopeRef,sourcePointer:c.sourcePointer})):[]
  }
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
    const modern = ['qwen-evidence-buyer-1.2.1', 'qwen-evidence-buyer-1.3.0', 'qwen-evidence-buyer-1.4.0', 'qwen-purchase-clarification-1.5.0'].includes(model.usage.prompt_version)
    const productRefs = refs.map(ref => bindings?.[ref]).filter(b => b?.type === 'GUARD_LITERAL' && b.fact?.rule_id === 'INFO-01')
    const productScopes = productRefs.map(b => b.fact.source?.citation?.product_scope_ref)
    const badProductScope = ['qwen-evidence-buyer-1.3.0', 'qwen-evidence-buyer-1.4.0', 'qwen-purchase-clarification-1.5.0'].includes(model.usage.prompt_version) &&
      (productScopes.some(scope => typeof scope !== 'string' || !/^ps-[0-9a-f]{64}$/.test(scope)) ||
       new Set(productScopes).size > 1)
    let purchase = null
    if (model.usage.prompt_version === 'qwen-purchase-clarification-1.5.0') {
      const card=procurement.find(c=>c.productScopeRef===productScopes[0])
      purchase=card?.purchaseTasks.find(t=>t.task===claim.purchase_task)
      if (!purchase || purchase.state!=='SOURCE_INFORMATION_AVAILABLE' || claim.opportunity_kind!=='CLARIFICATION' ||
          JSON.stringify(claim.rebuild)!==JSON.stringify([purchase.nextStep]) ||
          JSON.stringify(claim.questions)!==JSON.stringify([purchase.question]) || claim.verification!==purchase.verification) {
        aiWarning='AI_OUTPUT_NOT_DISPLAYABLE';continue
      }
      const row=pointer(body,card.sourcePointer)
      const signature=c=>JSON.stringify([c.snapshot_ref,c.evidence_ref,c.field_index,c.fact_role,c.product_scope_ref,
        c.text?.normalize('NFKC').trim().replace(/\s+/g,' ')])
      const cited=new Set(productRefs.map(b=>signature(b.fact.source.citation)))
      const supported=new Set(purchase.fieldIndexes.filter(i=>card.fields[i].citationIndexes.every(j=>cited.has(signature(row.citations[j]))))
        .map(i=>card.fields[i].key))
      if (supported.size < (purchase.task==='OPTION_SELECTION'?2:1)) { aiWarning='AI_OUTPUT_NOT_DISPLAYABLE';continue }
    }
    if (!tasks.includes(claim.task) || claim.status !== 'HUMAN_REVIEW_REQUIRED' ||
        claim.guard_semantic_approval !== false || !text(claim.explanation) || !sources.length || badProductScope ||
        !list(claim.rebuild).length || !claim.rebuild.every(text) ||
        refs.some(ref => !object(bindings) || !Object.hasOwn(bindings, ref)) ||
        modern && (!text(claim.verification) || claim.verification_status !== 'PROPOSED_NOT_EXECUTED')) {
      aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
      continue // AI failure never erases established rule facts.
    }
    claims.push({ task: claim.task, explanation: claim.explanation, rebuild: [...claim.rebuild],
      purchaseTask:claim.purchase_task??null, opportunityKind:claim.opportunity_kind??null,
      uncertainties: list(claim.uncertainties).filter(text), questions: list(claim.questions).filter(text),
      verification: text(claim.verification) ? claim.verification : null, verificationIsPlan: true,
      sources: [...new Map(sources.map(p => [p.snapshot_ref, p])).values()], humanReviewRequired: true })
  }
  if (model?.usage?.prompt_version === 'qwen-purchase-clarification-1.5.0') {
    const rank={SPECIFICATION_COMPARISON:0,OPTION_SELECTION:1,APPLICATION_SCREEN:2}
    claims.sort((a,b)=>rank[a.purchaseTask]-rank[b.purchaseTask])
  }
  if (genuine && !claims.length && !(model.usage.prompt_version === 'qwen-purchase-clarification-1.5.0' &&
      body.deterministic_diagnosis?.diagnostic_version==='l2-industrial-1.0.7' && model.reason==='NO_SUPPORTED_OPPORTUNITIES' &&
      !list(body.claims).length && body.analysis_outcome === 'COMPLETED_NO_RECOMMENDATIONS')) aiWarning = 'AI_OUTPUT_NOT_DISPLAYABLE'
  const summary = body.capture_summary
  if (summary && (summary.fetched_pages !== visited.length || summary.unvisited_is_defect !== false)) fail()
  return { auditRef, state: body.state, analysisOutcome: body.analysis_outcome,
    buyerReview: review,
    analysisText: p.analysis_text[language], facts, claims, aiWarning,
    modelFailureStage: typeof model?.failure_stage === 'string' ? model.failure_stage : null,
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
