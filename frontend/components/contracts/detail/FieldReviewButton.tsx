"use client";

import Popover from "@/components/ui/Popover";
import Signal from "@/components/ui/Signal";
import type { FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { STATUS_TONE, TIER_NAME, decisionFields, nextOpenTier, pluralize, reviewHeadline, stageOf } from "@/lib/field-review";

/**
 * Prüfung im Kopf der Vertragsakte (auf jedem Reiter sichtbar): die wesentlichen Entscheidungen, die noch warten.
 * Jede lässt sich direkt entscheiden (Schublade) oder in der geführten Prüfung weitergehen – derselbe Stand wie in den Karten.
 */
export default function FieldReviewButton({ review, onOpenField, onStartGuided }: {
  review: FieldReviewDto | null | undefined;
  onOpenField: (field: FieldReviewFieldDto) => void;
  onStartGuided: (tier: FieldTier) => void;
}) {
  const open = decisionFields(review, "essential");
  if (!review || open.length === 0) return null;
  const next = nextOpenTier(review) ?? "essential";
  return <Popover
    className="ai-review"
    label={<><span aria-hidden="true">✦ </span>{`Prüfung · ${open.length}`}</>}
    panelLabel="Wesentliche Entscheidungen"
    align="start"
    wide
  >
    {(close) => <div className="ai-review-panel">
      <p className="ai-review-title">{pluralize(open.length, "wesentliche Entscheidung wartet", "wesentliche Entscheidungen warten")}</p>
      <ul className="ai-review-list">
        {open.slice(0, 8).map((field) => <li key={field.fact_key}>
          <button type="button" className="rg-link" onClick={() => { close(); onOpenField(field); }}>{field.label}</button>
          <span className="evt-muted">{field.current ?? "nicht gefunden"}</span>
          <Signal tone={STATUS_TONE[field.status]} size="sm">{field.status_label}</Signal>
        </li>)}
      </ul>
      {open.length > 8 ? <p className="field-hint">… und {open.length - 8} weitere in der geführten Prüfung.</p> : null}
      <div className="ai-review-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => { close(); onStartGuided(next); }}>{TIER_NAME[next]} prüfen</button>
      </div>
      <p className="field-hint">Jede Angabe wird einmal entschieden. Belege, die denselben Wert stützen, müssen nicht einzeln bestätigt werden.</p>
    </div>}
  </Popover>;
}

const RC_ICON = <svg className="dw-rc-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" /><path d="M9 3h6v3H9z" /><path d="m9 12 1.5 1.5L13 11M9 17l1.5 1.5L13 16" /></svg>;
const RC_ARROW = <svg className="dw-rc-btn-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 12h14M13 6l6 6-6 6" /></svg>;

/** Stand der Prüfung über dem Dokument: eine Karte mit Fortschritt (Felder, nicht Nachweise) und einer Handlung – ehrlich formuliert. */
export function ReviewControl({ review, onStart }: {
  review: FieldReviewDto | null | undefined;
  onStart: (tier: FieldTier) => void;
}) {
  const essential = stageOf(review, "essential");
  const headline = reviewHeadline(review);
  if (!review || !essential || (essential.total === 0 && review.decisions_open === 0)) return null;
  const next = nextOpenTier(review);
  const open = essential.total - essential.decided;
  return <section className="dw-rc" aria-label="Vertragsprüfung">
    <div className="dw-rc-head">
      <span className="dw-rc-tile">{RC_ICON}</span>
      <span className="dw-rc-title"><strong>Vertragsprüfung</strong><span>Wesentliche Angaben</span></span>
    </div>
    {essential.total > 0 ? <div className="dw-rc-progress">
      <div className="dw-rc-line"><strong>{essential.decided} von {essential.total} geprüft</strong><span>{open} offen</span></div>
      <span className="dw-progress-bar dw-rc-bar" role="progressbar" aria-label="Wesentliche Angaben entschieden" aria-valuemin={0} aria-valuemax={essential.total} aria-valuenow={essential.decided}><span style={{ width: `${(essential.decided / essential.total) * 100}%` }} /></span>
    </div> : null}
    <div className="dw-rc-actions">
      {next
        ? <button type="button" className="btn btn-sm btn-primary dw-review" onClick={() => onStart(next)}>
          {next === "essential" ? "Prüfung starten" : `${TIER_NAME[next]} prüfen`}{RC_ARROW}
        </button>
        : headline ? <Signal tone={headline.tone} size="sm">{headline.text}</Signal> : null}
    </div>
  </section>;
}
