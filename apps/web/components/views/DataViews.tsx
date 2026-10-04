"use client";
import { useState } from "react";
import { useApi } from "@/lib/useApi";
import { claimLabel, tone, truncate } from "@/lib/format.mjs";
import { Card, Empty, Gate, Pill } from "../ui";
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, ExternalLink, BookOpen } from "lucide-react";
import SourceModal, { SourceInfo } from "../SourceModal";

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
  <details className="inline-block relative">
    <summary className="cursor-pointer list-none inline-flex items-center gap-1 hover:opacity-80 transition-opacity">
      <Pill tone={q.level === "HIGH" ? "ok" : q.level === "MEDIUM" ? "warn" : "muted"}>
        Quality: {q.level} ({q.total})
      </Pill>
    </summary>
    <div className="mt-1.5 min-w-[260px] rounded-lg border border-bd bg-card/95 p-2.5 shadow-lg text-[11px] text-mut space-y-1 z-10">
      <div className="font-semibold text-tx border-b border-bd/50 pb-1 flex justify-between">
        <span>Factor Breakdown</span>
        <span className="font-mono text-primary">Score: {q.total}</span>
      </div>
      {Object.entries(q.components || {}).map(([k, v]: any) => (
        <div key={k} className="flex items-start justify-between gap-2 pt-0.5">
          <span className="capitalize text-tx font-medium">{k}:</span>
          <span className="text-right text-mut">{v.score} ({v.note})</span>
        </div>
      ))}
    </div>
  </details>
);

export function ClaimsView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0), [status, setStatus] = useState(""), [open, setOpen] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<SourceInfo | null>(null);
  const q = useApi<any[]>(`/api/research/${rid}/claims?limit=${PAGE}&offset=${page * PAGE}`);
  const ev = useApi<any[]>(open ? `/api/research/${rid}/evidence?claim_id=${open}&limit=50` : null);

  return (
    <>
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
                      <p className="text-sm font-medium text-tx">{c.text}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-mut">
                        <span className="capitalize font-medium">{c.claim_type.replace(/_/g, " ")}</span>
                        {c.attributes?.value && (
                          <span className="rounded bg-surface px-1.5 py-0.5 border border-bd/60 text-tx">
                            {c.attributes.metric || "Metric"}: <strong>{c.attributes.value} {c.attributes.unit || ""}</strong>
                          </span>
                        )}
                        {c.attributes?.geography && (
                          <span className="text-mut">({c.attributes.geography})</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3"><Pill tone={tone(c.status)}>{claimLabel(c.status)}</Pill></td>
                    <td className="px-4 py-3 text-sm">{c.confidence}</td>
                    <td className="px-4 py-3 font-mono text-sm tabular-nums">{c.evidence_count}</td>
                    <td className="px-4 py-3 font-mono text-sm tabular-nums">{new Set(c.sources.map((s: any) => s.source_id)).size}</td>
                    <td className="px-4 py-3">
                      <button className="flex items-center gap-1 text-xs font-medium text-primary hover:underline" onClick={() => setOpen(open === c.id ? null : c.id)}>
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
                        <div className="mt-1 flex items-center justify-between text-[11px] text-mut">
                          <span>{e.source ? e.source.publisher : "source unavailable"}</span>
                          {e.source && (
                            <button
                              onClick={() => setSelectedSource({ id: e.source_id, ...e.source })}
                              className="inline-flex items-center gap-1 text-primary font-semibold hover:underline"
                            >
                              <BookOpen size={12} /> Read Source Document
                            </button>
                          )}
                        </div>
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
      {selectedSource && <SourceModal rid={rid} source={selectedSource} onClose={() => setSelectedSource(null)} />}
    </>
  );
}

export function EvidenceView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0), [stance, setStance] = useState("");
  const [selectedSource, setSelectedSource] = useState<SourceInfo | null>(null);
  const q = useApi<any[]>(`/api/research/${rid}/evidence?limit=${PAGE}&offset=${page * PAGE}`);

  return (
    <>
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
                  <span className="ml-auto font-mono text-[11px] text-mut">{e.agent_id} · {e.created_at.slice(0, 19).replace("T", " ")}</span>
                </div>
                <p className="mt-2 text-sm italic text-mut">"{e.excerpt}"</p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px] text-mut">
                  <div>
                    {e.source ? (
                      <button
                        onClick={() => setSelectedSource({ id: e.source_id, ...e.source })}
                        className="inline-flex items-center gap-1 font-semibold text-primary hover:underline text-left"
                      >
                        <BookOpen size={12} />
                        {truncate(e.source.title || e.source.url, 80)}
                      </button>
                    ) : "source unavailable"}
                    {" · "}{e.source?.publisher} · {e.source?.source_type}
                  </div>
                  {e.source && (
                    <button
                      onClick={() => setSelectedSource({ id: e.source_id, ...e.source })}
                      className="btn text-[11px] h-6 px-2"
                    >
                      Inspect Source
                    </button>
                  )}
                </div>
              </div>
            ))}</div>
            <Pager page={page} setPage={setPage} count={rows.length} />
          </>; 
        }}</Gate>
      </Card>
      {selectedSource && <SourceModal rid={rid} source={selectedSource} onClose={() => setSelectedSource(null)} />}
    </>
  );
}

