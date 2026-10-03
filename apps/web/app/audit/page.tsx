"use client";
import Link from "next/link";
import { useState } from "react";
import Shell, { useSession } from "@/components/Shell";
import { Card, Empty, Gate } from "@/components/ui";
import { useApi } from "@/lib/useApi";

const PAGE = 25;
function Body() {
  const { ws } = useSession();
  const [page, setPage] = useState(0), [action, setAction] = useState("");
  const q = useApi<any>(`/api/workspaces/${ws.id}/audit?limit=${PAGE}&offset=${page * PAGE}${action ? `&action=${encodeURIComponent(action)}` : ""}`);
  return (
    <Card><div className="flex gap-2 border-b border-bd p-2"><input className="inp max-w-xs" placeholder="Filter by action (e.g. REPORT_EXPORTED)" value={action} onChange={(e) => { setAction(e.target.value.trim().toUpperCase()); setPage(0); }} /></div>
      <Gate q={q}>{(d) => d.items.length === 0 ? <Empty title="No audit entries" hint={action ? "No entries match this action." : "Actions in this workspace are recorded here."} /> : <>
        <table className="w-full"><thead className="border-b border-bd text-left text-mut"><tr><th className="px-3 py-2">Time</th><th>Action</th><th>Actor</th><th>Research</th><th>Details</th></tr></thead>
          <tbody>{d.items.map((a: any) => <tr key={a.id} className="border-b border-bd align-top hover:bg-bg"><td className="px-3 py-1.5 font-mono text-[11px]">{a.created_at.slice(0, 19).replace("T", " ")}</td><td className="font-mono text-[11px]">{a.action}</td><td>{a.actor || "system"}</td>
            <td>{a.research_id ? <Link className="text-acc" href={`/research/${a.research_id}`}>open</Link> : "—"}</td><td className="font-mono text-[11px] text-mut">{Object.keys(a.meta || {}).length ? JSON.stringify(a.meta) : "—"}</td></tr>)}</tbody></table>
        <div className="flex items-center justify-between border-t border-bd p-2 text-mut"><span>{d.total} entries</span><div className="flex gap-2"><button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><button className="btn" disabled={(page + 1) * PAGE >= d.total} onClick={() => setPage(page + 1)}>Next</button></div></div></>}</Gate></Card>
  );
}
export default function Page() { return <Shell title="Audit Log" sub="Immutable record of important actions in this workspace"><Body /></Shell>; }
