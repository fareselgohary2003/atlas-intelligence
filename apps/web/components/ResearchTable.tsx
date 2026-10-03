"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "./Shell";
import { Bar, Card, ErrorBox, Mock, Skeleton, STATUS, StatusDot } from "./ui";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, ArrowRight } from "lucide-react";

export default function ResearchTable({ compact = false }: { compact?: boolean }) {
  const { ws } = useSession();
  const router = useRouter();
  const [d, setD] = useState<any>(null), [err, setErr] = useState("");
  const [q, setQ] = useState(""), [status, setStatus] = useState(""), [sort, setSort] = useState("-created_at"), [page, setPage] = useState(1);
  const size = compact ? 5 : 10;

  const load = useCallback(() => {
    setErr("");
    api(`/api/research?workspace_id=${ws?.id}&q=${encodeURIComponent(q)}&status=${status}&sort=${sort}&page=${page}&page_size=${size}`)
      .then(setD)
      .catch((e) => setErr(e.message));
  }, [ws?.id, q, status, sort, page, size]);

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  const th = (key: string, label: string) => (
    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">
      <button onClick={() => setSort(sort === key ? "-" + key : key)} className="flex items-center gap-1 hover:text-tx transition-colors">
        {label}
        {sort.replace("-", "") === key && <span className="text-primary">{sort[0] === "-" ? "↓" : "↑"}</span>}
      </button>
    </th>
  );

  return (
    <Card className="overflow-hidden border-bd shadow-sm">
      {!compact && (
        <div className="flex flex-wrap items-center gap-3 border-b border-bd/60 p-3.5 bg-surface/30">
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-mut" />
            <input
              className="inp pl-9 h-9 text-xs"
              placeholder="Search research briefs…"
              value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }}
            />
          </div>
          <div className="relative">
            <SlidersHorizontal size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-mut" />
            <select
              className="inp w-44 pl-9 h-9 text-xs appearance-none"
              aria-label="Filter status"
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            >
              <option value="">All statuses</option>
              {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
        </div>
      )}

      {err ? (
        <ErrorBox msg={err} retry={load} />
      ) : !d ? (
        <Skeleton />
      ) : d.items.length === 0 ? (
        <div className="py-16 text-center">
          <p className="font-semibold text-tx">{q || status ? "No research matches these filters" : "No research yet"}</p>
          {!q && !status && (
            <>
              <p className="mx-auto mt-1.5 max-w-sm text-xs text-mut">Turn complex business questions into evidence-backed intelligence.</p>
              <Link className="btn-p mt-4 inline-flex" href="/research/new">
                Start research brief
              </Link>
            </>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="border-b border-bd/70 bg-surface/50">
              <tr>
                {th("title", "Research Brief")}
                {th("status", "Status")}
                {th("progress", "Progress")}
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Sources</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Claims</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Confidence</th>
                {th("created_at", "Created")}
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-mut">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bd/60 text-sm">
              {d.items.map((r: any, i: number) => (
                <tr
                  key={r.id}
                  onClick={() => router.push("/research/" + r.id)}
                  className="group cursor-pointer transition-all duration-150 hover:bg-primary/5 active:bg-primary/10 animate-fade-in"
                  style={{ animationDelay: `${i * 30}ms` }}
                >
                  <td className="px-4 py-3.5">
                    <div className="font-semibold text-tx group-hover:text-primary transition-colors flex items-center gap-2">
                      <span>{r.title}</span>
                      {r.is_demo && <Mock />}
                    </div>
                    {r.objective && (
                      <p className="text-xs text-mut line-clamp-1 mt-0.5 max-w-md">{r.objective}</p>
                    )}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap"><StatusDot s={r.status} /></td>
                  <td className="px-4 py-3.5 whitespace-nowrap"><Bar v={r.progress} /></td>
                  <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-tx font-semibold">{r.sources_count}</td>
                  <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-tx font-semibold">{r.claims_count}</td>
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    {r.confidence ? (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{r.confidence}</span>
                    ) : <span className="text-mut text-xs">—</span>}
                  </td>
                  <td className="px-4 py-3.5 font-mono text-xs tabular-nums text-mut whitespace-nowrap">{r.created_at.slice(0, 10)}</td>
                  <td className="px-4 py-3.5 text-right whitespace-nowrap">
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary opacity-75 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all">
                      Open <ArrowRight size={12} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!compact && d && d.total > size && (
        <div className="flex items-center justify-between border-t border-bd/60 p-3.5 bg-surface/30">
          <span className="text-xs text-mut">{d.total} projects · Page {page}</span>
          <div className="flex gap-1.5">
            <button className="btn text-xs h-8" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft size={14} /> Previous
            </button>
            <button className="btn text-xs h-8" disabled={page * size >= d.total} onClick={() => setPage(page + 1)}>
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
