"use client";
import { useState } from "react";
import { useApi } from "@/lib/useApi";
import { claimLabel, tone, truncate } from "@/lib/format.mjs";
import { Card, Empty, Gate, Mock, Pill } from "../ui";
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

const PAGE = 25;
function Pager({ page, setPage, count }: { page: number; setPage: (n: number) => void; count: number }) {
  return (
    <div className="flex items-center justify-between border-t border-bd p-3 text-sm text-mut">
      <span>Page {page + 1}</span>
      <div className="flex gap-1.5">
        <button className="btn text-xs" disabled={page === 0} onClick={() => setPage(page - 1)}><ChevronLeft size={14} /> Previous</button>
        <button className="btn text-xs" disabled={count < PAGE} onClick={() => setPage(page + 1)}>Next <ChevronRight size={14} /></button>
      </div>
    </div>
  );
}

const Quality = ({ q }: { q: any }) => !q?.level ? null : (
  <details className="inline">
    <summary className="cursor-pointer"><Pill tone={q.level === "HIGH" ? "ok" : q.level === "MEDIUM" ? "warn" : "muted"}>quality {q.level} ({q.total})</Pill></summary>
    <ul className="mt-1 text-[11px] text-mut">{Object.entries(q.components || {}).map(([k, v]: any) => <li key={k}>{k}: {v.score} — {v.note}</li>)}</ul>
  </details>
);

export function ClaimsView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0), [status, setStatus] = useState(""), [open, setOpen] = useState<string | null>(null);
  const q = useApi<any[]>(`/api/research/${rid}/claims?limit=${PAGE}&offset=${page * PAGE}`);
  const ev = useApi<any[]>(open ? `/api/research/${rid}/evidence?claim_id=${open}&limit=50` : null);
  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-bd p-3">
        <select aria-label="Filter status" className="inp w-52" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["supported", "partially_supported", "contradicted", "insufficient_evidence", "proposed"].map((s) => <option key={s} value={s}>{claimLabel(s)}</option>)}
        </select>
      </div>
      <Gate q={q}>{(rows) => {
        const list = rows.filter((c: any) => !status || c.status === status);
        return list.length === 0 ? <Empty title="No claims" hint={status ? "No claims with this status on this page." : "Claims appear once agents have extracted evidence."} /> : <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-bd bg-bg/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Claim</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Confidence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Evidence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Sources</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bd">{list.map((c: any) => (<>
                <tr key={c.id} className="transition-colors hover:bg-bg/50">
                  <td className="px-4 py-3">
                    <p className="text-sm">{c.text}</p>
                    {c.is_demo && <span className="ml-1"><Mock /></span>}
                    <div className="mt-0.5 text-[11px] text-mut">{c.claim_type.replace(/_/g, " ")}</div>
                  </td>
                  <td className="px-4 py-3"><Pill tone={tone(c.status)}>{claimLabel(c.status)}</Pill></td>
                  <td className="px-4 py-3 text-sm">{c.confidence}</td>
                  <td className="px-4 py-3 font-mono text-sm tabular-nums">{c.evidence_count}</td>
                  <td className="px-4 py-3 font-mono text-sm tabular-nums">{new Set(c.sources.map((s: any) => s.source_id)).size}</td>
                  <td className="px-4 py-3">
                    <button className="flex items-center gap-1 text-xs font-medium text-acc hover:underline" onClick={() => setOpen(open === c.id ? null : c.id)}>
                      {open === c.id ? <><ChevronUp size={12} />Hide</> : <><ChevronDown size={12} />Inspect</>}
                    </button>
                  </td>
                </tr>
                {open === c.id && <tr key={c.id + "d"} className="bg-bg/30"><td colSpan={6} className="px-4 py-4">
                  {c.verification ? (
                    <div className="mb-3 rounded-lg border border-bd bg-card p-3">
                      <div className="text-xs font-semibold text-mut mb-1">Verification ({c.verification.verifier})</div>
                      <p className="text-sm">{c.verification.rationale}</p>
                      <p className="mt-1 text-[11px] text-mut">independent supporting: {c.verification.factors?.independent_supporting ?? 0} · contradicting: {c.verification.factors?.independent_contradicting ?? 0}{c.verification.factors?.freshness ? ` · ${c.verification.factors.freshness}` : ""}</p>
                    </div>
                  ) : <p className="mb-3 text-sm text-mut">Not verified yet.</p>}
                  <Gate q={ev} rows={2}>{(items) => items.length === 0 ? <p className="text-mut">No evidence linked.</p> : items.map((e: any) => (
                    <div key={e.id} className="mb-2 rounded-lg border border-bd p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Pill tone={e.stance === "contradicts" ? "bad" : "ok"}>{e.stance}</Pill>
                        <Quality q={e.quality} />
                      </div>
                      <p className="mt-1.5 text-sm italic text-mut">"{e.excerpt}"</p>
                      <div className="mt-1 text-[11px] text-mut">{e.source ? <a className="inline-flex items-center gap-1 text-acc hover:underline" href={e.source.url} target="_blank" rel="noreferrer noopener">{truncate(e.source.title || e.source.url, 80)}<ExternalLink size={10} /></a> : "source unavailable"} · {e.source?.publisher}</div>
                    </div>
                  ))}</Gate>
                </td></tr>}
              </>))}</tbody>
            </table>
          </div>
          <Pager page={page} setPage={setPage} count={rows.length} />
        </>; 
      }}</Gate>
    </Card>
  );
}

