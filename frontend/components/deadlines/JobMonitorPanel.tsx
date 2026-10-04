"use client";

import { useCallback, useEffect, useState } from "react";
import { getJobStatus, runDailyJob, type JobStatusDto } from "@/lib/domain-api/deadlines";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" });

const COUNT_LABEL: Record<string, string> = {
  deadline_reminder: "Erinnerungen",
  deadline_overdue: "Überfällig",
  deadline_escalation: "Eskalationen",
  emails_queued: "E-Mails vorbereitet",
  emails_sent: "E-Mails gesendet",
  emails_failed: "E-Mail-Fehler",
  emails_waiting_for_smtp: "E-Mails warten auf SMTP",
  system_created: "Fristen angelegt",
  system_updated: "Fristen aktualisiert",
  system_cancelled: "Fristen entfernt",
  unassigned: "Ohne Zuständigkeit",
};

export default function JobMonitorPanel({ organizationSlug }: { organizationSlug: string }) {
  const [status, setStatus] = useState<JobStatusDto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getJobStatus(organizationSlug));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Status konnte nicht geladen werden.");
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  async function runNow() {
    setBusy(true);
    setError(null);
    try {
      setStatus(await runDailyJob(organizationSlug));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Tageslauf fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="cw-section" aria-labelledby="job-monitor-heading">
    <div className="cw-section-head">
      <div><h2 id="job-monitor-heading">Tageslauf Fristen & Erinnerungen</h2><p>Gleicht Fristen ab, erstellt Erinnerungen und versendet E-Mails.</p></div>
      <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void runNow()}>{busy ? "Läuft…" : "Jetzt ausführen"}</button>
    </div>
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {status ? <>
      <dl className="rg-fields">
        <div className="rg-field"><dt>Zeitplan</dt><dd>{status.scheduler_enabled ? `täglich ab ${status.run_hour} Uhr` : "Im Backend aus – Aufgabenplanung nutzen (python -m app.jobs.daily)"}</dd></div>
        <div className="rg-field"><dt>Letzter erfolgreicher Lauf</dt><dd>{status.last_success_at ? timestamp.format(new Date(status.last_success_at)) : "Noch keiner"}{status.stale ? <span className="cw-badge cw-badge-red">Prüfen</span> : null}</dd></div>
        <div className="rg-field"><dt>E-Mail-Versand</dt><dd>{status.smtp_configured ? "SMTP eingerichtet" : "Kein SMTP – Erinnerungen nur im Postfach"}</dd></div>
        <div className="rg-field"><dt>E-Mail-Warteschlange</dt><dd>{status.emails_pending} wartend · {status.emails_failed} fehlgeschlagen</dd></div>
      </dl>
      {status.runs.length > 0 ? <table className="rg-table mt-3">
        <thead><tr><th scope="col">Start</th><th scope="col">Auslöser</th><th scope="col">Status</th><th scope="col">Ergebnis</th></tr></thead>
        <tbody>{status.runs.map((run) => <tr key={run.id}>
          <td>{run.started_at ? timestamp.format(new Date(run.started_at)) : "–"}</td>
          <td>{run.scope === "global" ? "Zeitplan (alle)" : run.trigger === "manual" ? "Manuell" : run.trigger}</td>
          <td>{run.status === "succeeded" ? "Erfolgreich" : run.status === "failed" ? `Fehler: ${run.error ?? ""}` : "Läuft"}</td>
          <td>{Object.entries(run.counts).filter(([, value]) => value > 0).map(([key, value]) => `${COUNT_LABEL[key] ?? key}: ${value}`).join(" · ") || "–"}</td>
        </tr>)}</tbody>
      </table> : null}
    </> : <p role="status">Status wird geladen…</p>}
  </section>;
}
