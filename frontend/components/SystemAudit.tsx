"use client";

import { useCallback, useEffect, useState } from "react";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";

type SystemAuditEvent = {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

function actionLabel(action: string): string {
  if (action === "auth.login") return "Anmeldung";
  if (action === "auth.logout") return "Abmeldung";
  return action;
}

export default function SystemAudit() {
  const [events, setEvents] = useState<SystemAuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEvents(await apiGet<SystemAuditEvent[]>("/api/audit?limit=100"));
    } catch {
      setError("System-Audit konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel" aria-labelledby="system-audit-heading" style={{ marginBottom: 18 }}>
      <div className="panel-head">
        <div>
          <h2 id="system-audit-heading">System-Audit</h2>
          <p>Authentifizierte lokale Sitzungsereignisse · append-only</p>
        </div>
      </div>
      {loading ? (
        <LoadingState>System-Audit wird geladen…</LoadingState>
      ) : error ? (
        <InlineAlert
          tone="critical"
          role="alert"
          action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}
        >
          {error}
        </InlineAlert>
      ) : events.length === 0 ? (
        <p className="evidence-empty">Noch keine authentifizierten Systemereignisse.</p>
      ) : (
        <ul className="audit-list">
          {events.map((event) => (
            <li key={event.id}>
              <span className="audit-action audit-confirm">{actionLabel(event.action)}</span>
              <span className="audit-key">{event.entity_type ?? "System"}</span>
              {event.entity_id && <span className="audit-ref">{event.entity_id}</span>}
              <time className="audit-date">{formatDate(event.created_at)}</time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
