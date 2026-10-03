"use client";
import "reactflow/dist/style.css";
import { useMemo, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import { useApi } from "@/lib/useApi";
import { layoutGraph, neighbors } from "@/lib/graph.mjs";
import { claimLabel } from "@/lib/format.mjs";
import { Card, Empty, Gate, Mock, Pill } from "../ui";

export default function GraphView({ rid }: { rid: string }) {
  const q = useApi<any>(`/api/research/${rid}/graph?limit=100`);
  const [sel, setSel] = useState<string | null>(null);
  return (
    <Gate q={q} rows={6}>{(g) => g.nodes.length === 0 ? <Card><Empty title="No evidence graph yet" hint="The graph is built from stored claims, evidence and sources." /></Card> : <GraphBody g={g} sel={sel} setSel={setSel} />}</Gate>
  );
}

function GraphBody({ g, sel, setSel }: { g: any; sel: string | null; setSel: (s: string | null) => void }) {
  const flow = useMemo(() => layoutGraph(g), [g]);
  const near = sel ? neighbors(g, sel) : null;
  const nodes = flow.nodes.map((n: any) => ({ ...n, style: { ...n.style, opacity: near && !near.has(n.id) ? 0.25 : 1 } }));
  const node = g.nodes.find((n: any) => n.id === sel);
  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
      <Card className="h-[70vh]"><ReactFlow nodes={nodes} edges={flow.edges} fitView onNodeClick={(_, n) => setSel(n.id)} onPaneClick={() => setSel(null)} nodesDraggable minZoom={0.2}><Background /><Controls /><MiniMap pannable zoomable /></ReactFlow></Card>
      <Card className="p-3 text-[12px]">
        <div className="mb-2 font-medium">Inspector</div>
        <div className="mb-3 text-mut">{g.counts.claims} claims · {g.counts.evidence} evidence · {g.counts.sources} sources · {g.counts.conflicts} conflicts{g.truncated && " · truncated to the first claims"}</div>
        {!node ? <p className="text-mut">Click a node to inspect it and highlight its relationships. Dashed borders mark DEMO/MOCK data; dashed edges are conflicts.</p> : <div className="space-y-2">
          <div className="flex items-center gap-2"><Pill>{node.type}</Pill>{node.is_demo && <Mock />}{node.status && <Pill>{claimLabel(node.status)}</Pill>}{node.stance && <Pill>{node.stance}</Pill>}</div>
          <p>{node.label}</p>{node.url && <a className="text-acc" href={node.url} target="_blank" rel="noreferrer noopener">{node.url}</a>}
          {node.has_conflict && <p className="text-amber-700 dark:text-amber-400">This claim is involved in a recorded conflict.</p>}
          {g.edges.filter((e: any) => e.type === "conflicts_with" && (e.source === node.id || e.target === node.id)).map((e: any) => <p key={e.id}>Conflict: {e.conflict_type.replace(/_/g, " ")} ({e.severity}, {e.resolution_status.replace(/_/g, " ")})</p>)}</div>}
      </Card>
    </div>
  );
}
