"use client";
import { useState } from "react";
import Shell, { useSession } from "@/components/Shell";
import { Card, Gate, Pill, StatusDot } from "@/components/ui";
import { useApi } from "@/lib/useApi";
import { formatDuration, NO_DATA } from "@/lib/format.mjs";

function Runs({ id, wid }: { id: string; wid: string }) {
  const q = useApi<any>(`/api/agents/${id}/runs?workspace_id=${wid}&limit=10`);
  return <Gate q={q} rows={2}>{(d) => d.items.length === 0 ? <p className="p-3 text-mut">{NO_DATA}</p> : (
    <table className="w-full text-[12px]"><thead className="text-left text-mut"><tr><th className="px-3 py-1">Started</th><th>Status</th><th>Attempt</th><th>Duration</th><th>Sources</th><th>Evidence</th><th>Claims</th><th>Summary</th></tr></thead>
      <tbody>{d.items.map((r: any) => <tr key={r.id} className="border-t border-bd"><td className="px-3 py-1 font-mono">{r.started_at.slice(0, 19).replace("T", " ")}</td><td><StatusDot s={r.status === "retrying" ? "researching" : r.status} /></td><td>{r.attempt}</td>
        <td>{formatDuration(r.duration_ms == null ? null : r.duration_ms / 1000)}</td><td>{r.counts.sources}</td><td>{r.counts.evidence}</td><td>{r.counts.claims}</td><td>{r.error || r.summary || "—"}</td></tr>)}</tbody></table>)}</Gate>;
}

function Body() {
  const { ws } = useSession();
  const q = useApi<any[]>(`/api/agents?workspace_id=${ws.id}`);
  const [open, setOpen] = useState<string | null>(null);
  return <Gate q={q}>{(agents) => <div className="space-y-3">{agents.map((a: any) => (
    <Card key={a.id}><div className="p-3"><div className="flex flex-wrap items-center gap-2"><h2 className="font-medium">{a.name}</h2><span className="font-mono text-[11px] text-mut">{a.id}</span>
      {a.stats ? <><Pill>{a.stats.runs} runs</Pill>{Object.entries(a.stats.by_status).map(([k, v]: any) => <Pill key={k} tone={k === "failed" ? "bad" : k === "completed" ? "ok" : "muted"}>{v} {k}</Pill>)}<span className="text-mut">avg {formatDuration(a.stats.avg_duration_ms == null ? null : a.stats.avg_duration_ms / 1000)} · {a.stats.sources} sources · {a.stats.evidence} evidence · {a.stats.claims} claims</span></> : <span className="text-mut">{NO_DATA}</span>}
      {a.stats && <button className="ml-auto text-acc" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? "Hide runs" : "Execution history"}</button>}</div>
      <p className="mt-1 text-mut">{a.description}</p>
      <div className="mt-2 flex flex-wrap gap-1">{a.capabilities.map((c: string) => <Pill key={c} tone="info">{c.replace(/_/g, " ")}</Pill>)}</div>
      <div className="mt-1 flex flex-wrap gap-1">{a.allowed_tools.length ? a.allowed_tools.map((t: string) => <span key={t} className="rounded bg-bg px-1.5 py-0.5 font-mono text-[11px]">{t}</span>) : <span className="text-[11px] text-mut">no tools (orchestrator)</span>}</div></div>
      {open === a.id && <div className="border-t border-bd"><Runs id={a.id} wid={ws.id} /></div>}</Card>))}</div>}</Gate>;
}
export default function Page() { return <Shell title="Agents" sub="Registered agents, their permitted tools and real execution history"><Body /></Shell>; }
