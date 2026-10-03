import test from "node:test";
import assert from "node:assert/strict";
import { metric, formatCost, formatDuration, formatTokens, claimLabel, tone, elapsedSeconds, NO_DATA, truncate } from "../lib/format.mjs";
import { readCookie, csrfHeaders } from "../lib/csrf.mjs";
import { mergeEvents, lastSeq, reasonsByTask, FILTERS, eventsForTask } from "../lib/events.mjs";
import { currentPhase, describeEvent } from "../lib/phase.mjs";
import { layoutGraph, neighbors } from "../lib/graph.mjs";

test("metrics never invent numbers", () => {
  assert.equal(metric(null), NO_DATA); assert.equal(metric(undefined), NO_DATA); assert.equal(metric(0), NO_DATA);
  assert.equal(metric(1284), "1,284");
  assert.equal(formatCost(null), "Unavailable"); assert.equal(formatCost(0.0002), "$0.0002"); assert.equal(formatCost(1.234), "$1.23");
  assert.equal(formatCost(0.5, false), "$0.50 (partial)");
  assert.equal(formatTokens(null), "Unavailable"); assert.equal(formatTokens(5, false), "Unavailable"); assert.equal(formatTokens(1500), "1,500");
  assert.equal(formatDuration(null), NO_DATA); assert.equal(formatDuration(42), "42s"); assert.equal(formatDuration(125), "2m 5s"); assert.equal(formatDuration(7260), "2h 1m");
  assert.equal(truncate("abcdef", 4), "abc…"); assert.equal(truncate(null), "");
});
test("claim labels do not overstate verification", () => {
  assert.equal(claimLabel("proposed"), "Unverified"); assert.equal(claimLabel("supported"), "Verified");
  assert.equal(claimLabel("insufficient_evidence"), "Insufficient evidence"); assert.equal(tone("contradicted"), "bad"); assert.equal(tone("zzz"), "muted");
});
test("elapsed time", () => {
  assert.equal(elapsedSeconds(null, null), null);
  assert.equal(elapsedSeconds("2026-01-01T00:00:00Z", "2026-01-01T00:01:30Z"), 90);
  assert.equal(elapsedSeconds("2026-01-01T00:00:00Z", null, Date.parse("2026-01-01T00:00:10Z")), 10);
  assert.equal(elapsedSeconds("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"), null);
});
test("csrf header is attached only to unsafe methods and only when the cookie exists", () => {
  const c = "a=1; atlas_csrf=tok%20en; atlas_session=ignored";
  assert.equal(readCookie("atlas_csrf", c), "tok en"); assert.equal(readCookie("missing", c), null); assert.equal(readCookie("x", ""), null);
  assert.deepEqual(csrfHeaders("GET", c), {}); assert.deepEqual(csrfHeaders("head", c), {});
  assert.deepEqual(csrfHeaders("POST", c), { "X-CSRF-Token": "tok en" }); assert.deepEqual(csrfHeaders("delete", c), { "X-CSRF-Token": "tok en" });
  assert.deepEqual(csrfHeaders("POST", "a=1"), {}); assert.equal(readCookie("atlas_csrf", "xatlas_csrf=bad"), null);
});
test("event merging is idempotent, ordered and bounded", () => {
  const a = [{ seq: 1, kind: "X" }, { seq: 2, kind: "Y" }];
  const m = mergeEvents(a, [{ seq: 2, kind: "Y" }, { seq: 4, kind: "Z" }, { seq: 3, kind: "W" }, null, { kind: "bad" }]);
  assert.deepEqual(m.map((e) => e.seq), [1, 2, 3, 4]); assert.equal(lastSeq(m), 4); assert.equal(lastSeq([]), 0);
  assert.deepEqual(mergeEvents(m, m).map((e) => e.seq), [1, 2, 3, 4]);
  assert.deepEqual(mergeEvents([], [{ seq: 1 }, { seq: 2 }, { seq: 3 }], 2).map((e) => e.seq), [2, 3]);
  assert.equal(eventsForTask([{ seq: 1, task_id: "t1" }, { seq: 2, task_id: "t2" }], "t1").length, 1);
  assert.deepEqual(reasonsByTask([{ kind: "TASK_CREATED", task_id: "f-1", reason_code: "LOW_SOURCE_QUALITY" }, { kind: "TASK_CREATED", task_id: "t1" }]), { "f-1": "LOW_SOURCE_QUALITY" });
  assert.ok(FILTERS.tools({ kind: "TOOL_STARTED" }) && !FILTERS.tools({ kind: "CLAIM_CREATED" }) && FILTERS.conflicts({ kind: "CONFLICT_DETECTED" }) && FILTERS.replanning({ kind: "REPLAN_REQUESTED" }));
});
test("phase follows the latest meaningful event, and terminal statuses win", () => {
  assert.equal(currentPhase([], "planning"), "planning");
  assert.equal(currentPhase([{ kind: "PLAN_CREATED" }, { kind: "AGENT_STARTED" }], "researching"), "researching");
  assert.equal(currentPhase([{ kind: "AGENT_STARTED" }, { kind: "VERIFICATION_STARTED" }], "researching"), "verifying");
  assert.equal(currentPhase([{ kind: "ANALYSIS_REQUESTED" }], "researching"), "analyzing");
  assert.equal(currentPhase([{ kind: "ANALYSIS_REQUESTED" }], "completed"), "completed"); assert.equal(currentPhase([], "paused"), "paused");
  assert.equal(currentPhase([], "needs_review"), "needs_review");
});
test("event descriptions are concise activity summaries and never expose reasoning", () => {
  const e = { kind: "TASK_COMPLETED", agent: "market", summary: "Saved 3 sources", reasoning: "SECRET CHAIN OF THOUGHT", chain_of_thought: "x" };
  const t = describeEvent(e);
  assert.equal(t, "market agent completed: Saved 3 sources"); assert.ok(!t.includes("SECRET"));
  assert.equal(describeEvent({ kind: "VERIFICATION_COMPLETED", counts: { partially_supported: 3 } }), "Verification completed: 3 partially supported");
  assert.equal(describeEvent({ kind: "RESEARCH_GAP_DETECTED", reason_code: "INSUFFICIENT_EVIDENCE" }), "Research gap detected: INSUFFICIENT_EVIDENCE");
  assert.equal(describeEvent({ kind: "RESEARCH_REPLANNED", new_tasks: ["a", "b"], replans: 1 }), "Plan updated: 2 new tasks (replan 1)");
  assert.equal(describeEvent({ kind: "SOURCE_FOUND", counts: { results: 1 } }), "1 search result found");
  assert.equal(describeEvent({ kind: "UNKNOWN_KIND" }), "UNKNOWN_KIND");
  assert.equal(describeEvent({ kind: "CONFLICT_DETECTED", conflict_type: "different_definition", action: "explained_by_scope" }), "Conflict detected: different definition (explained_by_scope)");
});
const G = { nodes: [{ id: "c:1", type: "claim", label: "A", status: "supported" }, { id: "c:2", type: "claim", label: "B", status: "contradicted", is_demo: true },
  { id: "e:1", type: "evidence", label: "q", stance: "supports" }, { id: "s:1", type: "source", label: "S" }],
  edges: [{ id: "ce:1", source: "c:1", target: "e:1", type: "has_evidence", stance: "supports" }, { id: "es:1", source: "e:1", target: "s:1", type: "from_source" },
    { id: "cc:1", source: "c:1", target: "c:2", type: "conflicts_with", conflict_type: "different_definition", resolution_status: "explained_by_scope" }] };
test("graph layout keeps every backend node/edge and adds none", () => {
  const { nodes, edges } = layoutGraph(G);
  assert.equal(nodes.length, 4); assert.equal(edges.length, 3);
  assert.deepEqual(nodes.map((n) => n.id), G.nodes.map((n) => n.id));
  assert.deepEqual(nodes.filter((n) => n.data.raw.type === "claim").map((n) => n.position.y), [0, 96]);
  assert.ok(nodes[0].position.x < nodes[2].position.x && nodes[2].position.x < nodes[3].position.x);
  assert.equal(nodes[1].style.borderStyle, "dashed"); assert.equal(nodes[0].style.borderStyle, "solid");
  const c = edges.find((e) => e.id === "cc:1");
  assert.equal(c.label, "different definition"); assert.equal(c.animated, false); assert.ok(c.style.strokeDasharray);
  assert.deepEqual(layoutGraph({ nodes: [], edges: [] }), { nodes: [], edges: [] });
});
test("neighbors for the inspector", () => {
  assert.deepEqual([...neighbors(G, "e:1")].sort(), ["c:1", "e:1", "s:1"]);
  assert.deepEqual([...neighbors(G, "zzz")], ["zzz"]);
});
