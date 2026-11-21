// Presentation grouping only. Never changes a rule outcome or source observation.
function groupContext(facts) {
  const groups = new Map()
  for (const fact of facts) {
    const key = JSON.stringify([fact.kind, fact.text, fact.productScopeRef])
    const binding = { sourcePointer: fact.sourcePointer, citationIndexes: fact.citationIndexes }
    const previous = groups.get(key)
    if (previous) {
      previous.bindings.push(binding)
      previous.sources = [...new Map([...previous.sources, ...fact.sources].map(p => [p.snapshot_ref, p])).values()]
    } else groups.set(key, { ...fact, bindings: [binding] })
  }
  return [...groups.values()]
}

export function buildReportView(preview) {
  const tasks = preview.buyerTasks.map(task => {
    const groups = new Map()
    for (const observation of task.observations) {
      const path = observation.path
      const key = ['DISC-01', 'DISC-02', 'CTA-02'].includes(observation.rule) && path?.from && path?.to
        ? JSON.stringify([observation.rule, observation.result, observation.reason, path.from.snapshot_ref, path.to.snapshot_ref])
        : observation.observationId
      const previous = groups.get(key)
      if (previous) {
        previous.observationIds.push(observation.observationId)
        previous.sourcePointers.push(observation.sourcePointer)
        previous.sources = [...new Map([...previous.sources, ...observation.sources].map(p => [p.snapshot_ref, p])).values()]
      } else groups.set(key, { ...observation, observationIds: [observation.observationId], sourcePointers: [observation.sourcePointer] })
    }
    return { ...task, observations: [...groups.values()],
      contextFacts: groupContext(task.observations.flatMap(o => o.contextFacts)) }
  })
  const view = { tasks, buyerReview:preview.buyerReview, visitedPageCount: preview.pages.length,
    failedPageCount: preview.pageScope.failed.length, candidatePageCount: preview.pageScope.candidates.length,
    originalObservationCount: preview.buyerTasks.reduce((n, t) => n+t.observations.length, 0),
    displayObservationCount: tasks.reduce((n, t) => n+t.observations.length, 0),
    unknownCount: preview.buyerTasks.flatMap(t => t.observations).filter(o => o.result === 'UNKNOWN').length,
    countsAreNotScoreOrDefectCount: true, printCandidateUrls: false,
    contextFacts: groupContext(tasks.flatMap(t => t.contextFacts)),
    analysisText: preview.analysisText, insights: preview.insights }
  if (preview.judgment) view.judgment = preview.judgment
  return view
}
