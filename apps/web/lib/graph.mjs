// Turns the backend graph (Claim -> Evidence -> Source, Claim <-> Claim conflicts) into React Flow nodes/edges. No data is added.
export const STATUS_COLOR = { supported: "#16a34a", partially_supported: "#d97706", contradicted: "#dc2626", insufficient_evidence: "#6b7280", proposed: "#6b7280" };
const COL = { claim: 0, evidence: 360, source: 720 };
export const layoutGraph = (graph, rowHeight = 96) => {
  const rows = { claim: 0, evidence: 0, source: 0 };
  const nodes = graph.nodes.map((n) => {
    const y = rows[n.type]++ * rowHeight;
    const border = n.type === "claim" ? STATUS_COLOR[n.status] || "#6b7280" : n.type === "evidence" ? (n.stance === "contradicts" ? "#dc2626" : "#2563eb") : "#475569";
    return { id: n.id, position: { x: COL[n.type], y }, data: { label: n.label, raw: n }, type: "default",
      style: { width: 300, fontSize: 12, border: `2px solid ${border}`, borderRadius: 6, padding: 8, background: "var(--card)", color: "var(--tx)", borderStyle: n.is_demo ? "dashed" : "solid" } };
  });
  const edges = graph.edges.map((e) => e.type === "conflicts_with"
    ? { id: e.id, source: e.source, target: e.target, label: e.conflict_type.replace(/_/g, " "), animated: e.resolution_status === "unresolved",
        style: { stroke: e.resolution_status === "explained_by_scope" ? "#d97706" : "#dc2626", strokeDasharray: "6 4" }, data: e }
    : { id: e.id, source: e.source, target: e.target, label: e.type === "has_evidence" ? e.stance : undefined, data: e });
  return { nodes, edges };
};
export const neighbors = (graph, id) => {
  const ids = new Set([id]);
  for (const e of graph.edges) { if (e.source === id) ids.add(e.target); if (e.target === id) ids.add(e.source); }
  return ids;
};
