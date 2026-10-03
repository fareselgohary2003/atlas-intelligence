// Pure formatting helpers. Unknown values are shown as "No data yet" / "Unavailable", never as invented numbers.
export const NO_DATA = "No data yet";
export const metric = (n) => (n == null || n === 0 ? NO_DATA : Number(n).toLocaleString("en-US"));
export const formatDuration = (s) => {
  if (s == null || Number.isNaN(s)) return NO_DATA;
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
};
export const formatCost = (cost, complete = true) =>
  cost == null ? "Unavailable" : `$${cost < 0.01 ? cost.toFixed(4) : cost.toFixed(2)}${complete ? "" : " (partial)"}`;
export const formatTokens = (n, reported = true) => (!reported || n == null ? "Unavailable" : Number(n).toLocaleString("en-US"));
export const truncate = (s, n = 120) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");
export const CLAIM_LABEL = {
  supported: "Verified", partially_supported: "Partially supported", contradicted: "Contradicted",
  insufficient_evidence: "Insufficient evidence", proposed: "Unverified",
};
export const claimLabel = (status) => CLAIM_LABEL[status] || status;
export const TONE = { supported: "ok", partially_supported: "warn", contradicted: "bad", insufficient_evidence: "muted", proposed: "muted",
  completed: "ok", researching: "info", verifying: "info", analyzing: "info", queued: "muted", paused: "warn", cancelled: "muted",
  failed: "bad", needs_review: "warn", planning: "muted", running: "info", pending: "muted", skipped: "muted" };
export const tone = (status) => TONE[status] || "muted";
export const elapsedSeconds = (startedAt, finishedAt, now = Date.now()) => {
  if (!startedAt) return null;
  const end = finishedAt ? Date.parse(finishedAt) : now;
  const s = (end - Date.parse(startedAt)) / 1000;
  return Number.isFinite(s) && s >= 0 ? s : null;
};
