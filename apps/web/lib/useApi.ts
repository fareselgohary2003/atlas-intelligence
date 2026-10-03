"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

/** Loads a backend resource; null path = skip. Exposes loading/error so every view can render proper states. */
export function useApi<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api<T>(path).then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [path]);
  useEffect(() => { setData(null); load(); }, [load]);
  return { data, error, loading, reload: load };
}
