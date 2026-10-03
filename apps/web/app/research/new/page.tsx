"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Shell, { useSession } from "@/components/Shell";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";

function Form() {
  const { ws } = useSession(), router = useRouter();
  const [f, setF] = useState<any>({ objective: "", industry: "", geography: "", target_customer: "", time_range: "", competitors: "", depth: "deep" });
  const [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const body = { ...f, workspace_id: ws.id, competitors: f.competitors.split(",").map((s: string) => s.trim()).filter(Boolean) };
      Object.keys(body).forEach((k) => body[k] === "" && delete body[k]);
      const r = await api("/api/research", { method: "POST", body: JSON.stringify(body) });
      router.push("/research/" + r.id);
    } catch (x: any) { setErr(x.message); setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4">
      <Card className="p-4"><label className="mb-1 block font-medium">What do you need to know?</label>
        <textarea className="inp h-32" required minLength={10} placeholder="Analyze the opportunity for launching a B2B SaaS product in Saudi Arabia…" value={f.objective} onChange={set("objective")} /></Card>
      <Card className="grid gap-3 p-4 md:grid-cols-2">
        <div className="col-span-full font-medium">Research scope</div>
        {[["industry", "Industry"], ["geography", "Geography"], ["target_customer", "Target customer"], ["time_range", "Time range (e.g. 2022–2026)"]].map(([k, l]) => <input key={k} className="inp" placeholder={l} value={f[k]} onChange={set(k)} />)}
        <input className="inp md:col-span-2" placeholder="Known competitors, comma separated" value={f.competitors} onChange={set("competitors")} />
        <div className="md:col-span-2"><div className="mb-1 text-mut">Research depth</div><div className="flex gap-2">
          {[["quick", "Quick"], ["standard", "Standard"], ["deep", "Deep research"]].map(([k, l]) => <button type="button" key={k} onClick={() => setF({ ...f, depth: k })} className={`btn ${f.depth === k ? "!border-acc text-acc" : ""}`}>{l}</button>)}</div></div>
      </Card>
      {err && <p role="alert" className="text-red-600 dark:text-red-400">{err}</p>}
      <button className="btn-p" disabled={busy}>{busy ? "Saving…" : "Save research brief"}</button>
      <p className="text-xs text-mut">Plan generation and execution arrive in Phase 2. Saving now creates the project in Planning status.</p>
    </form>
  );
}
export default function Page() { return <Shell title="Start new research"><Form /></Shell>; }
