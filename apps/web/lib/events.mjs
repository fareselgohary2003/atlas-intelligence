// Live event handling. Events come from the backend (persisted + SSE); nothing here fabricates events.
export const mergeEvents = (existing, incoming, max = 2000) => {
  const bySeq = new Map(existing.map((e) => [e.seq, e]));
  for (const e of incoming) if (e && Number.isInteger(e.seq)) bySeq.set(e.seq, e); // duplicate delivery is idempotent
  const all = [...bySeq.values()].sort((a, b) => a.seq - b.seq);
  return all.length > max ? all.slice(all.length - max) : all;
};
export const lastSeq = (events) => (events.length ? events[events.length - 1].seq : 0);
export const eventsForTask = (events, taskId) => events.filter((e) => e.task_id === taskId);
export const reasonsByTask = (events) => {
  const out = {};
  for (const e of events) if (e.kind === "TASK_CREATED" && e.reason_code) out[e.task_id] = e.reason_code;
  return out;
};
export const FILTERS = {
  all: () => true,
  tools: (e) => e.kind.startsWith("TOOL_"),
  sources: (e) => e.kind.startsWith("SOURCE_"),
  claims: (e) => e.kind === "CLAIM_CREATED" || e.kind === "EVIDENCE_CREATED",
  verification: (e) => e.kind.startsWith("VERIFICATION_"),
  conflicts: (e) => e.kind === "CONFLICT_DETECTED",
  replanning: (e) => ["REPLAN_REQUESTED", "RESEARCH_REPLANNED", "RESEARCH_GAP_DETECTED", "ANALYSIS_REQUESTED"].includes(e.kind),
};
