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

/** Stand der Prüfung in der Kopfzeile von Dokumente: ein Fortschritt, eine Handlung – ehrlich formuliert. */
export function ReviewControl({ review, onStart, onOpenOverview }: {
  review: FieldReviewDto | null | undefined;
  onStart: (tier: FieldTier) => void;
  onOpenOverview: () => void;
}) {
  const essential = stageOf(review, "essential");
  const headline = reviewHeadline(review);
  if (!review || !essential || (essential.total === 0 && review.decisions_open === 0)) return null;
  const next = nextOpenTier(review);
  return <>
    {essential.total > 0 ? <span className="dw-progress">
      <span className="dw-progress-bar" role="progressbar" aria-label="Wesentliche Angaben entschieden" aria-valuemin={0} aria-valuemax={essential.total} aria-valuenow={essential.decided}><span style={{ width: `${(essential.decided / essential.total) * 100}%` }} /></span>
      <span>{essential.decided} von {essential.total} wesentlichen Angaben entschieden</span>
    </span> : null}
    {next
      ? <button type="button" className="btn btn-sm btn-primary dw-review" onClick={() => onStart(next)}>
        {next === "essential" ? "Wesentliches prüfen" : `${TIER_NAME[next]} prüfen`} · {stageOf(review, next)?.open}
      </button>
      : headline ? <Signal tone={headline.tone} size="sm">{headline.text}</Signal> : null}
    {next && next !== "essential" && headline ? <Signal tone={headline.tone} size="sm">{headline.text}</Signal> : null}
    <button type="button" className="btn btn-sm btn-ghost" onClick={onOpenOverview}>Übersicht</button>
  </>;
}
