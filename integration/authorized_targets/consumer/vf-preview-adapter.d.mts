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
}
export type ProcurementCard = {
  reviewRef: string; configurationRef: string; sourcePointer: string; productScopeRef: string
  name: string; declaredModel: string | null; profile: { id: string | null; state: string; title: string | null }
  state: string; isRulePass: false; verifiedSku: false; engineeringFit: 'UNKNOWN'; unknownIsDefect: false
  fields: { key: string | null; label: string; value: string; citationIndexes: number[];
    sourcePointer: string; sources: VisitedPage[]; normalization: { dimension: string; value: string; unit: string } | null }[]
  groups: { key: string; title: string; state: string; fieldIndexes: number[]; nextStep: string }[]
  sources: VisitedPage[]
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
  buyerTasks: { task: BuyerTask; title: string; observations: Observation[]; insights: Insight[]; procurementCards: ProcurementCard[]; procurementCoverage: { eligible_products: number; reviewed_products: number; truncated: boolean } | null; reviewCandidates: ReviewCandidate[]; reviewCoverage: ReviewCoverage[] }[]
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
    tasks: { task: BuyerTask; title: string; observations: (Observation & { observationIds: string[]; sourcePointers: string[] })[]; insights: Insight[]; contextFacts: Observation['contextFacts']; procurementCards: ProcurementCard[]; procurementCoverage: PreviewResult['buyerTasks'][number]['procurementCoverage']; reviewCandidates: ReviewCandidate[]; reviewCoverage: ReviewCoverage[] }[]
    visitedPageCount: number; failedPageCount: number; candidatePageCount: number
    originalObservationCount: number; displayObservationCount: number; unknownCount: number
    countsAreNotScoreOrDefectCount: true; printCandidateUrls: false
    contextFacts: Observation['contextFacts']; analysisText: string; insights: Insight[]
  }
}

/** Call after existing mTLS, source-SHA, media, no-store and same-session checks. */
export function projectPreviewResult(body: Record<string, unknown>, status: number,
  auditRef: string, language?: 'zh' | 'en'): PreviewResult
