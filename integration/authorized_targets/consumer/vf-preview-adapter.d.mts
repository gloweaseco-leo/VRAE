export type BuyerTask = 'DISCOVER' | 'UNDERSTAND' | 'TRUST' | 'INQUIRE' | 'SEARCH_TECHNICAL'
export type RuleResult = 'PASS' | 'FAIL_WITH_EVIDENCE' | 'UNKNOWN' | 'ACCESS_BLOCKED' | 'NOT_APPLICABLE'
export type VisitedPage = {
  snapshot_ref: string; url: string; observed_at: string
  capture_status: 'FETCHED'; http_status: 200
}
export type Observation = {
  rule: string; observationId: string; result: RuleResult; text: string; statusText: string
  reason: string | null; sources: VisitedPage[]; sourcePointer: string
  contextFacts: { kind: string; text: string; isRulePass: false; productScopeRef: string | null; citationIndexes: number[]; sourcePointer: string; sources: VisitedPage[] }[]
  path: { from: VisitedPage | null; to: VisitedPage | null }
  limit: { kind: string; text: string } | null
}
export type Insight = {
  task: BuyerTask; explanation: string; rebuild: string[]; checks: string[]
  verification: string | null; verificationIsPlan: true; sources: string[]
  purchaseTask: string | null; opportunityKind: 'CLARIFICATION' | null
}
export type PurchaseTask = {
  task: 'APPLICATION_SCREEN' | 'SPECIFICATION_COMPARISON' | 'OPTION_SELECTION'; title: string
  state: 'SOURCE_INFORMATION_AVAILABLE' | 'UNKNOWN'; decisionReadiness: 'SUPPLIER_CONFIRMATION_REQUIRED' | 'UNKNOWN'
  fieldIndexes: number[]; citationIndexes: number[]; nextStep: string; question: string; verification: string
  engineeringFit: 'UNKNOWN'; relationshipsVerified: false; isDefect: false
}
export type InquiryPreparation = { state: 'STATIC_ROUTE_RECORDED' | 'UNKNOWN'; pathObservationIds: string[];
  availableInputFieldIndexes: number[]; productContextTransfer: 'UNKNOWN'; inquirySubmitted: false }
export type ProcurementCard = {
  reviewRef: string; configurationRef: string; sourcePointer: string; productScopeRef: string
  name: string; declaredModel: string | null; profile: { id: string | null; state: string; title: string | null }
  state: string; isRulePass: false; verifiedSku: false; engineeringFit: 'UNKNOWN'; unknownIsDefect: false
  fields: { key: string | null; label: string; value: string; citationIndexes: number[];
    sourcePointer: string; sources: VisitedPage[]; normalization: { dimension: string; value: string; unit: string } | null }[]
  groups: { key: string; title: string; state: string; fieldIndexes: number[]; nextStep: string }[]
  sources: VisitedPage[]
  purchaseTasks: PurchaseTask[]; inquiryPreparation: InquiryPreparation | null
}
export type ReviewPage = VisitedPage | { snapshot_ref: string; url: string; observed_at: string;
  capture_status: string; http_status: number | null; reason: string | null }
export type ReviewCoverage = { rule_id: string; total: number; returned: number; truncated: boolean }
export type ReviewCandidate = {
  observationId: string; rule: string; candidateResult: RuleResult; title: string; text: string; reason: string
  sourceVersion: string; ruleVersion: string; sources: ReviewPage[]; humanReviewRequired: true; isNativeFact: false
  evidenceBindings: { evidence_ref: string; snapshot_ref: string; locator: string; content_sha256: string; byte_start: number; byte_end: number }[]
}
export type BuyerReview = {
  state: 'AVAILABLE' | 'CANDIDATES_UNAVAILABLE'; reviewRef: string; s2ProjectionRef: string | null
  tasks: { task: BuyerTask; candidates: ReviewCandidate[]; coverage: ReviewCoverage[] }[]
  paths: { journeyRef: string; staticPathComplete: boolean; terminalResult: RuleResult;
    productScopeRefs: string[];
    productContextTransfer: 'UNKNOWN'; inquirySubmitted: false;
    steps: { rule: string; observationId: string; result: RuleResult; sourcePointer: string;
      from: ReviewPage | null; to: ReviewPage | null }[] }[]
  pathCoverage: { total: number; returned: number; truncated: boolean; whole_site_coverage_known: false }
  technicalMaterialRoute: 'UNKNOWN'; proofRoute: 'UNKNOWN'
}
export type PreviewResult = {
  state: 'running' | 'analyzing' | 'failed' | 'diagnosed' | 'ai-unavailable'
  pages: { id: string; url: string; observed: true; checkedAt: string }[]
  insights: Insight[]
  buyerReview: BuyerReview | null
  buyerTasks: { task: BuyerTask; title: string; observations: Observation[]; insights: Insight[]; procurementCards: ProcurementCard[]; procurementCoverage: { eligible_products: number; reviewed_products: number; truncated: boolean } | null; reviewCandidates: ReviewCandidate[]; reviewCoverage: ReviewCoverage[];
    recordedFacts: Observation['contextFacts']; purchaseTasks: (PurchaseTask & { productScopeRef: string; sourcePointer: string })[];
    inquiryPreparation: (InquiryPreparation & { productScopeRef: string; sourcePointer: string })[];
    sourceFactReview: (TrustSourceReview | InquirySourceReview | TechnicalSourceReview)[];
    supplementalInvestigations: SupplementalInvestigation[] }[]
  analysisOutcome: string; analysisText: string; modelFailureStage: string | null; aiWarning: string | null
  captureSummary: {
    candidate_urls: number; page_records: number; fetched_pages: number; unvisited_candidates: number
    http_requests_including_robots: number; timeout_page_records: number; inventory_truncated: boolean
    unvisited_is_defect: false
  } | null
  pageScope: {
    visited: VisitedPage[]; failed: { url: string; reason: string | null; capture_status: string }[]
    candidates: { url: string; reason: string; is_defect: false }[]
    candidatesAreDefects: false; candidatesInitiallyCollapsed: true
  }
  formalHumanReview: false
  reportView: {
    buyerReview: BuyerReview | null
    tasks: { task: BuyerTask; title: string; observations: (Observation & { observationIds: string[]; sourcePointers: string[] })[]; insights: Insight[]; contextFacts: Observation['contextFacts']; procurementCards: ProcurementCard[]; procurementCoverage: PreviewResult['buyerTasks'][number]['procurementCoverage']; reviewCandidates: ReviewCandidate[]; reviewCoverage: ReviewCoverage[];
      recordedFacts: Observation['contextFacts']; purchaseTasks: PreviewResult['buyerTasks'][number]['purchaseTasks'];
      inquiryPreparation: PreviewResult['buyerTasks'][number]['inquiryPreparation'];
      sourceFactReview: PreviewResult['buyerTasks'][number]['sourceFactReview'];
      supplementalInvestigations: SupplementalInvestigation[] }[]
    visitedPageCount: number; failedPageCount: number; candidatePageCount: number
    originalObservationCount: number; displayObservationCount: number; unknownCount: number
    countsAreNotScoreOrDefectCount: true; printCandidateUrls: false
    contextFacts: Observation['contextFacts']; analysisText: string; insights: Insight[]
  }
}

