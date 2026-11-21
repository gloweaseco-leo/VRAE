// A committed source-review extension, never a rule PASS or product-fit verdict.
const list = v => Array.isArray(v) ? v : []
const literal = v => typeof v === 'string' ? v.normalize('NFKC').trim().replace(/\s+/g, ' ') : null
const text = v => typeof v === 'string' && v.length > 0 && v.length <= 600
const fail = () => { throw new Error('INVALID_DIAGNOSIS_DELIVERY') }
const placeholders = new Set(['n/a','na','unknown','not specified','tbd','-','—','on request'])
const informative = value => !placeholders.has(value.trim().replace(/\s+/g,' ').toLowerCase())

// Exact decimal check for the fixed v1 source-unit contract; no float rounding.
function scalar(raw, result, key) {
  const units = { mm: ['length', '1', 'mm'], m: ['head', '1', 'm'],
    bar: ['pressure', '1', 'bar'], MPa: ['pressure', '10', 'bar'], kPa: ['pressure', '0.01', 'bar'],
    'm3/h': ['flow', '1', 'm3/h'], 'L/min': ['flow', '0.06', 'm3/h'], kW: ['power', '1', 'kW'],
    V: ['voltage', '1', 'V'], Hz: ['frequency', '1', 'Hz'], degC: ['temperature', '1', 'degC'] }
  const expected = { dimensions: 'length', bore: 'length', flow: 'flow', head: 'head', power: 'power',
    voltage: 'voltage', frequency: 'frequency', pressure: 'pressure', temperature: 'temperature' }
  const match = /^([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z0-9/]+)$/.exec(raw)
  if (!match || match[1].length > 20 || !units[match[2]]) return false
  const [dimension, factor, unit] = units[match[2]]
  if (expected[key] !== dimension || result.dimension !== dimension || result.unit !== unit ||
      typeof result.value !== 'string' || result.value.length > 40 || !/^[0-9]+(?:\.[0-9]+)?$/.test(result.value)) return false
  const decimal = s => { const [a, b = ''] = s.split('.'); return [BigInt(a+b), 10n**BigInt(b.length)] }
  const [a, ad] = decimal(match[1]), [f, fd] = decimal(factor), [b, bd] = decimal(result.value)
  return a*f*bd === b*fd*ad
}

