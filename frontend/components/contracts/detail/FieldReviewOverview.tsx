"use client";

import { useState } from "react";
import Signal from "@/components/ui/Signal";
import type { ContractDetailResponse, FieldEvidenceDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import {
  STATUS_TONE, TIER_HINT, TIER_NAME, TIER_ORDER, fieldsOf, nextOpenTier, pluralize, reviewHeadline, stageOf,
} from "@/lib/field-review";
import FieldDecisionDrawer from "./FieldDecisionDrawer";
import FindingsSection from "./FindingsSection";

/**
 * Dokumente → Prüfung: der Überblick über die Feldprüfung. Zeigt je Stufe, wie viele *Angaben* (nicht Nachweise) eine
 * Entscheidung brauchen, startet die geführte Prüfung und öffnet jede Angabe in derselben Entscheidungsansicht wie die
 * Karte. Berechnete Werte stehen getrennt, Weitere Informationen aus dem Dokument am Ende.
 */
export default function FieldReviewOverview({
  data, orgSlug, canReview, focusKey, onReload, onStartGuided, onShowEvidence, onShowPage, onOpenAnalysis,
}: {
  data: ContractDetailResponse;
  orgSlug: string;
  canReview: boolean;
  /** Diese Angabe gleich öffnen (Klick auf eine KI-Plakette); `n` ändert sich bei jedem Klick. */
  focusKey?: { key: string; n: number } | null;
  onReload: () => void;
  onStartGuided: (tier: FieldTier, key?: string | null) => void;
  onShowEvidence: (evidence: FieldEvidenceDto) => void;
  onShowPage: (page: number | null, quote: string | null) => void;
  onOpenAnalysis?: () => void;
}) {
  const review = data.field_review;
  const [opened, setOpened] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState<number | null>(null);
  if (focusKey && focusKey.n !== seenFocus) { setSeenFocus(focusKey.n); setOpened(focusKey.key); }

  if (!review) return <section className="detail-card frv" aria-label="Prüfung"><h2>Prüfung</h2><p className="fd-muted">Für diesen Vertrag liegt noch keine Prüfung vor.</p></section>;

  const headline = reviewHeadline(review);
  const firstOpen = nextOpenTier(review);
  const calculated = review.fields.filter((field) => field.kind === "calculated" && field.present);
  const notFound = review.fields.filter((field) => field.kind === "extracted" && !field.present && !field.decision_needed && field.status !== "absent");
  const open = (field: FieldReviewFieldDto) => setOpened(field.fact_key);

  return <section id="field-review-panel" className="detail-card frv" aria-labelledby="frv-title">
    <div className="frv-head">
      <div>
        <h2 id="frv-title">Prüfung</h2>
        <p className="fd-muted">Hier stehen die Angaben der Vertragsakte, über die Sie entscheiden. Jede Angabe wird einmal entschieden – Belege, die denselben Wert stützen, zählen nicht einzeln.</p>
      </div>
      {headline ? <Signal tone={headline.tone}>{headline.text}</Signal> : null}
    </div>

    <ol className="frv-stages">
      {TIER_ORDER.map((tier) => {
        const stage = stageOf(review, tier);
        if (!stage) return null;
        const pct = stage.total ? Math.round((stage.decided / stage.total) * 100) : 0;
        return <li key={tier} className={`frv-stage frv-stage--${tier}`}>
          <div className="frv-stage-head">
            <strong>{TIER_NAME[tier]}</strong>
            <span>{stage.total ? `${stage.decided} von ${stage.total} entschieden` : "Nichts zu entscheiden"}</span>
          </div>
          <span className="frv-bar" role="progressbar" aria-label={`${TIER_NAME[tier]}: ${stage.decided} von ${stage.total} entschieden`} aria-valuemin={0} aria-valuemax={stage.total} aria-valuenow={stage.decided}><i style={{ width: `${pct}%` }} /></span>
          <p className="fd-muted">{TIER_HINT[tier]}</p>
          {stage.missing || stage.conflicts || stage.deferred ? <p className="frv-stage-notes">
            {stage.conflicts ? <Signal tone="warning" size="sm">{pluralize(stage.conflicts, "Widerspruch bzw. Änderung", "Widersprüche bzw. Änderungen")}</Signal> : null}
            {stage.missing ? <Signal tone="warning" size="sm">{stage.missing} nicht gefunden</Signal> : null}
            {stage.deferred ? <Signal tone="neutral" size="sm">{stage.deferred} zurückgestellt</Signal> : null}
          </p> : null}
          {stage.open > 0
            ? <button type="button" className={`btn btn-sm${tier === firstOpen ? " btn-primary" : ""}`} onClick={() => onStartGuided(tier)}>{TIER_NAME[tier]} prüfen · {stage.open}</button>
            : stage.total > 0 ? <Signal tone="done" size="sm">{tier === "essential" ? "Wesentliche Prüfung abgeschlossen" : "Entschieden"}</Signal> : null}
        </li>;
      })}
    </ol>

    {TIER_ORDER.map((tier) => {
      const fields = fieldsOf(review, tier).filter((field) => field.kind === "extracted" && (field.present || field.decision_needed || field.status === "absent"));
      if (!fields.length) return null;
      return <section key={tier} className="frv-group" aria-label={TIER_NAME[tier]}>
        <h3>{TIER_NAME[tier]}</h3>
        <table className="evt-table frv-table">
          <caption className="visually-hidden">{TIER_NAME[tier]}</caption>
          <thead><tr><th scope="col">Angabe</th><th scope="col">Wert</th><th scope="col">Quelle</th><th scope="col">Stand</th></tr></thead>
          <tbody>{fields.map((field) => <tr key={field.fact_key}>
            <td><button type="button" className="evt-link" onClick={() => open(field)}>{field.label}</button><span className="evt-sub">{field.card_label}</span></td>
            <td className="evt-muted">{field.current ?? "–"}{field.candidates.length > 1 ? <span className="evt-sub">{field.candidates.length} Werte zur Wahl</span> : null}</td>
            <td className="evt-muted">{field.source_state_label ?? "–"}</td>
            <td><Signal tone={STATUS_TONE[field.status]} size="sm">{field.status_label}</Signal></td>
          </tr>)}</tbody>
        </table>
      </section>;
    })}

    {calculated.length ? <section className="frv-group" aria-label="Berechnete Werte">
      <h3>Berechnete Werte</h3>
      <p className="fd-muted">Diese Werte entstehen aus den Angaben oben und werden nicht einzeln bestätigt.</p>
      <ul className="frv-calc">{calculated.map((field) => <li key={field.fact_key}>
        <button type="button" className="evt-link" onClick={() => open(field)}>{field.label}</button>
        <span className="evt-muted">{field.current ?? "–"}</span>
        <Signal tone="neutral" size="sm">{field.status === "derived" ? "Berechnet" : "Wartet auf Angaben"}</Signal>
      </li>)}</ul>
    </section> : null}

    {notFound.length ? <details className="frv-group frv-notfound">
      <summary>{pluralize(notFound.length, "Angabe", "Angaben")} im Dokument nicht gefunden (nicht erforderlich)</summary>
      <ul>{notFound.map((field) => <li key={field.fact_key}>{field.label}</li>)}</ul>
    </details> : null}

    <FindingsSection contractId={data.contract_id} orgSlug={orgSlug} review={review} canReview={canReview} onReload={onReload} onShowPage={onShowPage} />

    <FieldDecisionDrawer contractId={data.contract_id} orgSlug={orgSlug} review={review} factKey={opened} canReview={canReview} onClose={() => setOpened(null)}
      onReload={onReload} onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis}
      onStartGuided={(key) => { const field = review.fields.find((item) => item.fact_key === key); onStartGuided(field?.tier ?? "essential", key); }} />
  </section>;
}
