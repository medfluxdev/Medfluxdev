const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Standard-Timeout damit kein Ladezustand ewig haengen kann: Bleibt der
// Backend-Request ohne Antwort (z. B. Netz/Service haengt), endet der Request
// mit einem ehrlichen Fehler-Zustand, statt in "laedt…" zu verharren.
const DEFAULT_TIMEOUT_MS = 20000;

function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const withCredentials: RequestInit = { credentials: "include", ...init };
  if (!timeoutMs || timeoutMs <= 0) {
    return fetch(url, withCredentials);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
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
  return fetch(url, { ...withCredentials, signal: controller.signal }).then(
    (res) => {
      cleanup();
      return res;
    },
    (err) => {
      cleanup();
      throw err;
    }
  );
}

export async function apiGet<T>(
  path: string,
  signal?: AbortSignal,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { signal }, timeoutMs);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function errorMessage(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (text) {
    try {
      const body = JSON.parse(text) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail) {
        return body.detail;
      }
    } catch {
      /* kein JSON-Fehlertext vorhanden */
    }
  }
  return `Request failed: ${res.status} ${res.statusText}`;
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const res = await fetchWithTimeout(
    `${API_BASE}${path}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    timeoutMs
  );
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiPut<T>(
  path: string,
  body: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const res = await fetchWithTimeout(
    `${API_BASE}${path}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    timeoutMs
  );
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return (await res.json()) as T;
}

export async function apiPatch<T>(
  path: string,
  body: unknown,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const res = await fetchWithTimeout(
    `${API_BASE}${path}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    timeoutMs
  );
  if (!res.ok) {
    throw new Error(await errorMessage(res));
  }
  return (await res.json()) as T;
}

// Sichere Content-URL fuer den lokalen PDF-Viewer. Klebt ausschliesslich an
// opaque IDs (contract_id / version_id) + org-slug; kein storage_key, kein
// Dateisystempfad. Die Bytes liefert das Backend org-/vertragsgebunden.
export function contentUrl(
  contractId: string,
  documentVersionId: string,
  orgSlug: string
): string {
  const q = new URLSearchParams({ organization_slug: orgSlug });
  return `${API_BASE}/api/contracts/${encodeURIComponent(
    contractId
  )}/documents/${encodeURIComponent(documentVersionId)}/content?${q.toString()}`;
}

export async function apiUpload<T>(
  path: string,
  files: File[],
  slug?: string
): Promise<T> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const query = slug ? `?organization_slug=${encodeURIComponent(slug)}` : "";
  const res = await fetch(`${API_BASE}${path}${query}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

// Quell-Geometrie-Endpoint: schmalste nachweisbare PDF-Region fuer ein
// Fakten-Snippet (PR-5 UAT D). Ehrlicher `status` aus dem Backend (exact /
// coarse / none) – nie erfundene Koordinaten.
export function sourceRegionUrl(
  documentVersionId: string,
  orgSlug: string,
  snippet: string,
  page: number | null
): string {
  const q = new URLSearchParams({ organization_slug: orgSlug });
  q.set("snippet", snippet);
  if (page != null) q.set("page", String(page));
  return `${API_BASE}/api/documents/${encodeURIComponent(
    documentVersionId
  )}/source-region?${q.toString()}`;
}
