// U5 Entwicklermodus: Zeiten der letzten API-Anfragen, nur im Speicher dieses Tabs.
// Gespeichert wird nur Methode, Pfad (ohne Suchparameter), Status und Dauer – keine Inhalte.

export interface RequestLogEntry {
  id: number;
  method: string;
  path: string;
  status: number | "Fehler";
  ms: number;
  at: number;
}

const LIMIT = 100;
let entries: RequestLogEntry[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

export function recordRequest(method: string, url: string, status: number | "Fehler", ms: number) {
  let path = url;
  try {
    path = new URL(url, "http://local").pathname;
  } catch { /* Pfad unveraendert */ }
  entries = [{ id: nextId++, method, path, status, ms: Math.round(ms), at: Date.now() }, ...entries].slice(0, LIMIT);
  listeners.forEach((listener) => listener());
}

export function getRequestLog(): RequestLogEntry[] {
  return entries;
}

export function clearRequestLog() {
  entries = [];
  listeners.forEach((listener) => listener());
}

export function subscribeRequestLog(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
