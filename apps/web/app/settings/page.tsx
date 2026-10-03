"use client";
import { useState } from "react";
import Shell, { canAdmin, useSession } from "@/components/Shell";
import { Card, Gate, Pill } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const Row = ({ k, v }: { k: string; v: any }) => <div className="flex gap-3 border-b border-bd px-4 py-1.5 last:border-0"><dt className="w-56 text-mut">{k}</dt><dd className="font-mono text-[12px]">{v === null || v === undefined || v === "" ? "—" : String(v)}</dd></div>;

function Members({ wid }: { wid: string }) {
  const { ws, user } = useSession();
  const q = useApi<any[]>(`/api/workspaces/${wid}/members`);
  const [email, setEmail] = useState(""), [role, setRole] = useState("researcher"), [err, setErr] = useState("");
  const run = async (fn: () => Promise<any>) => { setErr(""); try { await fn(); q.reload(); } catch (e: any) { setErr(e.message); } };
  const admin = canAdmin(ws);
  return <Card><div className="border-b border-bd px-4 py-2 font-medium">Members and roles</div>
    <Gate q={q} rows={3}>{(ms) => <table className="w-full"><thead className="text-left text-mut"><tr><th className="px-4 py-2">Name</th><th>Email</th><th>Role</th><th></th></tr></thead>
      <tbody>{ms.map((m: any) => <tr key={m.user_id} className="border-t border-bd"><td className="px-4 py-1.5">{m.name}{m.user_id === user.id && " (you)"}</td><td>{m.email}</td>
        <td>{admin && m.role !== "owner" ? <select aria-label={`Role for ${m.name}`} className="inp w-36" value={m.role} onChange={(e) => run(() => api(`/api/workspaces/${wid}/members/${m.user_id}`, { method: "PATCH", body: JSON.stringify({ role: e.target.value }) }))}>{["admin", "researcher", "viewer"].map((r) => <option key={r}>{r}</option>)}</select> : <Pill>{m.role}</Pill>}</td>
        <td className="pr-4 text-right">{admin && m.role !== "owner" && <button className="text-red-600" onClick={() => confirm(`Remove ${m.name}?`) && run(() => api(`/api/workspaces/${wid}/members/${m.user_id}`, { method: "DELETE" }))}>Remove</button>}</td></tr>)}</tbody></table>}</Gate>
    {admin && <form className="flex flex-wrap gap-2 border-t border-bd p-3" onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/api/workspaces/${wid}/members`, { method: "POST", body: JSON.stringify({ email, role }) }); setEmail(""); }); }}>
      <input className="inp max-w-xs" type="email" required placeholder="Existing user's email" value={email} onChange={(e) => setEmail(e.target.value)} /><select className="inp w-36" value={role} onChange={(e) => setRole(e.target.value)}>{["admin", "researcher", "viewer"].map((r) => <option key={r}>{r}</option>)}</select><button className="btn-p">Add member</button></form>}
    {err && <p role="alert" className="px-4 pb-3 text-red-600">{err}</p>}</Card>;
}

function Body() {
  const { ws } = useSession();
  const q = useApi<any>(`/api/settings/config?workspace_id=${ws.id}`);
  return <div className="space-y-4">
    <Card><div className="border-b border-bd px-4 py-2 font-medium">Workspace</div><dl><Row k="Name" v={ws.name} /><Row k="Your role" v={ws.role} /></dl></Card>
    <Gate q={q} rows={6}>{(c) => <>
      {c.security.jwt_secret_is_default && <p role="alert" className="rounded border border-red-500/50 p-2 text-red-600">JWT_SECRET is still the development default. Set a long random value before any real use.</p>}
      {c.demo.demo_mode && <p className="rounded border border-amber-500/50 p-2 text-amber-700 dark:text-amber-400">DEMO_MODE is on: demo providers produce clearly labelled MOCK data.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        <Card><div className="border-b border-bd px-4 py-2 font-medium">Providers</div><dl><Row k="LLM provider" v={c.demo.llm_provider} /><Row k="LLM model" v={c.llm.model} /><Row k="LLM endpoint host" v={c.llm.endpoint_host} /><Row k="LLM API key" v={c.llm.api_key_configured ? "configured" : "not configured"} />
          <Row k="Search provider" v={c.search.provider || "not set"} /><Row k="Search API key" v={c.search.api_key_configured ? "configured" : "not configured"} /></dl></Card>
        <Card><div className="border-b border-bd px-4 py-2 font-medium">Usage and cost</div><dl><Row k="Input price / 1K tokens" v={c.pricing.input_per_1k || "not set"} /><Row k="Output price / 1K tokens" v={c.pricing.output_per_1k || "not set"} /><Row k="Cost estimates" v={c.pricing.configured ? "enabled" : "unavailable (prices not configured)"} /></dl></Card>
        <Card><div className="border-b border-bd px-4 py-2 font-medium">Security</div><dl><Row k="Secure cookies" v={c.security.cookie_secure} /><Row k="SameSite" v={c.security.cookie_samesite} /><Row k="Session lifetime (min)" v={c.security.session_ttl_minutes} /><Row k="API rate limit / min" v={c.security.api_rate_limit_per_minute} /><Row k="Rate limiter backend" v={c.security.rate_limiter} /></dl></Card>
        <Card><div className="border-b border-bd px-4 py-2 font-medium">Research</div><dl><Row k="Max replans" v={c.research.max_replans} /><Row k="Max parallel tasks" v={c.research.max_parallel_tasks} /></dl><p className="px-4 pb-3 text-[12px] text-mut">Configuration is read-only here; change it through environment variables. Secrets are never displayed.</p></Card>
      </div></>}</Gate>
    <Members wid={ws.id} /></div>;
}
export default function Page() { return <Shell title="Settings" sub="Workspace, providers, security and members"><Body /></Shell>; }
