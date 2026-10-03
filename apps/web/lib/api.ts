import { csrfHeaders } from "./csrf.mjs";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** All requests use the httpOnly session cookie (credentials: include); unsafe methods echo the CSRF cookie. No token is ever stored in JS. */
export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const method = (opts.method || "GET").toUpperCase();
  const r = await fetch(API + path, {
    ...opts, method, credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders(method, typeof document === "undefined" ? "" : document.cookie), ...(opts.headers || {}) },
  });
  if (r.status === 401 && !path.startsWith("/api/auth/login") && !path.startsWith("/api/auth/signup")) {
    location.href = "/login";
  }
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(typeof e.detail === "string" ? e.detail : `Request failed (${r.status})`);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

export async function download(path: string, filename: string) {
  const r = await fetch(API + path, { credentials: "include" });
  if (!r.ok) throw new Error(`Export failed (${r.status})`);
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