export function EvidenceView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0), [stance, setStance] = useState("");
  const q = useApi<any[]>(`/api/research/${rid}/evidence?limit=${PAGE}&offset=${page * PAGE}`);
  return (
    <Card>
      <div className="border-b border-bd p-3">
        <select aria-label="Filter stance" className="inp w-48" value={stance} onChange={(e) => setStance(e.target.value)}>
          <option value="">All stances</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option>
        </select>
      </div>
      <Gate q={q}>{(rows) => {
        const list = rows.filter((e: any) => !stance || e.stance === stance);
        return list.length === 0 ? <Empty title="No evidence" hint="Evidence excerpts appear once agents have saved sources." /> : <>
          <div className="divide-y divide-bd">{list.map((e: any, i: number) => (
            <div key={e.id} className="p-4 transition-colors hover:bg-bg/30 animate-fade-in" style={{ animationDelay: `${i * 20}ms` }}>
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone={e.stance === "contradicts" ? "bad" : "ok"}>{e.stance}</Pill>
                <Quality q={e.quality} />
                <Pill tone={e.location?.basis === "unverified" ? "warn" : "ok"}>{e.location?.basis === "unverified" ? "grounding unchecked" : "grounded in source text"}</Pill>
                {e.is_demo && <Mock />}
                <span className="ml-auto font-mono text-[11px] text-mut">{e.agent_id} · {e.created_at.slice(0, 19).replace("T", " ")}</span>
              </div>
              <p className="mt-2 text-sm italic text-mut">"{e.excerpt}"</p>
              <div className="mt-1.5 text-[12px] text-mut">{e.source ? <>
                <a className="inline-flex items-center gap-1 text-acc hover:underline" href={e.source.url} target="_blank" rel="noreferrer noopener">{truncate(e.source.title || e.source.url, 90)}<ExternalLink size={10} /></a>
                {" · "}{e.source.publisher} · {e.source.source_type} · retrieved {e.source.retrieved_at.slice(0, 10)}
              </> : "source unavailable"}</div>
            </div>
          ))}</div>
          <Pager page={page} setPage={setPage} count={rows.length} />
        </>; 
      }}</Gate>
    </Card>
  );
}

export function SourcesView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0);
  const q = useApi<any[]>(`/api/research/${rid}/sources?limit=${PAGE}&offset=${page * PAGE}`);
  return (
    <Card>
      <Gate q={q}>{(rows) => rows.length === 0 ? <Empty title="No sources" hint="Sources appear once agents retrieve pages." /> : <>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-bd bg-bg/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Source</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Publisher</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Retrieved</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Evidence</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Claims</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bd">{rows.map((s: any, i: number) => (
              <tr key={s.id} className="transition-colors hover:bg-bg/50 animate-fade-in" style={{ animationDelay: `${i * 20}ms` }}>
                <td className="px-4 py-3">
                  <a className="inline-flex items-center gap-1 text-sm font-medium text-acc hover:underline" href={s.url} target="_blank" rel="noreferrer noopener">
                    {truncate(s.title || s.url, 80)}<ExternalLink size={10} />
                  </a>
                  {s.is_demo && <span className="ml-1"><Mock /></span>}
                  <div className="font-mono text-[11px] text-mut">{truncate(s.url, 80)}</div>
                  {s.aliases?.length > 0 && <div className="text-[11px] text-mut">{s.aliases.length} duplicate URL(s) merged</div>}
                </td>
                <td className="px-4 py-3 text-sm">{s.publisher}</td>
                <td className="px-4 py-3"><Pill>{s.source_type}</Pill></td>
                <td className="px-4 py-3 font-mono text-xs tabular-nums">{s.retrieved_at.slice(0, 10)}</td>
                <td className="px-4 py-3 font-mono text-sm tabular-nums">{s.evidence_count}</td>
                <td className="px-4 py-3 font-mono text-sm tabular-nums">{s.claim_count}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <Pager page={page} setPage={setPage} count={rows.length} />
      </>}</Gate>
    </Card>
  );
}
