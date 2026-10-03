"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import StatusBadge from "@/components/ui/StatusBadge";
import { listProcessingJobs, type ProcessingJob } from "@/lib/domain-api/processingJobs";

function tone(status: string): "success" | "critical" | "warning" | "neutral" {
  if (status === "succeeded") return "success";
  if (status === "failed") return "critical";
  if (status === "partial") return "warning";
  return "neutral";
}

export default function ProcessingDiagnosticsPage() {
  const { account, organizationSlug } = useAuth();
  const [items, setItems] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    if (!account?.is_developer || !organizationSlug) return;
    setLoading(true); setError(false);
    listProcessingJobs(organizationSlug, { limit: 200 })
      .then((response) => setItems(response.items))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [account?.is_developer, organizationSlug]);

  useEffect(load, [load]);

  if (!account?.is_developer) return <section className="cw-section"><h2>Keine Berechtigung</h2><p className="cw-muted">Dieser Bereich ist ausschließlich für den MedFlux Developer verfügbar.</p><Link href="/">Zur Übersicht</Link></section>;

  return <div className="page">
    <header className="entity-header"><h1>Dokumentverarbeitung</h1><p className="page-sub">Persistierte Processing Runs mit Provider-, OCR-, Laufzeit- und Fehlerdiagnose.</p><button type="button" className="btn btn-sm" onClick={() => void load()}>Aktualisieren</button></header>
    {error ? <InlineAlert tone="critical">Verarbeitungsläufe konnten nicht geladen werden.</InlineAlert> : null}
    {loading ? <LoadingState>Verarbeitungsläufe werden geladen…</LoadingState> : null}
    {!loading && !error ? <section className="panel"><div className="table-wrap"><table className="contract-table"><thead><tr><th>Status</th><th>Dokumentversion</th><th>Provider</th><th>OCR</th><th>Dauer</th><th>Ergebnis</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><StatusBadge label={item.status} tone={tone(item.status)} /></td><td><code>{item.document_version_id}</code></td><td>{[item.provider,item.provider_version].filter(Boolean).join(" ") || "–"}</td><td>{item.do_ocr ? [item.ocr_engine,item.ocr_engine_version].filter(Boolean).join(" ") || "aktiv" : "aus"}</td><td>{item.processing_duration != null ? `${item.processing_duration.toFixed(1)} s` : "–"}</td><td>{item.error ? <span className="text-critical">{item.error}</span> : item.message ?? `${item.success_count ?? 0} ok / ${item.failure_count ?? 0} Fehler`}</td></tr>)}</tbody></table></div>{items.length === 0 ? <p className="muted">Noch keine Verarbeitungsläufe im aktuellen Bereich.</p> : null}</section> : null}
  </div>;
}
