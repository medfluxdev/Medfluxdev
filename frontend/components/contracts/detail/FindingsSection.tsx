"use client";

import { useState } from "react";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { FieldFindingDto, FieldReviewDto } from "@/lib/contract-detail-types";
import { decideFinding } from "@/lib/domain-api/contracts";
import { pluralize } from "@/lib/field-review";

const DECISION_LABEL = { linked: "Einem Feld zugeordnet", note: "Als Notiz gesichert", dismissed: "Ausgeblendet" } as const;

/**
 * „Weitere Informationen aus dem Dokument“: Funde der KI ohne offizielles Feld, mit ihrer Quelle. Nichts davon ist ein
 * Pflichtpunkt: kein Zähler der Prüfung, keine Berechnung, kein Alarm. Zuordnen (als Kandidat eines Felds), als Notiz
 * sichern oder ausblenden – jederzeit wiederherstellbar.
 */
export default function FindingsSection({ contractId, orgSlug, review, canReview, onReload, onShowPage }: {
  contractId: string;
  orgSlug: string;
  review: FieldReviewDto;
  canReview: boolean;
  onReload: () => void;
  onShowPage: (page: number | null, quote: string | null) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<Record<string, string>>({});
  const open = review.findings.filter((finding) => finding.decision === null);
  const done = review.findings.filter((finding) => finding.decision !== null);
  const targets = review.fields.filter((field) => field.kind === "extracted");

  async function act(finding: FieldFindingDto, decision: "link" | "note" | "dismiss" | "restore", success: string) {
    setBusy(finding.finding_key);
    setError(null);
    try {
      await decideFinding(contractId, orgSlug, { finding_key: finding.finding_key, decision, target_fact_key: decision === "link" ? target[finding.finding_key] : null });
      toast(success, "success");
      onReload();
    } catch (err) {
      setError(err instanceof ApiError && err.message ? err.message : "Das konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setBusy(null);
    }
  }

  if (review.findings.length === 0) return null;
  return <section className="frv-findings" aria-labelledby="frv-findings-title">
    <h3 id="frv-findings-title">Weitere Informationen aus dem Dokument<span className="count-chip" aria-label={`${open.length} offen`}>{open.length}</span></h3>
    <p className="fd-muted">Die KI hat dies gefunden, aber es gehört zu keinem Feld der Vertragsakte. Sie müssen nichts davon bestätigen; es fließt in keine Berechnung ein und zählt nicht zur Prüfung.</p>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {open.length ? <ul className="frv-finding-list">
      {open.map((finding) => <li key={finding.finding_key} className="frv-finding">
        <div className="frv-finding-head">
          <strong>{finding.label}</strong>
          {finding.consequential ? <Signal tone="info" size="sm" title="Könnte Kosten oder Fristen berühren – bitte selbst einschätzen. Es ist keine bestätigte Angabe.">Zur Einschätzung</Signal> : null}
          {finding.contact ? <Signal tone="neutral" size="sm" title="Kontaktdaten pflegen Sie am Vertragspartner (Stammdaten).">Kontakt</Signal> : null}
        </div>
        {finding.snippet ? <blockquote className="fd-quote">„{finding.snippet}“</blockquote> : null}
        <div className="frv-finding-source">
          <button type="button" className="fd-ev-page" onClick={() => onShowPage(finding.page, finding.snippet)}>{finding.page != null ? `Seite ${finding.page}` : "Ohne Seite"}</button>
          <span className="fd-muted">KI-Fund, nicht bestätigt</span>
        </div>
        {canReview ? <div className="frv-finding-actions">
          <label className="visually-hidden" htmlFor={`link-${finding.finding_key}`}>Feld für „{finding.label}“</label>
          <select id={`link-${finding.finding_key}`} value={target[finding.finding_key] ?? ""} onChange={(event) => setTarget({ ...target, [finding.finding_key]: event.target.value })}>
            <option value="">Feld wählen …</option>
            {targets.map((field) => <option key={field.fact_key} value={field.fact_key}>{field.label}</option>)}
          </select>
          <button type="button" className="btn btn-sm" disabled={busy !== null || !target[finding.finding_key]} onClick={() => void act(finding, "link", "Als Kandidat zugeordnet.")}>Als Kandidat zuordnen</button>
          <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={() => void act(finding, "note", "Als Notiz gesichert.")}>Als Notiz sichern</button>
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy !== null} onClick={() => void act(finding, "dismiss", "Ausgeblendet.")}>Ausblenden</button>
        </div> : null}
      </li>)}
    </ul> : <p className="fd-muted">Nichts offen.</p>}
    {done.length ? <details className="frv-finding-done">
      <summary>{pluralize(done.length, "bearbeitete Information", "bearbeitete Informationen")}</summary>
      <ul>{done.map((finding) => <li key={finding.finding_key}>
        <span><strong>{finding.label}</strong> – {DECISION_LABEL[finding.decision!]}{finding.target_fact_key ? ` (${review.fields.find((field) => field.fact_key === finding.target_fact_key)?.label ?? finding.target_fact_key})` : ""}{finding.decided_by ? ` · ${finding.decided_by}` : ""}</span>
        {canReview ? <button type="button" className="btn btn-ghost btn-sm" disabled={busy !== null} onClick={() => void act(finding, "restore", "Wiederhergestellt.")}>Wiederherstellen</button> : null}
      </li>)}</ul>
    </details> : null}
  </section>;
}
