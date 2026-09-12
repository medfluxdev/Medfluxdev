const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 20000;

function scopedPath(path: string): string {
  if (typeof window === "undefined" || !path.startsWith("/api/")) return path;
  if (!path.includes("organization_slug=")) return path;
  const hospitalId = window.localStorage.getItem("medflux.hospitalId");
  const departmentId = window.localStorage.getItem("medflux.departmentId");
  if (!hospitalId && !departmentId) return path;
  const [base, query = ""] = path.split("?", 2);
  const params = new URLSearchParams(query);
  if (hospitalId && !params.has("hospital_id")) params.set("hospital_id", hospitalId);
  if (departmentId && !params.has("department_id")) params.set("department_id", departmentId);
  return `${base}?${params.toString()}`;
}

function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const withCredentials: RequestInit = { credentials: "include", ...init };
  if (!timeoutMs || timeoutMs <= 0) return fetch(url, withCredentials);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const outer = init.signal;
  const onOuterAbort = () => controller.abort();
  if (outer) {
    if (outer.aborted) controller.abort();
    else outer.addEventListener("abort", onOuterAbort, { once: true });
  }
  const cleanup = () => { clearTimeout(timer); if (outer) outer.removeEventListener("abort", onOuterAbort); };
  return fetch(url, { ...withCredentials, signal: controller.signal }).then((res) => { cleanup(); return res; }, (err) => { cleanup(); throw err; });
}

export async function apiGet<T>(path: string, signal?: AbortSignal, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { signal }, timeoutMs);
  if (!res.ok) { const err = new Error(`Request failed: ${res.status} ${res.statusText}`) as Error & { status?: number }; err.status = res.status; throw err; }
  return (await res.json()) as T;
}

async function errorMessage(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (text) { try { const body = JSON.parse(text) as { detail?: unknown }; if (typeof body.detail === "string" && body.detail) return body.detail; } catch {} }
  return `Request failed: ${res.status} ${res.statusText}`;
}

export async function apiPost<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
  if (!res.ok) throw new Error(await errorMessage(res));
  return (await res.json()) as T;
}
export async function apiPut<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
  if (!res.ok) throw new Error(await errorMessage(res));
  return (await res.json()) as T;
}
export async function apiPatch<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
  if (!res.ok) throw new Error(await errorMessage(res));
  return (await res.json()) as T;
}

export function contentUrl(contractId: string, documentVersionId: string, orgSlug: string): string {
  const q = new URLSearchParams({ organization_slug: orgSlug });
  const h = typeof window !== "undefined" ? window.localStorage.getItem("medflux.hospitalId") : null;
  const d = typeof window !== "undefined" ? window.localStorage.getItem("medflux.departmentId") : null;
  if (h) q.set("hospital_id", h); if (d) q.set("department_id", d);
  return `${API_BASE}/api/contracts/${encodeURIComponent(contractId)}/documents/${encodeURIComponent(documentVersionId)}/content?${q.toString()}`;
}

export async function apiUpload<T>(path: string, files: File[], slug?: string): Promise<T> {
  const form = new FormData(); for (const file of files) form.append("files", file);
  const q = new URLSearchParams(); if (slug) q.set("organization_slug", slug);
  if (typeof window !== "undefined") { const h=localStorage.getItem("medflux.hospitalId"); const d=localStorage.getItem("medflux.departmentId"); if(h)q.set("hospital_id",h); if(d)q.set("department_id",d); }
  const query = q.toString() ? `?${q.toString()}` : "";
  const res = await fetch(`${API_BASE}${path}${query}`, { method: "POST", body: form, credentials: "include" });
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export function sourceRegionUrl(documentVersionId: string, orgSlug: string, snippet: string, page: number | null): string {
  const q = new URLSearchParams({ organization_slug: orgSlug }); q.set("snippet", snippet); if (page != null) q.set("page", String(page));
  if (typeof window !== "undefined") { const h=localStorage.getItem("medflux.hospitalId"); const d=localStorage.getItem("medflux.departmentId"); if(h)q.set("hospital_id",h); if(d)q.set("department_id",d); }
  return `${API_BASE}/api/documents/${encodeURIComponent(documentVersionId)}/source-region?${q.toString()}`;
}
