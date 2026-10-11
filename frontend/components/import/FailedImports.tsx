"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { retryDocument } from "@/lib/domain-api/documents";
import { listProcessingJobs, type ProcessingJob } from "@/lib/domain-api/processingJobs";
import { formatDate } from "@/lib/format";

// Fehlgeschlagene Importe der eigenen Organisation (sichtbarer Bereich), mit verständlicher Meldung.
// Technische Rohtexte liefert das Backend nur Administration/Entwicklung; hier gilt result_label_de.
export default function FailedImports({ organizationSlug }: { organizationSlug: string }) {
  const toast = useToast();
  const [items, setItems] = useState<ProcessingJob[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = useCallback(() => {
    listProcessingJobs(organizationSlug, { status: ["failed"], limit: 50 })
      .then((data) => {
        // Je Dokumentversion nur der jüngste Lauf; schon erfolgreich wiederholte Läufe fallen heraus.
        const latest = new Map<string, ProcessingJob>();
        for (const job of data.items) if (!latest.has(job.document_version_id)) latest.set(job.document_version_id, job);
        setItems(Array.from(latest.values()));
        setFailed(false);
      })
      .catch(() => { setItems(null); setFailed(true); });
  }, [organizationSlug]);

  useEffect(load, [load]);

  async function retry(job: ProcessingJob) {
    setRetrying(job.document_version_id);
    try {
      const result = await retryDocument(job.document_version_id, organizationSlug);
      const ok = result.analysis_status === "success" || result.status === "imported";
      toast(ok ? "Analyse erneut erfolgreich." : "Analyse erneut fehlgeschlagen.", ok ? "success" : "error");
      load();
    } catch {
      toast("Die erneute Analyse konnte nicht gestartet werden.", "error");
    } finally {
      setRetrying(null);
    }
  }

  if (failed) return <InlineAlert tone="warning" action={<Button size="sm" onClick={load}>Erneut laden</Button>}>Fehlgeschlagene Importe konnten nicht geladen werden.</InlineAlert>;
  if (!items || items.length === 0) return null;

  return <section className="card card-pad stack-4" aria-labelledby="failed-imports">
    <h2 id="failed-imports">Fehlgeschlagene Importe ({items.length})</h2>
    <p className="field-hint">Das Original ist gespeichert. Die Analyse kann erneut gestartet werden, z. B. nachdem die lokale KI wieder bereit ist.</p>
    <ul className="result-list">
      {items.map((job) => <li key={job.id} className="result-row">
        <span className="result-file">{job.original_filename ?? "Dokument"}</span>
        <span className="result-state-stack">
          <Signal tone="critical">{job.result_label_de ?? "Verarbeitung fehlgeschlagen."}</Signal>
          {job.created_at ? <span className="field-hint">{formatDate(job.created_at)}</span> : null}
        </span>
        <span className="btn-group">
          <Button size="sm" loading={retrying === job.document_version_id} disabled={retrying !== null} onClick={() => void retry(job)}>Analyse erneut starten</Button>
          {job.contract_id ? <Link className="result-link" href={`/contracts/${job.contract_id}?tab=documents&subtab=document`}>Dokument im Vertrag ansehen</Link> : null}
        </span>
      </li>)}
    </ul>
  </section>;
}
