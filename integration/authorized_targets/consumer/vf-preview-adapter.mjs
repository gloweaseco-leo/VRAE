// Pure BFF adapter for VF's existing preview shape. No UI/HTTP/session changes.
import { projectResult } from './reference.mjs'

const states = { CAPTURE_PENDING: 'running', AI_PENDING: 'analyzing', CAPTURE_FAILED: 'failed',
  DIAGNOSED: 'diagnosed', AI_UNAVAILABLE: 'ai-unavailable' }

export function projectPreviewResult(body, status, auditRef, language = 'zh') {
  const value = projectResult(body, status, auditRef, language)
  const pages = value.pageScope.visited.map(page => ({ id: page.snapshot_ref,
    url: page.url, observed: true, checkedAt: page.observed_at }))
  const insights = value.claims.map(claim => ({ task: claim.task, explanation: claim.explanation,
    rebuild: claim.rebuild, checks: [...claim.uncertainties, ...claim.questions],
    verification: claim.verification, verificationIsPlan: true,
    sources: claim.sources.map(page => page.snapshot_ref) }))
  return { state: states[value.state], pages, insights,
    buyerTasks: value.facts.map(task => ({ ...task,
      insights: insights.filter(claim => claim.task === task.task) })),
    analysisOutcome: value.analysisOutcome, analysisText: value.analysisText,
    modelFailureStage: value.modelFailureStage, aiWarning: value.aiWarning,
    captureSummary: value.captureSummary, pageScope: value.pageScope,
    formalHumanReview: false }
}