export type SourceBinding = { evidence_ref: string; snapshot_ref: string; locator: string;
  content_sha256: string; byte_start: number; byte_end: number }
export type TrustSourceReview = { source_pointer: string; nativeResult: RuleResult;
  context_facts: { kind: string; citation_indexes: number[] }[]; missing_prerequisites: string[];
  identity_verified: false; materials_authenticated: false }
export type FormField = { field_ref: string; kind: 'NAME'|'EMAIL'|'COMPANY'|'PHONE'|'COUNTRY'|'SUBJECT'|'MESSAGE'|'PRODUCT'|'MODEL'|'QUANTITY'|'SEARCH'|'ACCOUNT_SECRET'|'UNKNOWN';
  input_type: string; label_basis: 'SOURCE_LABEL'|'INPUT_TYPE'|'UNRESOLVED'; required_attribute: boolean;
  disabled_attribute: boolean; readonly_attribute: boolean; binding: SourceBinding; label_binding: SourceBinding|null }
export type StaticForm = { form_ref: string; binding: SourceBinding; purpose: 'INQUIRY_CANDIDATE'|'SEARCH_CANDIDATE'|'ACCOUNT_CANDIDATE'|'UNRESOLVED';
  method: 'GET'|'POST'|'UNKNOWN'; action_scope: 'SAME_ORIGIN'|'EXTERNAL'|'UNRESOLVED'; fields: FormField[];
  hidden_control_count: number; submit_control_observed: boolean; field_coverage: {total:number;returned:number;truncated:boolean};
  visibility:'UNKNOWN';product_context_transfer:'UNKNOWN';submission_tested:false;delivery:'UNKNOWN';native_fact_admission:'NONE' }
export type InquirySourceReview = { snapshot_ref:string;state:'STATIC_DECLARATIONS_RECORDED'|'PARSER_UNSUPPORTED';
  static_forms: {forms:StaticForm[];coverage:{total:number;returned:number;truncated:boolean};nested_forms_excluded:number;unclosed_forms_excluded:number}|null;
  absence_proven:false;delivery:'UNKNOWN' }
export type HttpMeasurement = {method:'PINNED_HTTP_MONOTONIC_V1';scope:'FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS';samples:1;
  connect_ms:number;stream_setup_ms:number;first_byte_after_send_ms:number;headers_after_send_ms:number;body_after_headers_ms:number;exchange_ms:number}
export type TechnicalSourceReview = {snapshot_ref:string;source_ref:string;source_locator:string;capture_status:string;http_status:number|null;
  response_body_bytes:number;redirect_count:number;measurement:HttpMeasurement|null;timing_state:'MEASURED'|'UNKNOWN';samples:0|1;is_defect:false}

export type SupplementalInvestigation = {source_snapshot_ref:string;target_snapshot_ref:string;
  purpose:'TECHNICAL_MATERIAL'|'APPLICATION_CONTEXT'|'PROOF_CONTEXT';trigger:string;source_binding:SourceBinding;
  product_applicability:'UNKNOWN';gap_resolved:'UNKNOWN';is_defect:false;native_fact_admission:'NONE';
  source:VisitedPage;target:ReviewPage;result:'CAPTURED'|'NOT_CAPTURED';policy:'SOURCE_LINK_GAPS_V1';stopReason:string}

/** Call after existing mTLS, source-SHA, media, no-store and same-session checks. */
export function projectPreviewResult(body: Record<string, unknown>, status: number,
  auditRef: string, language?: 'zh' | 'en'): PreviewResult
