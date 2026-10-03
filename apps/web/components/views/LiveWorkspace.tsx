"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { API, api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { FILTERS, eventsForTask, lastSeq, mergeEvents, reasonsByTask } from "@/lib/events.mjs";
import { currentPhase, describeEvent } from "@/lib/phase.mjs";
import { claimLabel, elapsedSeconds, formatCost, formatDuration, formatTokens, tone } from "@/lib/format.mjs";
import { Bar, Card, Empty, ErrorBox, Mock, Pill, Skeleton, StatusDot } from "../ui";
import { canWrite, useSession } from "../Shell";
import { Play, Pause, StopCircle, RotateCw, Wifi, WifiOff, Clock, Coins, Zap, RefreshCw, Sparkles, BarChart3, Network } from "lucide-react";

const FILTER_LABELS: Record<string, string> = { all: "All", tools: "Tools", sources: "Sources", claims: "Claims & evidence", verification: "Verification", conflicts: "Conflicts", replanning: "Replanning" };

function ClaimInline({ rid, claimId }: { rid: string; claimId: string }) {
  const q = useApi<any[]>(`/api/research/${rid}/claims?limit=200`);
  if (q.error) return <ErrorBox msg={q.error} />;
  const c = q.data?.find((x) => x.id === claimId);
  if (!q.data) return <Skeleton rows={2} />;
  if (!c) return <p className="text-mut">Claim not on the first page; open the Claims tab.</p>;
  return <div className="space-y-1"><div className="flex items-center gap-2"><Pill tone={tone(c.status)}>{claimLabel(c.status)}</Pill>{c.is_demo && <Mock />}</div>
    <p>{c.text}</p>{c.verification && <p className="text-mut">{c.verification.rationale}</p>}<p className="text-mut">{c.evidence_count} evidence item(s)</p></div>;
}

