"use client";

import { useState } from "react";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { FieldFindingDto, FieldReviewDto } from "@/lib/contract-detail-types";
import { decideFinding } from "@/lib/domain-api/contracts";
import { LEVEL_NAME, levelOf } from "@/lib/field-review";
import { icon } from "./ReviewParts";

const BACK = icon(<path d="m15 6-6 6 6 6" />);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);
const DOC = icon(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></>);

const DECISION_LABEL = { linked: "Einem Feld zugeordnet", note: "Im Verlauf vermerkt", dismissed: "Ausgeblendet" } as const;

/**
 * Ein Schritt der Stufe Optional: eine Weitere Information aus dem Dokument (Fund der KI ohne offizielles Feld).
 * Zuordnen (als Kandidat eines Felds), im Verlauf vermerken oder ausblenden; Weiter lässt sie unverändert.
 * Nichts davon fließt in eine Berechnung.
 */
export default function FindingPanel({ contractId, orgSlug, finding, review, canReview, position, nextLabel, headingRef, onPrev, onNext, onShowPage, onDecided }: {
  contractId: string;
  orgSlug: string;
  finding: FieldFindingDto;
  review: FieldReviewDto;
  canReview: boolean;
  position: { index: number; total: number };
  nextLabel: string | null;
  headingRef: React.RefObject<HTMLHeadingElement>;
  onPrev: () => void;
  onNext: () => void;
  onShowPage: (page: number | null, quote: string | null) => void;
  onDecided: (decision: "link" | "note" | "dismiss" | "restore", targetKey: string | null) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState("");
  const targets = review.fields.filter((field) => field.kind === "extracted");
  const groups = (["pflicht", "optional"] as const).map((level) => ({ level, fields: targets.filter((field) => levelOf(field.tier) === level) })).filter((group) => group.fields.length);

  async function act(decision: "link" | "note" | "dismiss" | "restore", success: string) {
    setBusy(true);
    setError(null);
    try {
      await decideFinding(contractId, orgSlug, { finding_key: finding.finding_key, decision, target_fact_key: decision === "link" ? target : null });
      toast(success, "success");
      onDecided(decision, decision === "link" ? target : null);
    } catch (err) {
      setError(err instanceof ApiError && err.message ? err.message : "Das konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  const decided = finding.decision !== null;
  const targetLabel = finding.target_fact_key ? review.fields.find((field) => field.fact_key === finding.target_fact_key)?.label ?? finding.target_fact_key : null;
  return <div className="vp">
    <header className="vp-head vp-head--optional">
      <div className="vp-meta">
        <span className="vp-level vp-level--optional">Optional</span>
        <span className="vp-bar" aria-hidden="true" />
        <span>Angabe {position.index + 1} von {position.total}</span>
        <span className="vp-sp" />
        <span className="vp-arrows">
          <button type="button" className="btn btn-sm vp-arrow" onClick={onPrev} disabled={position.index <= 0} aria-label="Vorherige Angabe" title="Vorherige Angabe">{BACK}</button>
          <button type="button" className="btn btn-sm vp-arrow" onClick={onNext} aria-label="Nächste Angabe" title={nextLabel ? `Nächste: ${nextLabel}` : "Nächste Angabe"}>{NEXT}</button>
        </span>
      </div>
      <div className="vp-titlerow">
        <h2 ref={headingRef} tabIndex={-1} className="vp-title">{finding.label}</h2>
        <span className="vp-chip">{decided ? <Signal tone="done" size="sm">{DECISION_LABEL[finding.decision!]}</Signal> : <Signal tone="neutral" size="sm">Weitere Information</Signal>}</span>
      </div>
    </header>

    <div className="vp-body">
      {finding.snippet ? <div className="vp-src">
        <b>{finding.page != null ? `Seite ${finding.page}` : "Ohne Seite"}</b>
        <span className="vp-quote" title={finding.snippet}>„{finding.snippet}“</span>
        <button type="button" className="vp-link" onClick={() => onShowPage(finding.page, finding.snippet)}>{DOC}Im Dokument zeigen</button>
      </div> : null}
      {finding.contact ? <p className="vp-muted">Kontaktdaten pflegen Sie am Vertragspartner (Stammdaten).</p> : null}
      {finding.consequential ? <p className="vp-muted">Könnte Kosten oder Fristen berühren – bitte selbst einschätzen.</p> : null}
      {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}

      {decided ? <div className="vp-decided">
        <span>{DECISION_LABEL[finding.decision!]}{targetLabel ? ` (${targetLabel})` : ""}{finding.decided_by ? ` · ${finding.decided_by}` : ""}</span>
        <span className="vp-sp" />
        {canReview ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => void act("restore", "Wiederhergestellt.")}>Wiederherstellen</button> : null}
      </div> : canReview ? <section className="vp-other" aria-label="Was soll mit dieser Information geschehen?">
        <p className="vp-other-title">Gehört das zu einer Angabe?</p>
        <label className="vp-field">Zu welcher Angabe hinzufügen?
          <select value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="">Angabe wählen …</option>
            {groups.map((group) => <optgroup key={group.level} label={LEVEL_NAME[group.level]}>
              {group.fields.map((field) => <option key={field.fact_key} value={field.fact_key}>{field.label}</option>)}
            </optgroup>)}
          </select>
        </label>
        <div className="vp-finding-actions">
          <button type="button" className="btn btn-primary btn-sm vp-finding-link" disabled={busy || !target} onClick={() => void act("link", "Zur Angabe hinzugefügt – bitte dort prüfen.")}>Zur Angabe hinzufügen und prüfen</button>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void act("note", "Im Verlauf vermerkt.")}>Im Verlauf vermerken</button>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void act("dismiss", "Ausgeblendet.")}>Ausblenden</button>
        </div>
      </section> : <p className="vp-muted">Nur Lesen – entscheiden dürfen Prüfende und das Vertragsmanagement.</p>}
    </div>

    <footer className="vp-foot">
      <div className="vp-actions">
        <div className="vp-foot-row">
          <button type="button" className="btn vp-arrow" onClick={onPrev} disabled={position.index <= 0} aria-label="Zur vorherigen Angabe" title="Vorherige Angabe">{BACK}</button>
          <button type="button" className="btn btn-primary vp-primary" onClick={onNext}>Weiter</button>
          <button type="button" className="btn vp-arrow" onClick={onNext} aria-label="Zur nächsten Angabe" title={nextLabel ? `Nächste: ${nextLabel}` : "Nächste Angabe"}>{NEXT}</button>
        </div>
      </div>
    </footer>
  </div>;
}
