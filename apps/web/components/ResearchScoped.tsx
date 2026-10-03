"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, Empty, Gate } from "./ui";
import { useSession } from "./Shell";
import { useApi } from "@/lib/useApi";

/** Workspace-level pages (Evidence, Claims, Sources, Reports): pick a research project, then render the per-research view. */
export default function ResearchScoped({ render }: { render: (rid: string) => React.ReactNode }) {
  const { ws } = useSession();
  const list = useApi(`/api/research?workspace_id=${ws.id}&page_size=50&sort=-created_at`);
  const [rid, setRid] = useState("");
  useEffect(() => {
    if (!list.data?.items?.length) return;
    const saved = localStorage.getItem("atlas_last_research");  // UI preference only
    setRid(list.data.items.find((r: any) => r.id === saved)?.id || list.data.items[0].id);
  }, [list.data]);
  return (
    <Gate q={list}>{(d) => d.items.length === 0 ? (
      <Card><Empty title="No research yet" hint="Turn complex business questions into evidence-backed intelligence."><Link href="/research/new" className="btn-p">Start research</Link></Empty></Card>
    ) : (
      <div className="space-y-4">
        <div className="flex items-center gap-2"><label className="text-mut" htmlFor="rs">Research</label>
          <select id="rs" className="inp max-w-md" value={rid} onChange={(e) => { setRid(e.target.value); localStorage.setItem("atlas_last_research", e.target.value); }}>
            {d.items.map((r: any) => <option key={r.id} value={r.id}>{r.title}{r.is_demo ? " [MOCK]" : ""}</option>)}</select>
          {rid && <Link href={`/research/${rid}`} className="text-acc">Open workspace</Link>}</div>
        {rid && <div key={rid}>{render(rid)}</div>}
      </div>)}</Gate>
  );
}
