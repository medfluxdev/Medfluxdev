const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 20000;
const UPLOAD_TIMEOUT_MS = 30 * 60 * 1000;

export class ApiError extends Error {
  status?: number;
  code: "timeout" | "network" | "http";

  constructor(message: string, options: { status?: number; code?: "timeout" | "network" | "http" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code ?? "http";
  }
}

export function userMessageForStatus(status: number): string {
  if (status === 401) return "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.";
  if (status === 403) return "Sie haben für diese Aktion keine Berechtigung.";
  if (status === 404) return "Die angeforderten Daten wurden nicht gefunden.";
  if (status === 409) return "Die Aktion konnte wegen eines Konflikts nicht abgeschlossen werden. Bitte laden Sie den aktuellen Stand neu.";
  if (status === 422) return "Die Eingaben konnten nicht verarbeitet werden. Bitte prüfen Sie Ihre Angaben.";
  if (status >= 500) return "Der Server ist momentan nicht verfügbar. Bitte versuchen Sie es erneut.";
  return "Die Anfrage konnte nicht abgeschlossen werden.";
}

function notifySessionExpired(path: string) {
  if (typeof window === "undefined" || path === "/api/auth/login" || path === "/api/auth/logout") return;
  window.dispatchEvent(new CustomEvent("medflux:session-expired"));
}

function scopedPath(path: string): string {
  if (typeof window === "undefined" || !path.startsWith("/api/")) return path;
  if (!path.includes("organization_slug=")) return path;
  const selectedOrganization = window.localStorage.getItem("medflux.organization_slug");
  const hospitalId = window.localStorage.getItem("medflux.hospitalId");
  const departmentId = window.localStorage.getItem("medflux.departmentId");
  const [base, query = ""] = path.split("?", 2);
  const params = new URLSearchParams(query);
  if (selectedOrganization) params.set("organization_slug", selectedOrganization);
  if (hospitalId && !params.has("hospital_id")) params.set("hospital_id", hospitalId);
  if (departmentId && !params.has("department_id")) params.set("department_id", departmentId);
  return `${base}?${params.toString()}`;
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const withCredentials: RequestInit = { credentials: "include", ...init };
  if (!timeoutMs || timeoutMs <= 0) {
    try {
      return await fetch(url, withCredentials);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new ApiError("Die Verbindung zum Server ist fehlgeschlagen. Bitte prüfen Sie Ihre Netzwerkverbindung.", { code: "network" });
    }
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const outer = init.signal;
  const onOuterAbort = () => controller.abort();
  if (outer) {
    if (outer.aborted) controller.abort();
    else outer.addEventListener("abort", onOuterAbort, { once: true });
  }
  const cleanup = () => {
    clearTimeout(timer);
    if (outer) outer.removeEventListener("abort", onOuterAbort);
  };

  try {
    return await fetch(url, { ...withCredentials, signal: controller.signal });
  } catch (error) {
    if (timedOut) {
      throw new ApiError("Die Anfrage hat zu lange gedauert. Bitte versuchen Sie es erneut.", { code: "timeout" });
    }
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Die Verbindung zum Server ist fehlgeschlagen. Bitte prüfen Sie Ihre Netzwerkverbindung.", { code: "network" });
  } finally {
    cleanup();
  }
}

async function errorMessage(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (text) {
    try {
      const body = JSON.parse(text) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) return body.detail.trim();
    } catch {
      // Non-JSON server responses use the standardized status message below.
    }
  }
  return userMessageForStatus(res.status);
}

async function throwForResponse(res: Response, path: string): Promise<never> {
  if (res.status === 401) notifySessionExpired(path);
  throw new ApiError(await errorMessage(res), { status: res.status, code: "http" });
}

export async function apiGet<T>(path: string, signal?: AbortSignal, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { signal }, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS, signal?: AbortSignal): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal }, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  return (await res.json()) as T;
}

export async function apiPatch<T>(path: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  return (await res.json()) as T;
}

export async function apiDownload(
  path: string,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<{ blob: Blob; filename: string | null }> {
  const res = await fetchWithTimeout(`${API_BASE}${scopedPath(path)}`, {}, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  const disposition = res.headers.get("content-disposition");
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const simple = disposition?.match(/filename="?([^";]+)"?/i)?.[1];
  const filename = encoded ? decodeURIComponent(encoded) : simple ?? null;
  return { blob: await res.blob(), filename };
}

export function contentUrl(contractId: string, documentVersionId: string, orgSlug: string): string {
  const selected = typeof window !== "undefined" ? window.localStorage.getItem("medflux.organization_slug") : null;
  const q = new URLSearchParams({ organization_slug: selected || orgSlug });
  const h = typeof window !== "undefined" ? window.localStorage.getItem("medflux.hospitalId") : null;
  const d = typeof window !== "undefined" ? window.localStorage.getItem("medflux.departmentId") : null;
  if (h) q.set("hospital_id", h);
  if (d) q.set("department_id", d);
  return `${API_BASE}/api/contracts/${encodeURIComponent(contractId)}/documents/${encodeURIComponent(documentVersionId)}/content?${q.toString()}`;
}

export async function apiUpload<T>(
  path: string,
  files: File[],
  slug?: string,
  timeoutMs: number = UPLOAD_TIMEOUT_MS,
  fields?: Record<string, string | string[] | null | undefined>,
): Promise<T> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  for (const [key, value] of Object.entries(fields ?? {})) {
    if (Array.isArray(value)) value.forEach((item) => form.append(key, item));
    else if (value) form.append(key, value);
  }
  const selected = typeof window !== "undefined" ? localStorage.getItem("medflux.organization_slug") : null;
  const effectiveSlug = selected || slug;
  const q = new URLSearchParams();
  if (effectiveSlug) q.set("organization_slug", effectiveSlug);
  const h = typeof window !== "undefined" ? localStorage.getItem("medflux.hospitalId") : null;
  const d = typeof window !== "undefined" ? localStorage.getItem("medflux.departmentId") : null;
  if (h) q.set("hospital_id", h);
  if (d) q.set("department_id", d);
  const query = q.toString() ? `?${q.toString()}` : "";
  const res = await fetchWithTimeout(`${API_BASE}${path}${query}`, { method: "POST", body: form }, timeoutMs);
  if (!res.ok) return throwForResponse(res, path);
  return (await res.json()) as T;
}

export function sourceRegionUrl(documentVersionId: string, orgSlug: string, snippet: string, page: number | null): string {
  const selected = typeof window !== "undefined" ? localStorage.getItem("medflux.organization_slug") : null;
  const q = new URLSearchParams({ organization_slug: selected || orgSlug });
  q.set("snippet", snippet);
  if (page != null) q.set("page", String(page));
  if (typeof window !== "undefined") {
    const h = localStorage.getItem("medflux.hospitalId");
    const d = localStorage.getItem("medflux.departmentId");
    if (h) q.set("hospital_id", h);
    if (d) q.set("department_id", d);
  }
  return `${API_BASE}/api/documents/${encodeURIComponent(documentVersionId)}/source-region?${q.toString()}`;
}
