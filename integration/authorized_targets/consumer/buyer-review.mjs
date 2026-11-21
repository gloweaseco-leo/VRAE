// Derived review layer. Candidate PASS never changes a native observation.
const tasks = ['DISCOVER','UNDERSTAND','TRUST','INQUIRE','SEARCH_TECHNICAL']
const rules = [['DISC-03'],['INFO-02'],['TRUST-02','TRUST-03'],[],['SEO-02','TECH-01']]
const fail = () => { throw new Error('INVALID_DIAGNOSIS_DELIVERY') }
const text = v => typeof v === 'string' && v.length > 0 && v.length <= 600
const ordered = v => Array.isArray(v) ? v.map(ordered) : v && typeof v === 'object'
  ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])) : v
const equal = (a,b) => JSON.stringify(ordered(a)) === JSON.stringify(ordered(b))

export function buyerReview(body, pages, pointer, language) {
  const review = body.buyer_review
  if (review === undefined && body.customer_presentation.buyer_review === undefined) return null
  const d = body.deterministic_diagnosis
  if (!review || JSON.stringify(review) !== JSON.stringify(body.customer_presentation.buyer_review) ||
      !['l2-industrial-1.0.6','l2-industrial-1.0.7'].includes(d?.diagnostic_version) || review.contract !== 'vrae.buyer-review.v1' ||
      review.artifact_sha256 !== body.artifact_sha256 || review.pack_ref !== d.expected_pack_ref ||
      review.native_execution_ref !== d.native_execution_ref || !/^brv-[0-9a-f]{64}$/.test(review.review_ref) ||
      review.native_fact_admission !== 'NONE' || review.formal_human_review !== false ||
      review.unknown_is_defect !== false || review.inquiry_submitted !== false ||
      review.product_context_transfer !== 'UNKNOWN' || review.technical_material_route !== 'UNKNOWN' ||
      review.proof_route !== 'UNKNOWN' || !['AVAILABLE','CANDIDATES_UNAVAILABLE'].includes(review.state) ||
      (review.state === 'AVAILABLE' && (!/^s2p-[0-9a-f]{64}$/.test(review.s2_projection_ref) ||
        !/^ip-[0-9a-f]{64}$/.test(review.industry_ref))) ||
      (review.state === 'CANDIDATES_UNAVAILABLE' && (review.s2_projection_ref !== null || review.industry_ref !== null)) ||
      !Array.isArray(review.tasks) || review.tasks.length !== 5) fail()
  const allPages = new Map([...body.page_scope.failed_attempt_records,...pages.values()]
    .filter(p=>p.snapshot_ref).map(p=>[p.snapshot_ref,p]))
  const candidates = review.tasks.map((group, ti) => {
    if (group.task !== tasks[ti] || !Array.isArray(group.candidates) ||
        !Array.isArray(group.coverage) || group.coverage.length !== rules[ti].length) fail()
    const used = new Set()
    const items = group.candidates.map(c => {
      if (!rules[ti].includes(c.rule_id) || !/^obs-[0-9a-f]{64}$/.test(c.observation_id) ||
          used.has(c.observation_id) || !text(c.rule_version) || !text(c.source_version) || !text(c.reason) ||
          !['PASS','UNKNOWN','ACCESS_BLOCKED','NOT_APPLICABLE'].includes(c.candidate_result) ||
          c.native_fact_admission !== 'NONE' || c.human_review_required !== true ||
          !text(c.title?.[language]) || !text(c.text?.[language]) ||
          !Array.isArray(c.source_snapshot_refs) || !Array.isArray(c.evidence_bindings) ||
          new Set(c.source_snapshot_refs).size !== c.source_snapshot_refs.length ||
          c.source_snapshot_refs.some(ref=>!allPages.has(ref))) fail()
      used.add(c.observation_id)
      for (const b of c.evidence_bindings) {
        if (!/^ev-[0-9a-f]{64}$/.test(b.evidence_ref) || !/^[0-9a-f]{64}$/.test(b.content_sha256) ||
            !Number.isInteger(b.byte_start) || !Number.isInteger(b.byte_end) || b.byte_start < 0 ||
            b.byte_end <= b.byte_start || b.byte_end > 131072 ||
            !text(b.locator) || !pages.has(b.snapshot_ref) || !c.source_snapshot_refs.includes(b.snapshot_ref)) fail()
      }
      if (c.candidate_result === 'PASS' && (!c.evidence_bindings.length || !c.source_snapshot_refs.length ||
          c.source_snapshot_refs.some(ref=>!pages.has(ref)))) fail()
      return { observationId:c.observation_id, rule:c.rule_id, candidateResult:c.candidate_result,
        title:c.title[language], text:c.text[language], reason:c.reason,
        sourceVersion:c.source_version, ruleVersion:c.rule_version,
        evidenceBindings:c.evidence_bindings, sources:c.source_snapshot_refs.map(ref=>allPages.get(ref)),
        humanReviewRequired:true, isNativeFact:false }
    })
    for (let i=0;i<rules[ti].length;i++) {
      const coverage=group.coverage[i]
      if (coverage.rule_id !== rules[ti][i] || !Number.isInteger(coverage.total) || coverage.total < 0 ||
          coverage.returned !== items.filter(c=>c.rule === coverage.rule_id).length ||
          coverage.returned !== Math.min(coverage.total,16) ||
          coverage.truncated !== (coverage.total>coverage.returned) ||
          (review.state === 'CANDIDATES_UNAVAILABLE' && coverage.total !== 0)) fail()
    }
    return { task:group.task, candidates:items, coverage:group.coverage }
  })
  const original = d.buyer_journey
  if (!Array.isArray(original) || !Array.isArray(review.paths) || review.paths.length !== Math.min(original.length,16) ||
      review.path_coverage?.total !== original.length || review.path_coverage.returned !== review.paths.length ||
      review.path_coverage.truncated !== (original.length>review.paths.length) ||
      review.path_coverage.whole_site_coverage_known !== false) fail()
  const paths = review.paths.map((path, i) => {
    const source = original[i]
    if (path.journey_ref !== source.journey_ref || path.static_path_complete !== source.complete ||
        path.terminal_result !== source.terminal_result || path.product_context_transfer !== 'UNKNOWN' ||
        path.inquiry_submitted !== false || !Array.isArray(path.steps) || path.steps.length !== source.steps.length) fail()
    const steps = path.steps.map((step, si) => {
      const held = source.steps[si]
      if (step.rule_id !== held.rule_id || step.observation_id !== held.observation_id || step.result !== held.result ||
          !step.source_pointer?.startsWith('/deterministic_diagnosis/buyer_tasks/')) fail()
      const row = pointer(body,step.source_pointer)
      if (row.observation?.observation_id !== held.observation_id || row.observation.rule_id !== held.rule_id ||
          row.observation.result !== held.result || !equal(row.citations,held.citations) ||
          !equal(row.source_page ?? row.homepage,held.source_page) ||
          !equal(row.target_response,held.target_response)) fail()
      const from=row.source_page ?? row.homepage, to=row.target_response
      if (si && (path.steps[si-1].result !== 'PASS' || source.steps[si-1].target_response?.snapshot_ref !== from?.snapshot_ref)) fail()
      const endpoint = p => p && allPages.get(p.snapshot_ref)?.url === p.url ? allPages.get(p.snapshot_ref) : null
      if (held.result === 'PASS' && (!pages.has(from?.snapshot_ref) || !pages.has(to?.snapshot_ref))) fail()
      return {rule:step.rule_id,observationId:step.observation_id,result:step.result,
        sourcePointer:step.source_pointer,from:endpoint(from),to:endpoint(to)}
    })
    if (path.static_path_complete && (steps.length !== 3 || steps.some(s=>s.result !== 'PASS') ||
        JSON.stringify(steps.map(s=>s.rule)) !== JSON.stringify(['DISC-01','DISC-02','CTA-02']))) fail()
    return {journeyRef:path.journey_ref,steps,staticPathComplete:path.static_path_complete,
      terminalResult:path.terminal_result,productContextTransfer:'UNKNOWN',inquirySubmitted:false}
  })
  return {state:review.state,reviewRef:review.review_ref,s2ProjectionRef:review.s2_projection_ref,
    tasks:candidates,paths,pathCoverage:review.path_coverage,technicalMaterialRoute:'UNKNOWN',proofRoute:'UNKNOWN'}
}
