// A recorded investigation attempt does not establish applicability or success.
const fail=()=>{throw new Error('INVALID_DIAGNOSIS_DELIVERY')}
const purposes=['TECHNICAL_MATERIAL','APPLICATION_CONTEXT','PROOF_CONTEXT']
const triggers=['NO_STRUCTURED_PRODUCT_FIELDS_RECORDED','NO_APPLICATION_FIELD_RECORDED','PROOF_CONTEXT_NOT_YET_FETCHED']
export function supplementalReview(review,all,pages,technical,binding){
  if(review.supplemental===undefined)return []
  if(!Array.isArray(review.supplemental)||review.supplemental.length>1)fail()
  return review.supplemental.map(s=>{
    if(s.policy!=='SOURCE_LINK_GAPS_V1'||!/^src-[0-9a-f]{64}$/.test(s.source_ref)||s.max_supplemental_pages!==2||
      s.whole_site_coverage_known!==false||!Array.isArray(s.decisions)||s.decisions.length>2||
      !['SAFETY_OR_BUDGET_STOP','PAGE_LIMIT_REACHED','NO_ELIGIBLE_SOURCE_LINK','ADAPTIVE_LIMIT_REACHED','BASELINE_COVERAGE_FIRST','TIME_BUDGET_RESERVED','SOURCE_LINK_SELECTED'].includes(s.stop_reason))fail()
    const seen=new Set(),used=new Set()
    const decisions=s.decisions.map(d=>{
      const from=technical.find(t=>t.snapshot_ref===d.source_snapshot_ref),to=technical.find(t=>t.snapshot_ref===d.target_snapshot_ref)
      const position=t=>Number(t.source_locator.split('/').at(-1))
      if(!pages.has(d.source_snapshot_ref)||!all.has(d.target_snapshot_ref)||!from||!to||
        from.source_ref!==s.source_ref||to.source_ref!==s.source_ref||position(from)>=position(to)||
        seen.has(d.source_snapshot_ref)||seen.has(d.target_snapshot_ref)||used.has(d.purpose)||
        !purposes.includes(d.purpose)||d.trigger!==triggers[purposes.indexOf(d.purpose)]||
        d.product_applicability!=='UNKNOWN'||d.gap_resolved!=='UNKNOWN'||d.is_defect!==false||d.native_fact_admission!=='NONE')fail()
      binding(d.source_binding,d.source_snapshot_ref)
      seen.add(d.target_snapshot_ref);used.add(d.purpose)
      return {...d,source:pages.get(d.source_snapshot_ref),target:all.get(d.target_snapshot_ref),
        result:pages.has(d.target_snapshot_ref)?'CAPTURED':'NOT_CAPTURED'}
    })
    return {...s,decisions}
  })
}
