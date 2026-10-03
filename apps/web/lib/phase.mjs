// Phase + human-readable activity text. Only safe, public event fields are used: no reasoning is ever shown.
export const PHASE_ORDER = ["planning", "researching", "verifying", "analyzing", "completed"];
const kindPhase = { PLAN_CREATED: "planning", AGENT_STARTED: "researching", SOURCE_FOUND: "researching", VERIFICATION_STARTED: "verifying",
  VERIFICATION_COMPLETED: "verifying", ANALYSIS_REQUESTED: "analyzing", ANALYSIS_SAVED: "analyzing" };
export const currentPhase = (events, status) => {
  if (["completed", "needs_review"].includes(status)) return status === "completed" ? "completed" : "needs_review";
  if (["failed", "cancelled", "paused", "queued"].includes(status)) return status;
  for (let i = events.length - 1; i >= 0; i--) if (kindPhase[events[i].kind]) return kindPhase[events[i].kind];
  return status || "planning";
};
const n = (v, word) => `${v} ${word}${v === 1 ? "" : "s"}`;
const sum = (c) => Object.entries(c || {}).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ");
export const describeEvent = (e) => {
  const who = e.agent ? `${e.agent} agent` : "System";
  switch (e.kind) {
    case "RESEARCH_STARTED": return "Research started";
    case "PLAN_CREATED": return `Research plan created (${n(e.task_count ?? 0, "task")})`;
    case "TASK_CREATED": return `Task created: ${e.title ?? e.task_id}${e.reason_code ? ` — reason ${e.reason_code}` : ""}`;
    case "AGENT_STARTED": return `${who} started${e.attempt > 1 ? ` (attempt ${e.attempt})` : ""}`;
    case "TOOL_STARTED": return `${who} running tool ${e.tool}`;
    case "TOOL_COMPLETED": return `${who} finished ${e.tool}${e.duration_ms != null ? ` in ${e.duration_ms} ms` : ""}`;
    case "TOOL_FAILED": return `${who}: tool ${e.tool} failed (${e.error_category ?? "error"})`;
    case "SOURCE_FOUND": return `${n(e.counts?.results ?? 0, "search result")} found`;
    case "SOURCE_SAVED": return `Source ${e.action === "matched" ? "matched" : "saved"}${e.source?.publisher ? ` from ${e.source.publisher}` : ""}`;
    case "EVIDENCE_CREATED": return `${who} recorded evidence`;
    case "CLAIM_CREATED": return `${who} created a ${String(e.action ?? "").replace(/_/g, " ")} claim`;
    case "VERIFICATION_STARTED": return `Verification started (${n(e.counts?.claims ?? 0, "claim")})`;
    case "VERIFICATION_COMPLETED": return `Verification completed: ${sum(e.counts) || "no claims"}`;
    case "CONFLICT_DETECTED": return `Conflict detected: ${String(e.conflict_type ?? "").replace(/_/g, " ")} (${e.action ?? "unresolved"})`;
    case "RESEARCH_GAP_DETECTED": return `Research gap detected: ${e.reason_code}`;
    case "REPLAN_REQUESTED": return `Replan requested${e.reasons?.length ? `: ${e.reasons.join(", ")}` : ""}`;
    case "RESEARCH_REPLANNED": return `Plan updated: ${n(e.new_tasks?.length ?? 0, "new task")} (replan ${e.replans})`;
    case "ANALYSIS_REQUESTED": return "Analysis scheduled";
    case "ANALYSIS_SAVED": return `Analyst recorded an inference (${e.action})`;
    case "TASK_PROGRESS": return `${who}: ${e.summary ?? "progress"} (${e.progress ?? 0}%)`;
    case "TASK_COMPLETED": return `${who} completed${e.summary ? `: ${e.summary}` : ""}`;
    case "TASK_RETRY": return `${who} will retry (attempt ${e.attempt}): ${e.error ?? ""}`;
    case "TASK_FAILED": return `${who} failed: ${e.error ?? ""}`;
    case "TASK_SKIPPED": return "Task skipped: a dependency did not complete";
    case "TASK_CANCELLED": return "Task cancelled";
    case "RESEARCH_PAUSED": return "Research paused";
    case "RESEARCH_CANCELLED": return "Research cancelled";
    case "RESEARCH_COMPLETED": return `Research finished with status ${e.status}`;
    case "RESEARCH_FAILED": return `Research failed: ${e.error ?? ""}`;
    default: return e.kind;
  }
};