const SOURCE_RELIABILITY: Record<string, { label: string; score: string; tone: string }> = {
  government: { label: "Official (Tier 1)", score: "0.90", tone: "ok" },
  academic: { label: "Academic (Tier 1)", score: "0.85", tone: "ok" },
  research: { label: "Research (Tier 2)", score: "0.80", tone: "ok" },
  company: { label: "Corporate (Tier 3)", score: "0.60", tone: "info" },
  news: { label: "Editorial (Tier 3)", score: "0.60", tone: "info" },
  forum: { label: "Community (Tier 4)", score: "0.30", tone: "warn" },
  other: { label: "Standard", score: "0.40", tone: "muted" },
};

export function SourcesView({ rid }: { rid: string }) {
  const [page, setPage] = useState(0);
  const [selectedSource, setSelectedSource] = useState<SourceInfo | null>(null);
  const q = useApi<any[]>(`/api/research/${rid}/sources?limit=${PAGE}&offset=${page * PAGE}`);

  return (
    <>
      <Card>
        <Gate q={q}>{(rows) => rows.length === 0 ? <Empty title="No sources" hint="Sources appear once agents retrieve pages." /> : <>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-bd bg-bg/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Publisher</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Reliability</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Retrieved</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Evidence</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-mut">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bd">{rows.map((s: any, i: number) => {
                const rel = SOURCE_RELIABILITY[s.source_type] || SOURCE_RELIABILITY.other;
                return (
                  <tr key={s.id} className="transition-colors hover:bg-bg/50 animate-fade-in" style={{ animationDelay: `${i * 20}ms` }}>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setSelectedSource(s)}
                        className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline text-left"
                      >
                        <BookOpen size={14} className="shrink-0" />
                        <span>{truncate(s.title || s.url, 75)}</span>
                      </button>
                      <div className="font-mono text-[11px] text-mut mt-0.5">{truncate(s.url, 75)}</div>
                      {s.aliases?.length > 0 && <div className="text-[11px] text-mut">{s.aliases.length} duplicate URL(s) merged</div>}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">{s.publisher}</td>
                    <td className="px-4 py-3"><Pill>{s.source_type}</Pill></td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <Pill tone={rel.tone}>{rel.label}</Pill>
                        <span className="text-[10px] text-mut font-mono">Weight: {rel.score}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs tabular-nums">{s.retrieved_at.slice(0, 10)}</td>
                    <td className="px-4 py-3 font-mono text-sm tabular-nums">{s.evidence_count}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setSelectedSource(s)}
                        className="btn text-xs font-semibold"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
          <Pager page={page} setPage={setPage} count={rows.length} />
        </>}</Gate>
      </Card>
      {selectedSource && <SourceModal rid={rid} source={selectedSource} onClose={() => setSelectedSource(null)} />}
    </>
  );
}