export default function LiveWorkspace({ rid }: { rid: string }) {
  const { ws } = useSession();
  const proj = useApi<any>(`/api/research/${rid}`), status = useApi<any>(`/api/research/${rid}/status`);
  const tasks = useApi<any[]>(`/api/research/${rid}/tasks`), usage = useApi<any>(`/api/research/${rid}/usage`);
  const [events, setEvents] = useState<any[]>([]);
  const [conn, setConn] = useState("connecting"), [streamKey, setStreamKey] = useState(0);
  const [sel, setSel] = useState<{ type: "task" | "event"; id: any } | null>(null);
  const [filter, setFilter] = useState("all"), [busy, setBusy] = useState(""), [err, setErr] = useState(""), [now, setNow] = useState(Date.now());
  const timer = useRef<any>(null), feed = useRef<HTMLDivElement>(null);

  const refresh = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { status.reload(); tasks.reload(); usage.reload(); }, 400);
  }, [status.reload, tasks.reload, usage.reload]);

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    let es: EventSource | null = null, stopped = false;
    (async () => {
      try {
        let all: any[] = [], batch: any[] = [];
        do { batch = await api<any[]>(`/api/research/${rid}/events?after_seq=${lastSeq(all)}&limit=500`); all = mergeEvents(all, batch); } while (batch.length === 500 && !stopped);
        if (stopped) return;
        setEvents((p) => mergeEvents(p, all));
        es = new EventSource(`${API}/api/research/${rid}/events/stream?after_seq=${lastSeq(all)}`, { withCredentials: true });
        es.onopen = () => setConn("live");
        es.onmessage = (m) => { const ev = JSON.parse(m.data); setEvents((p) => mergeEvents(p, [ev])); if (/^(TASK_|RESEARCH_|AGENT_|ANALYSIS_|REPLAN)/.test(ev.kind)) refresh(); };
        es.addEventListener("end", () => { es?.close(); setConn("closed"); refresh(); });
        es.onerror = () => setConn("reconnecting");  // EventSource reconnects itself and resumes from Last-Event-ID
      } catch (e: any) { setConn("error"); }
    })();
    return () => { stopped = true; es?.close(); };
  }, [rid, streamKey, refresh]);
  useEffect(() => { if (feed.current) feed.current.scrollTop = feed.current.scrollHeight; }, [events.length, filter]);

  const act = async (path: string, confirmMsg?: string) => {
    if (confirmMsg && !confirm(confirmMsg)) return;
    setBusy(path); setErr("");
    try { await api(`/api/research/${rid}/${path}`, { method: "POST" }); setStreamKey((k) => k + 1); status.reload(); tasks.reload(); proj.reload(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(""); }
  };

  if (proj.error) return <ErrorBox msg={proj.error} retry={proj.reload} />;
  if (!proj.data) return <Skeleton rows={6} />;
  const p = proj.data, st = status.data, state = st?.status || p.status;
  const phase = currentPhase(events, state), reasons = reasonsByTask(events), shown = events.filter(FILTERS[filter]);
  const taskList: any[] = tasks.data || [], u = usage.data;
  const el = elapsedSeconds(st?.started_at, st?.finished_at, now);
  const w = canWrite(ws);
  const selTask = sel?.type === "task" ? taskList.find((t) => t.id === sel.id) : null;
  const selEvent = sel?.type === "event" ? events.find((e) => e.seq === sel.id) : null;

  const ConnIcon = conn === "live" ? Wifi : WifiOff;
  const connTone = conn === "live" ? "ok" : conn === "reconnecting" || conn === "error" ? "warn" : "muted";

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <StatusDot s={state} />
          <Pill tone="info">Phase: {phase.replace("_", " ")}</Pill>
          {p.is_demo && <Mock />}
          <div className="w-44"><Bar v={st?.progress ?? p.progress} /></div>

          <div className="flex items-center gap-1.5 text-xs text-mut">
            <Clock size={12} />
            <span>{formatDuration(el)}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-mut">
            <Coins size={12} />
            <span>{u ? formatCost(u.estimated_cost, u.cost_complete) : "…"}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-mut">
            <Zap size={12} />
            <span>{u ? formatTokens(u.input_tokens + u.output_tokens, u.input_tokens + u.output_tokens > 0) : "…"}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-mut">
            <RefreshCw size={12} />
            <span>Replans {st?.replans ?? 0}</span>
          </div>

          <Pill tone={connTone}><ConnIcon size={10} className="mr-1" />{conn === "closed" ? "ended" : conn}</Pill>

          <div className="ml-auto flex gap-2">
            {w && state === "planning" && <button className="btn-p text-xs" disabled={!!busy} onClick={() => act("start")}><Play size={12} />Start</button>}
            {w && ["researching", "queued"].includes(state) && <button className="btn text-xs" disabled={!!busy || st?.control_state === "pause"} onClick={() => act("pause")}><Pause size={12} />{st?.control_state === "pause" ? "Pausing…" : "Pause"}</button>}
            {w && state === "paused" && <button className="btn-p text-xs" disabled={!!busy} onClick={() => act("resume")}><Play size={12} />Resume</button>}
            {w && ["planning", "queued", "researching", "paused"].includes(state) && <button className="btn text-xs text-red-600 dark:text-red-400 border-red-500/30 hover:border-red-500/50" disabled={!!busy || st?.control_state === "cancel"} onClick={() => act("cancel", "Cancel this research? This cannot be undone.")}><StopCircle size={12} />Cancel</button>}
          </div>
        </div>
        {state === "completed" && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-gradient-to-r from-primary/15 via-primary/5 to-transparent p-3.5 shadow-sm">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-tx">Multi-Agent Intelligence Synthesis Complete</h4>
                <p className="text-[11px] text-mut">Interactive visual charts, verification spectrums, and knowledge graph are ready.</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link href={`/research/${rid}?tab=visuals`} className="btn-p text-xs py-1.5 px-3">
                <BarChart3 className="h-3.5 w-3.5 mr-1" />
                Open Visual Charts & Table
              </Link>
              <Link href={`/research/${rid}?tab=graph`} className="btn text-xs py-1.5 px-3">
                <Network className="h-3.5 w-3.5 mr-1" />
                Knowledge Graph
              </Link>
            </div>
          </div>
        )}
        {(err || st?.error) && <p role="alert" className="mt-3 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-600 dark:text-red-400">{err || st.error}</p>}
        {state === "needs_review" && <p className="mt-3 rounded-lg bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">Some tasks failed or were skipped: results are partial. Review the plan and activity below.</p>}
        {state === "paused" && <p className="mt-3 text-sm text-mut">Paused. Pending tasks are kept; Resume continues without repeating completed work.</p>}
        {state === "cancelled" && <p className="mt-3 text-sm text-mut">Cancelled. Collected sources, evidence and claims remain available.</p>}
      </Card>

      {/* Three-column layout */}
      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)_340px]">
        {/* Research plan */}
        <Card className="max-h-[70vh] overflow-auto" aria-label="Research plan">
          <div className="sticky top-0 z-10 border-b border-bd bg-card/90 backdrop-blur px-4 py-3 font-semibold text-sm">Research plan</div>
          {tasks.error ? <ErrorBox msg={tasks.error} retry={tasks.reload} /> : !tasks.data ? <Skeleton rows={5} /> : taskList.length === 0 ? <Empty title="No plan yet" hint={state === "planning" ? "Start the research to generate a plan." : "Waiting for the Research Manager."} /> :
            <div className="divide-y divide-bd">
              {taskList.map((t, i) => (
                <button key={t.id} onClick={() => setSel({ type: "task", id: t.id })}
                  className={`block w-full px-4 py-3 text-left transition-colors hover:bg-bg/50 animate-fade-in ${sel?.id === t.id && sel.type === "task" ? "bg-bg border-l-2 border-l-acc" : ""}`}
                  style={{ animationDelay: `${i * 30}ms` }}>
                  <div className="flex items-center gap-2">
                    <StatusDot s={t.status} />
                    <span className="ml-auto rounded-full bg-bg px-2 py-0.5 font-mono text-[10px] text-mut">{t.agent}</span>
                  </div>
                  <div className="mt-1 text-sm font-medium">{t.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-mut">
                    {t.depends_on?.length > 0 && <span>after {t.depends_on.join(", ")}</span>}
                    {t.attempts > 1 && <span>attempt {t.attempts}</span>}
                    {reasons[t.id] && <Pill tone="warn">{reasons[t.id]}</Pill>}
                    {t.confidence && <Pill>{t.confidence}</Pill>}
                  </div>
                </button>
              ))}
            </div>}
        </Card>

        {/* Live activity */}
        <Card className="flex max-h-[70vh] flex-col" aria-label="Live agent activity">
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-1.5 border-b border-bd bg-card/90 backdrop-blur px-4 py-3">
            <span className="mr-2 text-sm font-semibold">Live activity</span>
            {Object.keys(FILTERS).map((k) => (
              <button key={k} onClick={() => setFilter(k)}
                className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-all ${filter === k ? "bg-acc/10 text-acc border border-acc/30" : "text-mut hover:bg-bg border border-transparent"}`}>
                {FILTER_LABELS[k]}
              </button>
            ))}
          </div>
          <div ref={feed} className="flex-1 overflow-auto font-mono text-[12px]" role="log" aria-live="polite">
            {shown.length === 0 ? (
              <div className="p-8 text-center font-sans text-mut">
                {events.length === 0 ? (state === "planning" ? "No activity yet. Start the research to see agents work." : "No events recorded yet.") : "No events match this filter."}
              </div>
            ) : (
              <div className="divide-y divide-bd/50">
                {shown.map((e) => (
                  <button key={e.seq} onClick={() => setSel({ type: "event", id: e.seq })}
                    className={`flex w-full gap-2.5 px-4 py-2 text-left transition-colors hover:bg-bg/50 ${sel?.type === "event" && sel.id === e.seq ? "bg-bg" : ""} ${/FAILED|CANCEL/.test(e.kind) ? "text-red-600 dark:text-red-400" : /CONFLICT|GAP|REPLAN/.test(e.kind) ? "text-amber-700 dark:text-amber-400" : ""}`}>
                    <span className="shrink-0 text-mut tabular-nums">{String(e.ts).slice(11, 19)}</span>
                    <span className="font-sans text-sm">{describeEvent(e)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Details panel */}
        <Card className="max-h-[70vh] overflow-auto" aria-label="Details">
          <div className="sticky top-0 z-10 border-b border-bd bg-card/90 backdrop-blur px-4 py-3 text-sm font-semibold">Details</div>
          <div className="space-y-3 p-4">
            {!sel && <p className="text-center text-sm text-mut py-8">Select a task or event to inspect it.</p>}
            {selTask && <>
              <div><div className="flex items-center gap-2"><StatusDot s={selTask.status} /><Pill>{selTask.agent}</Pill></div><p className="mt-2 font-semibold">{selTask.title}</p></div>
              <dl className="grid grid-cols-2 gap-2 rounded-lg bg-bg/50 p-3 text-xs">
                <dt className="text-mut">Attempts</dt><dd className="font-mono">{selTask.attempts}</dd>
                <dt className="text-mut">Confidence</dt><dd>{selTask.confidence || "—"}</dd>
                <dt className="text-mut">Depends on</dt><dd>{selTask.depends_on?.join(", ") || "—"}</dd>
                <dt className="text-mut">Reason</dt><dd>{reasons[selTask.id] || "—"}</dd>
              </dl>
              {selTask.summary && <p className="text-sm">{selTask.summary}</p>}
              {selTask.error && <p className="rounded-lg border border-red-500/20 bg-red-500/5 p-2 text-sm text-red-600 dark:text-red-400">{selTask.error}</p>}
              <div><div className="mb-1 text-xs font-medium text-mut">Task activity</div>{eventsForTask(events, selTask.id).slice(-30).map((e) => <div key={e.seq} className="text-xs py-0.5">{describeEvent(e)}</div>)}</div>
            </>}
            {selEvent && <>
              <p className="font-semibold">{describeEvent(selEvent)}</p>
              <div className="font-mono text-[11px] text-mut">{selEvent.kind} · #{selEvent.seq} · {selEvent.ts}</div>
              {selEvent.claim_id && <ClaimInline rid={rid} claimId={selEvent.claim_id} />}
              <pre className="overflow-auto rounded-lg border border-bd bg-bg p-3 text-[11px] leading-relaxed">{JSON.stringify(selEvent, null, 2)}</pre>
            </>}
            <div className="flex gap-3 border-t border-bd pt-3 text-xs">
              <Link className="font-medium text-acc hover:underline" href={`/research/${rid}?tab=claims`}>Claims</Link>
              <Link className="font-medium text-acc hover:underline" href={`/research/${rid}?tab=evidence`}>Evidence</Link>
              <Link className="font-medium text-acc hover:underline" href={`/research/${rid}?tab=graph`}>Graph</Link>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
