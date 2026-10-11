"use client";

import { useEffect, useState } from "react";
import { getContractRegister, type ContractRegister } from "@/lib/domain-api/register";
import { formatDateTime } from "@/lib/format";

type Source = { document_version_id: string; page: number; quote: string };

/**
 * Werte, die eine Person aus einer markierten Textstelle übernommen hat („Angabe aus dem Text übernehmen“):
 * Feld, Wert, Seite und Zitat – mit Sprung zur Fundstelle. Sie stammen nicht aus der KI und brauchen keine
 * KI-Prüfung; sie stehen hier, damit Nachweise und Prüfung vollständig sind.
 */
export default function CapturedSources({ contractId, orgSlug, version, onShow, compact = false }: {
  contractId: string;
  orgSlug: string;
  /** Neu laden, wenn sich die Vertragsakte ändert. */
  version?: unknown;
  onShow: (source: Source) => void;
  compact?: boolean;
}) {
  const [register, setRegister] = useState<ContractRegister | null>(null);
  useEffect(() => {
    let active = true;
    getContractRegister(orgSlug, contractId).then((value) => { if (active) setRegister(value); }).catch(() => { if (active) setRegister(null); });
    return () => { active = false; };
  }, [contractId, orgSlug, version]);

  const items = Object.entries(register?.fields ?? {})
    .filter(([, field]) => field.document_source)
    .map(([key, field]) => ({ key, field, source: field.document_source! }));
  if (items.length === 0) return null;

  return <section className="captured-sources" aria-labelledby="captured-sources-heading">
    <h3 id="captured-sources-heading">Aus dem Text übernommen ({items.length})</h3>
    <p className="field-hint">{compact
      ? "Von einer Person aus einer markierten Textstelle übernommen – keine KI-Prüfung nötig."
      : "Von einer Person aus einer markierten Textstelle übernommen; Seite und Zitat sind gespeichert."}</p>
    <ul>{items.map(({ key, field, source }) => <li key={key}>
      <div><strong>{field.label}</strong>: {field.display ?? String(field.value ?? "–")}
        <span className="cw-muted"> · S. {source.page}{field.updated_by_name ? ` · ${field.updated_by_name}` : ""}{field.updated_at ? `, ${formatDateTime(field.updated_at)}` : ""}</span>
      </div>
      {compact ? null : <blockquote>„{source.quote}“</blockquote>}
      <button type="button" className="rg-link" onClick={() => onShow(source)} aria-label={`Fundstelle von ${field.label} zeigen (Seite ${source.page})`}>Im Dokument zeigen</button>
    </li>)}</ul>
  </section>;
}
