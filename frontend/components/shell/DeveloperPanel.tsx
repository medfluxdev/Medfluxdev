"use client";

import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import Drawer from "@/components/ui/Drawer";
import { clearRequestLog, getRequestLog, subscribeRequestLog } from "@/lib/request-log";

const EMPTY: ReturnType<typeof getRequestLog> = [];

function readScope(key: string) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}

// U5 Entwicklermodus: Seitenkontext und die letzten API-Anfragen mit Dauer.
export default function DeveloperPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { account, role, organizationSlug, previewOf } = useAuth();
  const log = useSyncExternalStore(subscribeRequestLog, getRequestLog, () => EMPTY);
  const slow = log.filter((entry) => entry.ms >= 1000).length;
  const average = log.length ? Math.round(log.reduce((sum, entry) => sum + entry.ms, 0) / log.length) : 0;

  return (
    <Drawer open={open} title="Entwicklerdetails" onClose={onClose} actions={<button type="button" className="btn btn-sm" onClick={clearRequestLog}>Protokoll leeren</button>}>
      <dl className="dev-context">
        <dt>Seite</dt><dd><code>{pathname}</code></dd>
        <dt>Organisation</dt><dd><code>{organizationSlug ?? "–"}</code></dd>
        <dt>Rolle</dt><dd>{role ?? "–"}{previewOf ? ` (Vorschau, echt: ${previewOf})` : ""}</dd>
        <dt>Krankenhaus / Bereich</dt><dd><code>{open ? readScope("medflux.hospitalId") ?? "–" : ""}</code> / <code>{open ? readScope("medflux.departmentId") ?? "–" : ""}</code></dd>
        <dt>Konto</dt><dd>{account?.email ?? "–"}{account?.is_developer ? " · Entwickler" : ""}</dd>
      </dl>
      <h3 className="dev-heading">API-Anfragen</h3>
      <p className="field-hint">{log.length} Anfragen · Durchschnitt {average} ms · {slow} langsamer als 1 s. Nur Pfade und Zeiten, keine Inhalte.</p>
      {log.length === 0 ? <p className="field-hint">Noch keine Anfragen aufgezeichnet.</p> : (
        <table className="data-table dev-log">
          <thead><tr><th scope="col">Methode</th><th scope="col">Pfad</th><th scope="col">Status</th><th scope="col">Dauer</th></tr></thead>
          <tbody>
            {log.map((entry) => (
              <tr key={entry.id} className={entry.ms >= 1000 || entry.status === "Fehler" || (typeof entry.status === "number" && entry.status >= 400) ? "is-flagged" : undefined}>
                <td>{entry.method}</td><td><code>{entry.path}</code></td><td>{entry.status}</td><td>{entry.ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Drawer>
  );
}
