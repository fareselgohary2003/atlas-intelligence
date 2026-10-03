"use client";
import { useEffect, useState } from "react";
import { api, download } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, Empty, ErrorBox, Gate, Mock, Pill } from "../ui";
import { canWrite, useSession } from "../Shell";
import { FileDown, FileText, Sparkles, AlertCircle, CheckCircle2, Info, BookOpen } from "lucide-react";

const TONE: Record<string, string> = {
  VERIFIED: "ok",
  "PARTIALLY SUPPORTED": "warn",
  UNVERIFIED: "muted",
  CONTRADICTED: "bad",
  INFERENCE: "info",
  UNCERTAINTY: "muted"
};

const Cites = ({ ns }: { ns: number[] }) => (
  <>
    {ns.map((n) => (
      <a key={n} href={`#cite-${n}`} className="mr-0.5 inline-flex items-center text-xs font-semibold text-primary hover:underline">
        [{n}]
      </a>
    ))}
  </>
);

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
            {["md", "json", "pdf"].map((f) => (
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
        v && <Gate q={rep} rows={8}>{(r) => <Report r={r.content} />}</Gate>
      )}
    </div>
  );
}

function Report({ r }: { r: any }) {
  return (
    <Card className="p-6 md:p-8 border-bd shadow-md">
      <article className="mx-auto max-w-4xl space-y-8 text-tx">
        <header className="border-b border-bd pb-5">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-primary">
            <BookOpen className="h-3.5 w-3.5" />
            Atlas Intelligence Synthesized Report
          </div>
          <h1 className="mt-2 text-2xl md:text-3xl font-bold tracking-tight text-tx">{r.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-mut">
            <span>Generated: <strong className="text-tx">{r.generated_at.slice(0, 19).replace("T", " ")}</strong></span>
            <span>•</span>
            <span><strong className="text-tx">{r.stats.claims}</strong> claims</span>
            <span>•</span>
            <span><strong className="text-tx">{r.stats.sources}</strong> sources</span>
            <span>•</span>
            <span><strong className="text-tx">{r.stats.conflicts}</strong> conflicts</span>
          </div>
          {r.provenance && (
            <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>{r.provenance}</div>
            </div>
          )}
        </header>

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
                  <li key={c.n} id={`cite-${c.n}`} className="text-xs leading-relaxed text-mut">
                    <span className="font-semibold text-primary">[{c.n}]</span>{" "}
                    <a className="font-medium text-primary hover:underline" href={c.url} target="_blank" rel="noreferrer noopener">
                      {c.title || c.url}
                    </a>{" "}
                    — <span className="text-tx font-medium">{c.publisher}</span>, {c.source_type}, retrieved {c.retrieved_at.slice(0, 10)}{" "}
                    {c.is_demo && <Mock />}
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
                  {f.is_demo && <Mock />}
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
                  {a.is_demo && <Mock />}
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
              <div key={c.conflict_id} className="my-3 rounded-lg border border-danger/30 bg-danger/5 p-3.5">
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
    </Card>
  );
}
