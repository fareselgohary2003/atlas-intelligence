"use client";
import { useEffect, useState } from "react";
import { api, download } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, Empty, ErrorBox, Gate, Pill } from "../ui";
import { canWrite, useSession } from "../Shell";
import {
  FileDown,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Table,
  BarChart3,
  Quote,
  ExternalLink,
} from "lucide-react";
import ExecutiveReportTable from "./ExecutiveReportTable";
import ExecutiveVisualAnalytics from "./ExecutiveVisualAnalytics";
import SourceModal, { SourceInfo } from "../SourceModal";

const TONE: Record<string, string> = {
  VERIFIED: "ok",
  "PARTIALLY SUPPORTED": "warn",
  UNVERIFIED: "muted",
  CONTRADICTED: "bad",
  INFERENCE: "info",
  UNCERTAINTY: "muted",
};

export default function ReportView({ rid }: { rid: string }) {
  const { ws } = useSession();
  const versions = useApi<any[]>(`/api/research/${rid}/report/versions`);
  const [v, setV] = useState<number | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");

  useEffect(() => {
    if (versions.data?.length && v == null) setV(versions.data[0].version);
  }, [versions.data, v]);

  const rep = useApi<any>(v ? `/api/research/${rid}/report?version=${v}` : null);

  const generate = async () => {
    setBusy(true);
    setErr("");
    try {
      const r = await api(`/api/research/${rid}/report`, { method: "POST" });
      setV(r.version);
      versions.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const exp = (fmt: string) =>
    download(`/api/research/${rid}/report/export?format=${fmt}&version=${v}`, `atlas-report-v${v}.${fmt}`).catch((e) =>
      setErr(e.message)
    );

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center justify-between gap-3 p-3 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          {versions.data && versions.data.length > 0 && (
            <div className="flex items-center gap-2">
              <label htmlFor="rep-ver" className="text-xs font-medium text-mut">Version:</label>
              <select
                id="rep-ver"
                aria-label="Report version"
                className="inp h-9 w-52 text-xs font-medium"
                value={v ?? ""}
                onChange={(e) => setV(Number(e.target.value))}
              >
                {versions.data.map((x: any) => (
                  <option key={x.id} value={x.version}>
                    Version {x.version} · {x.created_at.slice(0, 16).replace("T", " ")}
                  </option>
                ))}
              </select>
            </div>
          )}
          {canWrite(ws) && (
            <button className="btn-p" disabled={busy} onClick={generate}>
              <Sparkles className="h-4 w-4" />
              {busy ? "Generating Report..." : "Generate New Version"}
            </button>
          )}
        </div>

        {v && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-mut mr-1">Export:</span>
            {["md", "json", "csv", "pdf"].map((f) => (
              <button key={f} className="btn text-xs uppercase" onClick={() => exp(f)}>
                <FileDown className="h-3.5 w-3.5" />
                {f}
              </button>
            ))}
          </div>
        )}
        {err && <span role="alert" className="w-full text-xs font-medium text-danger">{err}</span>}
      </Card>

      {versions.error ? (
        <ErrorBox msg={versions.error} retry={versions.reload} />
      ) : versions.data && versions.data.length === 0 ? (
        <Card className="p-8 text-center">
          <Empty
            title="No report compiled yet"
            hint="Generate a comprehensive report from all collected claims, sources, and verified evidence. Findings are cited with precision."
          />
        </Card>
      ) : (
        v && <Gate q={rep} rows={8}>{(r) => <Report r={r.content} rid={rid} />}</Gate>
      )}
    </div>
  );
}
function Report({ r, rid }: { r: any; rid: string }) {
  const [viewMode, setViewMode] = useState<"table" | "visuals" | "document">("table");
  const [selectedSource, setSelectedSource] = useState<SourceInfo | null>(null);

  const stats = r.stats || {};
  const byGroup = stats.by_group || {};
  const verifiedCount = byGroup.verified ?? 0;
  const totalClaims = stats.claims ?? 0;
  const totalSources = stats.sources ?? 0;
  const totalEvidence = stats.evidence ?? 0;
  const totalConflicts = stats.conflicts ?? 0;

  const citationsMap = new Map<number, any>((r.citations || []).map((c: any) => [c.n, c]));

  const Cites = ({ ns }: { ns: number[] }) => (
    <>
      {ns.map((n) => {
        const src: any = citationsMap.get(n);
        return (
          <button
            key={n}
            onClick={() =>
              setSelectedSource(
                src || {
                  n,
                  title: `Source [${n}]`,
                  url: "",
                }
              )
            }
            className="mr-1 inline-flex items-center text-xs font-semibold text-primary hover:underline hover:scale-110 transition-transform"
            title={src?.title || `Inspect Source [${n}]`}
          >
            [{n}]
          </button>
        );
      })}
    </>
  );

  return (
    <div className="space-y-6">
      <Card className="p-6 md:p-8 border-bd shadow-md">
        <header className="border-b border-bd pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-primary">
              <BookOpen className="h-3.5 w-3.5" />
              Atlas Intelligence Synthesized Report
            </div>

            {/* View Mode Switcher Tabs */}
            <div className="flex items-center gap-1 rounded-xl bg-surface p-1 border border-bd">
              <button
                onClick={() => setViewMode("table")}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  viewMode === "table"
                    ? "bg-primary text-white shadow-sm"
                    : "text-mut hover:text-tx hover:bg-bg"
                }`}
              >
                <Table className="h-3.5 w-3.5" />
                <span>Executive Tables</span>
              </button>
              <button
                onClick={() => setViewMode("visuals")}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  viewMode === "visuals"
                    ? "bg-primary text-white shadow-sm"
                    : "text-mut hover:text-tx hover:bg-bg"
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                <span>Visual Analytics</span>
              </button>
              <button
                onClick={() => setViewMode("document")}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  viewMode === "document"
                    ? "bg-primary text-white shadow-sm"
                    : "text-mut hover:text-tx hover:bg-bg"
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>Document View</span>
              </button>
            </div>
          </div>

          <h1 className="mt-3 text-2xl md:text-3xl font-bold tracking-tight text-tx break-words whitespace-normal leading-tight max-w-full">{r.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-mut">
            <span>Generated: <strong className="text-tx">{r.generated_at?.slice(0, 19).replace("T", " ")}</strong></span>
            <span>•</span>
            <span><strong className="text-tx">{totalClaims}</strong> claims</span>
            <span>•</span>
            <span><strong className="text-tx">{totalEvidence}</strong> evidence excerpts</span>
            <span>•</span>
            <span><strong className="text-tx">{totalSources}</strong> sources</span>
            <span>•</span>
            <span><strong className="text-tx">{totalConflicts}</strong> conflicts</span>
          </div>
        </header>

        {/* Executive KPI Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 my-6">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-emerald-700 dark:text-emerald-400 font-medium">
              <span>Verified Claims</span>
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-tx tracking-tight">
              {verifiedCount} <span className="text-xs font-normal text-mut">/ {totalClaims}</span>
            </div>
            <div className="mt-1 text-[11px] text-mut">
              Dual-source corroborated
            </div>
          </div>

          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-amber-700 dark:text-amber-400 font-medium">
              <span>Partially Supported</span>
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-tx tracking-tight">
              {byGroup.partial ?? 0} <span className="text-xs font-normal text-mut">/ {totalClaims}</span>
            </div>
            <div className="mt-1 text-[11px] text-mut">
              Single-source or scoped
            </div>
          </div>

          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-indigo-700 dark:text-indigo-400 font-medium">
              <span>Evidence Excerpts</span>
              <FileText className="h-4 w-4 text-indigo-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-tx tracking-tight">
              {totalEvidence}
            </div>
            <div className="mt-1 text-[11px] text-mut">
              Verbatim grounded quotes
            </div>
          </div>

          <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-blue-700 dark:text-blue-400 font-medium">
              <span>Sources Cited</span>
              <BookOpen className="h-4 w-4 text-blue-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-tx tracking-tight">
              {r.citations?.length || totalSources}
            </div>
            <div className="mt-1 text-[11px] text-mut">
              {totalSources} harvested in scope
            </div>
          </div>

          <div className="rounded-xl border border-bd bg-surface/50 p-4 flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-tx font-medium">
              <span>Conflicts Detected</span>
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-tx tracking-tight">
              {totalConflicts}
            </div>
            <div className="mt-1 text-[11px] text-mut">
              Cross-source validated
            </div>
          </div>
        </div>

        {/* Verification Policy & Partial Evidence Explanation */}
        {(byGroup.partial ?? 0) > 0 && verifiedCount === 0 && (
          <div className="mb-6 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex items-start gap-3 text-xs text-tx">
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="font-bold text-amber-700 dark:text-amber-400">
                Verification Methodology: Why are claims classified as Partially Supported?
              </div>
              <p className="text-muted-foreground text-mut leading-relaxed">
                Under Atlas Intelligence verification standards, a claim requires either (1) at least 2 independent corroborating sources, or (2) a high-authority primary source (&ge; 0.80) with direct verbatim proof. The {byGroup.partial ?? 0} claims in this report are grounded in verified source excerpts but rely on a single source or distinct market boundary definitions (e.g. cloud-native SaaS vs. managed software). Rather than artificially overstating confidence, the system honestly designates them as <strong>Partially Supported</strong> until second-source corroboration is gathered.
              </p>
            </div>
          </div>
        )}

        {/* View Mode 1: Structured Tables View */}
        {viewMode === "table" && (
          <div className="mt-6 animate-fade-in">
            <ExecutiveReportTable report={r} rid={rid} />
          </div>
        )}

        {/* View Mode 2: Visual Analytics & Charts View */}
        {viewMode === "visuals" && (
          <div className="mt-6 animate-fade-in">
            <ExecutiveVisualAnalytics report={r} />
          </div>
        )}

        {/* View Mode 3: Traditional Document Narrative View */}
        {viewMode === "document" && (
          <article className="mx-auto max-w-4xl space-y-8 text-tx animate-fade-in pt-4">
            {r.sections.map((s: any, i: number) => (
              <section key={s.key} id={s.key} className="space-y-3">
                <h2 className="text-lg font-semibold tracking-tight text-tx border-b border-bd/40 pb-1.5 flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                    {i + 1}
                  </span>
                  {s.title}
                </h2>

                {s.key === "sources" && (
                  <ol className="mb-4 space-y-2 rounded-lg bg-surface/50 p-4 border border-bd">
                    {r.citations.map((c: any) => (
                      <li key={c.n} id={`cite-${c.n}`} className="text-xs leading-relaxed text-mut flex items-start justify-between gap-2">
                        <div>
                          <span className="font-semibold text-primary">[{c.n}]</span>{" "}
                          <button
                            onClick={() => setSelectedSource(c)}
                            className="font-medium text-primary hover:underline text-left"
                          >
                            {c.title || c.url}
                          </button>{" "}
                          — <span className="text-tx font-medium">{c.publisher}</span>, {c.source_type}, retrieved {c.retrieved_at.slice(0, 10)}
                        </div>
                        <button
                          onClick={() => setSelectedSource(c)}
                          className="btn text-[11px] h-7 px-2 shrink-0 flex items-center gap-1"
                        >
                          <BookOpen className="h-3 w-3" />
                          <span>Inspect</span>
                        </button>
                      </li>
                    ))}
                  </ol>
                )}

                {s.paragraphs.map((p: any, j: number) => (
                  <p
                    key={j}
                    className={`text-sm leading-relaxed ${
                      p.kind === "gap"
                        ? "italic text-mut bg-surface/40 p-2.5 rounded border border-bd/60"
                        : p.kind === "note"
                        ? "text-xs text-mut"
                        : "text-tx/90"
                    }`}
                  >
                    {p.text}
                  </p>
                ))}

                {s.findings.map((f: any) => (
                  <div key={f.claim_id + s.key} className="my-3 rounded-lg border border-bd bg-surface/60 p-3.5 transition-all hover:border-primary/40">
                    <div className="flex flex-wrap items-center gap-2">
                      <Pill tone={TONE[f.label]}>{f.label}</Pill>
                      <Pill>{f.confidence}</Pill>
                    </div>
                    <p className="mt-2 text-sm text-tx">
                      {f.text} <Cites ns={f.citations} />
                    </p>
                    {f.rationale && <p className="mt-1.5 text-xs text-mut">{f.rationale}</p>}
                    {s.key === "claims_appendix" &&
                      f.evidence.map((e: any) => (
                        <p key={e.id} className="mt-1 text-xs text-mut/80 pl-2 border-l-2 border-bd">
                          evidence <Cites ns={[e.n]} />: “{e.excerpt}”
                        </p>
                      ))}
                  </div>
                ))}

                {(s.analysis || []).map((a: any) => (
                  <div key={a.analysis_id} className="my-3 rounded-lg border border-bd bg-surface/60 p-3.5">
                    <div className="flex items-center gap-2">
                      <Pill tone={TONE[a.label]}>{a.label}</Pill>
                    </div>
                    <p className="mt-2 text-sm text-tx">
                      {a.text} <Cites ns={a.citations} />
                    </p>
                    {a.basis.map((b: any) => (
                      <p key={b.claim_id} className="mt-1 text-xs text-mut">
                        based on ({b.label.toLowerCase()}): {b.text} <Cites ns={b.citations} />
                      </p>
                    ))}
                  </div>
                ))}

                {(s.conflicts || []).map((c: any) => (
                  <div key={c.conflict_id} className="my-3 rounded-lg border border-bd bg-surface/50 p-3.5">
                    <div className="flex gap-2">
                      <Pill tone={c.resolution_status === "explained_by_scope" ? "warn" : "bad"}>
                        {c.conflict_type.replace(/_/g, " ")}
                      </Pill>
                      <Pill>{c.severity}</Pill>
                      <Pill>{c.resolution_status.replace(/_/g, " ")}</Pill>
                    </div>
                    <p className="mt-2 text-sm font-medium text-tx">{c.explanation}</p>
                    <p className="mt-1 text-xs text-mut">
                      <strong>A:</strong> {c.claim_a.text} <Cites ns={c.claim_a.citations} />
                    </p>
                    {c.claim_b && (
                      <p className="text-xs text-mut">
                        <strong>B:</strong> {c.claim_b.text} <Cites ns={c.claim_b.citations} />
                      </p>
                    )}
                  </div>
                ))}
              </section>
            ))}
          </article>
        )}
      </Card>

      {/* Source Reader Modal */}
      {selectedSource && (
        <SourceModal
          rid={rid}
          source={selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </div>
  );
}