export function procurementCards(body, pages, pointer, language) {
  const review = body.customer_presentation.procurement_review
  const diagnosis = body.deterministic_diagnosis
  if (!review) {
    if (['l2-industrial-1.0.6','l2-industrial-1.0.7'].includes(diagnosis?.diagnostic_version)) fail()
    return []
  }
  const modern = diagnosis?.diagnostic_version === 'l2-industrial-1.0.7'
  if (!['l2-industrial-1.0.6','l2-industrial-1.0.7'].includes(diagnosis?.diagnostic_version) ||
      JSON.stringify(review) !== JSON.stringify(diagnosis.procurement_review) ||
      review.contract !== 'vrae.l2-procurement-review.v1' || review.config_version !== (modern?'1.1.0':'1.0.0') ||
      !/^pcfg-[0-9a-f]{64}$/.test(review.configuration_ref) || !/^prv-[0-9a-f]{64}$/.test(review.review_ref) ||
      review.pack_ref !== diagnosis.expected_pack_ref || review.execution_ref !== diagnosis.native_execution_ref ||
      review.native_fact_admission !== 'NONE' || review.unknown_is_defect !== false ||
      review.formal_human_review !== false || review.semantic_approval !== false ||
      !Array.isArray(review.products) || review.products.length > 8 ||
      review.coverage?.reviewed_products !== review.products.length ||
      !Number.isInteger(review.coverage?.eligible_products) || review.coverage.eligible_products < review.products.length ||
      review.coverage.truncated !== (review.coverage.eligible_products > review.products.length)) fail()
  const items = list(body.customer_presentation.tasks).flatMap(t => list(t.observations))
  if (review.coverage.eligible_products > items.filter(i => i.rule_id === 'INFO-01').length) fail()
  const used = new Set()
  return review.products.map(card => {
    const item = items.find(o => o.rule_id === 'INFO-01' && o.observation_id === card.observation_id)
    if (!item || !/^ps-[0-9a-f]{64}$/.test(card.product_scope_ref) || used.has(card.product_scope_ref) ||
        card.is_rule_pass !== false || card.verified_sku !== false || card.engineering_fit !== 'UNKNOWN') fail()
    used.add(card.product_scope_ref)
    const row = pointer(body, item.source_pointer)
    const citations = list(row.citations)
    const bound = indexes => {
      if (!Array.isArray(indexes) || !indexes.length || new Set(indexes).size !== indexes.length ||
          indexes.some(i => !Number.isInteger(i) || i < 0 || i >= citations.length)) fail()
      const refs = indexes.map(i => citations[i])
      if (refs.some(c => c.product_scope_ref !== card.product_scope_ref || !pages.has(c.snapshot_ref) ||
          pages.get(c.snapshot_ref).url !== c.url)) fail()
      return refs
    }
    const name = bound(card.name?.citation_indexes)
    if (name.length !== 1 || name[0].fact_role !== 'NAME' || !text(card.name.text) ||
        card.name.text !== literal(name[0].text)) fail()
    if (!Array.isArray(card.fields) || card.fields.length > 64) fail()
    const fields = card.fields.map(field => {
      const refs = bound(field.citation_indexes)
      if (refs.length !== 2 || refs[0].fact_role !== 'SPEC_LABEL' || refs[1].fact_role !== 'SPEC_VALUE' ||
          refs[0].field_index !== refs[1].field_index || !text(field.label) || !text(field.value) ||
          field.label !== literal(refs[0].text) || field.value !== literal(refs[1].text)) fail()
      if (field.normalization && (!card.profile?.id || !scalar(field.value, field.normalization, field.key))) fail()
      return { key: field.key, label: field.label, value: field.value, normalization: field.normalization,
        citationIndexes: field.citation_indexes, sourcePointer: item.source_pointer,
        sources: [...new Map(refs.map(c => [c.snapshot_ref, pages.get(c.snapshot_ref)])).values()] }
    })
    const profile = card.profile
    if (!profile || !['UNRESOLVED', 'AMBIGUOUS', 'SOURCE_LABEL_CANDIDATE'].includes(profile.state) ||
        ![null, 'pump', 'valve', 'abrasive_wheel'].includes(profile.id) ||
        (profile.id !== null) !== (profile.state === 'SOURCE_LABEL_CANDIDATE')) fail()
    if (profile.id !== null || list(profile.citation_indexes).length) bound(profile.citation_indexes)
    if (profile.id !== null && !text(profile.title?.[language])) fail()
    if (!Array.isArray(card.groups) || card.groups.length > 19) fail()
    const groupKeys = new Set()
    const groups = card.groups.map(group => {
      const indexes = list(group.field_indexes)
      if (!text(group.key) || groupKeys.has(group.key) || !text(group.title?.[language]) ||
          !text(group.next_step?.[language]) || new Set(indexes).size !== indexes.length ||
          indexes.some(i => !Number.isInteger(i) || i < 0 || i >= fields.length || fields[i].key !== group.key)) fail()
      groupKeys.add(group.key)
      const actualIndexes = fields.flatMap((f, i) => f.key === group.key ? [i] : [])
      if (JSON.stringify(actualIndexes) !== JSON.stringify(indexes)) fail()
      const count = new Set(indexes.map(i => fields[i].value)).size
      const state = count > 1 ? 'AMBIGUOUS' : count === 1 ? 'OBSERVED' : 'NOT_OBSERVED_IN_CAPTURE'
      if (group.state !== state) fail()
      return { key: group.key, title: group.title[language], state, fieldIndexes: indexes,
        nextStep: group.next_step[language] }
    })
    const state = profile.id === null ? 'PROFILE_UNRESOLVED' :
      groups.every(g => g.state === 'OBSERVED') ? 'CONFIGURED_GROUPS_OBSERVED' : 'PARTIAL_SOURCE_INFORMATION'
    if (card.state !== state || (card.declared_model !== null &&
        (!['model', 'model number', 'part number'].includes(card.declared_model.label?.toLowerCase()) ||
         new Set(card.fields.filter(f => f.key === 'model').map(f => f.value)).size !== 1 ||
         !card.fields.some(f => f.key === 'model' && JSON.stringify(f) === JSON.stringify(card.declared_model))))) fail()
    const definitions = {
      APPLICATION_SCREEN:['usage'],
      SPECIFICATION_COMPARISON:['dimensions','model','bore','flow','head','power','voltage','frequency','pressure','temperature'],
      OPTION_SELECTION:['bond','grit','abrasive','medium','material','connection'] }
    const purchaseTasks = modern ? list(card.purchase_tasks).map((t,i)=>{
      const task=Object.keys(definitions)[i]
      if (t.task!==task || !text(t.title?.[language]) || !text(t.next_step?.[language]) ||
          !text(t.question?.[language]) || !text(t.verification?.[language])) fail()
      const indexes=card.fields.flatMap((f,j)=>definitions[task].includes(f.key)&&informative(f.value)?[j]:[])
      const citations=[...new Set(indexes.flatMap(j=>card.fields[j].citation_indexes))].sort((a,b)=>a-b)
      if (JSON.stringify(t.field_indexes)!==JSON.stringify(indexes) || JSON.stringify(t.citation_indexes)!==JSON.stringify(citations) ||
          t.state!==(indexes.length?'SOURCE_INFORMATION_AVAILABLE':'UNKNOWN') ||
          t.decision_readiness!==(indexes.length?'SUPPLIER_CONFIRMATION_REQUIRED':'UNKNOWN') ||
          t.engineering_fit!=='UNKNOWN' || t.relationships_verified!==false ||
          t.buyer_requirements_known!==false || t.is_defect!==false) fail()
      return {task,title:t.title[language],state:t.state,decisionReadiness:t.decision_readiness,
        fieldIndexes:indexes,citationIndexes:citations,nextStep:t.next_step[language],question:t.question[language],
        verification:t.verification[language],engineeringFit:'UNKNOWN',relationshipsVerified:false,isDefect:false}
    }) : []
    if (modern && purchaseTasks.length!==3) fail()
    let inquiryPreparation=null
    if (modern) {
      const routes=items.filter(i=>i.rule_id==='CTA-02').filter(i=>{
        const r=pointer(body,i.source_pointer)
        return r.observation.result==='PASS' && r.source_page?.snapshot_ref===name[0].snapshot_ref
      }).map(i=>i.observation_id)
      const q=card.inquiry_preparation
      if (!q || q.state!==(routes.length?'STATIC_ROUTE_RECORDED':'UNKNOWN') ||
          JSON.stringify(q.path_observation_ids)!==JSON.stringify(routes) ||
          JSON.stringify(q.available_input_field_indexes)!==JSON.stringify(fields.flatMap((f,i)=>informative(f.value)?[i]:[])) ||
          q.product_context_transfer!=='UNKNOWN' || q.inquiry_submitted!==false) fail()
      inquiryPreparation={state:q.state,pathObservationIds:routes,availableInputFieldIndexes:q.available_input_field_indexes,
        productContextTransfer:'UNKNOWN',inquirySubmitted:false}
    }
    return { reviewRef: review.review_ref, configurationRef: review.configuration_ref,
      sourcePointer: item.source_pointer, productScopeRef: card.product_scope_ref, name: card.name.text,
      declaredModel: card.declared_model?.value ?? null, profile: { id: profile.id, state: profile.state,
        title: profile.title?.[language] ?? null }, state, fields, groups,
      isRulePass: false, verifiedSku: false, engineeringFit: 'UNKNOWN',
      unknownIsDefect: false, purchaseTasks, inquiryPreparation, sources: [...new Map([...name, ...fields.flatMap(f => f.citationIndexes.map(i => citations[i]))]
        .map(c => [c.snapshot_ref, pages.get(c.snapshot_ref)])).values()] }
  })
}
