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
export type PreviewResult = {
  state: 'running' | 'analyzing' | 'failed' | 'diagnosed' | 'ai-unavailable'
  pages: { id: string; url: string; observed: true; checkedAt: string }[]
  insights: Insight[]
  buyerTasks: { task: BuyerTask; title: string; observations: Observation[]; insights: Insight[] }[]
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
    tasks: { task: BuyerTask; title: string; observations: (Observation & { observationIds: string[]; sourcePointers: string[] })[]; insights: Insight[]; contextFacts: Observation['contextFacts'] }[]
    visitedPageCount: number; failedPageCount: number; candidatePageCount: number
    originalObservationCount: number; displayObservationCount: number; unknownCount: number
    countsAreNotScoreOrDefectCount: true; printCandidateUrls: false
    contextFacts: Observation['contextFacts']; analysisText: string; insights: Insight[]
  }
}

/** Call after existing mTLS, source-SHA, media, no-store and same-session checks. */
export function projectPreviewResult(body: Record<string, unknown>, status: number,
  auditRef: string, language?: 'zh' | 'en'): PreviewResult
