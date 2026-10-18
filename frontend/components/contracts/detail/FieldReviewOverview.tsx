"use client";

import { useMemo, useState } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import { sectionByKey } from "@/lib/evidence";
import { TIER_HINT, TIER_NAME, TIER_ORDER, decisionFields, nextOpenTier, pluralize, reviewHeadline, stageOf } from "@/lib/field-review";
import FieldDecision from "./FieldDecision";
import FindingsSection from "./FindingsSection";
import { SECTION_ICON, icon } from "./ReviewParts";

/** Karten wie die Reiter der Vertragsakte (Reihenfolge fest). */
const CARDS: { key: string; title: string }[] = [
  { key: "partner", title: "Vertrag & Partner" },
  { key: "term", title: "Laufzeit & Kündigung" },
  { key: "cost", title: "Preise & Zahlung" },
  { key: "services", title: "Service & Leistungen" },
  { key: "device", title: "Geräte" },
];
type TierFilter = FieldTier | "all";

const CHECK = icon(<><circle cx="12" cy="12" r="10" /><path d="m7.5 12.5 3 3 6-7" /></>, "frv-mark frv-mark--done");
const CIRCLE = icon(<circle cx="12" cy="12" r="9" />, "frv-mark frv-mark--open");
const WARN = icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>, "frv-mark frv-mark--warn");
const CLOCK = icon(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>, "frv-mark frv-mark--later");
const CHEVRON = icon(<path d="m9 6 6 6-6 6" />, "frv-chevron");
const SEARCH = icon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>, "frv-search-icon");

function mark(field: FieldReviewFieldDto) {
  if (field.status === "decided" || field.status === "absent" || field.status === "derived") return CHECK;
  if (field.status === "conflict" || field.status === "changed" || field.status === "missing") return WARN;
  if (field.status === "deferred") return CLOCK;
  return CIRCLE;
}

const BADGE: Partial<Record<FieldReviewFieldDto["status"], string>> = { conflict: "Widerspruch", changed: "Neu zu prüfen", missing: "Nicht gefunden", deferred: "Zurückgestellt" };

/** Angaben, die ohne Nachdenken bestätigt werden können: ein Wert, genau belegte Fundstelle, kein Widerspruch. */
function confirmable(fields: FieldReviewFieldDto[]): FieldReviewFieldDto[] {
  return fields.filter((field) => field.kind === "extracted" && field.status === "open" && field.present && field.candidates.length === 1
    && field.source_state === "verified" && field.active_evidence_count >= 1);
}

/**
 * Dokumente → Prüfung: Angaben nach Karten (Vertrag & Partner, Laufzeit & Kündigung, Preise & Zahlung, Service &
 * Leistungen) mit Wert und Stand; rechts die Entscheidung zur gewählten Angabe – dieselbe Ansicht wie in der geführten
 * Prüfung. Gezählt werden Angaben, nicht Belege; Berechnetes und Weitere Informationen zählen nicht.
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
  const toast = useToast();
  const [live, setLive] = useState<FieldReviewDto | null | undefined>(data.field_review);
  const [seenData, setSeenData] = useState(data.field_review);
  if (data.field_review !== seenData) { setSeenData(data.field_review); setLive(data.field_review); }
  const review = live;
  const [tier, setTier] = useState<TierFilter>("essential");
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState<number | null>(null);
  const [busyCard, setBusyCard] = useState<string | null>(null);
  if (focusKey && focusKey.n !== seenFocus) {
    setSeenFocus(focusKey.n);
    setSelected(focusKey.key);
    const target = review?.fields.find((item) => item.fact_key === focusKey.key);
    if (target && tier !== "all" && target.tier !== tier) setTier("all");
  }

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    return (review?.fields ?? []).filter((field) => field.kind === "extracted" && (field.present || field.decision_needed || field.status === "absent")
      && (tier === "all" || field.tier === tier)
      && (!onlyOpen || field.decision_needed)
      && (!needle || `${field.label} ${field.current ?? ""}`.toLocaleLowerCase("de-DE").includes(needle)));
  }, [review, tier, onlyOpen, query]);

  if (!review) return <section className="detail-card frv" aria-label="Prüfung"><h2>Prüfung</h2><p className="fd-muted">Für diesen Vertrag liegt noch keine Prüfung vor.</p></section>;

  const headline = reviewHeadline(review);
  const firstOpen = nextOpenTier(review);
  const essential = stageOf(review, "essential");
  const calculated = review.fields.filter((field) => field.kind === "calculated" && field.present);
  const notFound = review.fields.filter((field) => field.kind === "extracted" && !field.present && !field.decision_needed && field.status !== "absent");
  const current = review.fields.find((field) => field.fact_key === selected) ?? null;
  const allOpen = decisionFields(review);
  const openInView = visible.filter((field) => field.decision_needed);

  function afterDecision(detail: ContractDetailResponse | null) {
    onReload();
    if (!detail?.field_review) return;
    setLive(detail.field_review);
    const open = decisionFields(detail.field_review).filter((field) => tier === "all" || field.tier === tier);
    const index = open.findIndex((field) => field.fact_key === selected);
    const next = open.find((field) => field.fact_key !== selected && open.indexOf(field) > index) ?? open.find((field) => field.fact_key !== selected);
    setSelected(next?.fact_key ?? selected);
  }

  function step(direction: 1 | -1, onlyOpenFields: boolean) {
    const list = onlyOpenFields ? openInView : visible;
    if (!list.length) return;
    const index = list.findIndex((field) => field.fact_key === selected);
    const target = index < 0 ? (direction === 1 ? list[0] : list[list.length - 1]) : list[(index + direction + list.length) % list.length];
    setSelected(target.fact_key);
  }

  async function confirmCard(cardKey: string, fields: FieldReviewFieldDto[]) {
    setBusyCard(cardKey);
    let detail: ContractDetailResponse | null = null;
    let failed = 0;
    for (const field of fields) {
      try {
        detail = await decideField(data.contract_id, orgSlug, { fact_key: field.fact_key, decision: "keep", expected_version: field.version });
      } catch (err) {
        failed += 1;
        if (err instanceof ApiError && err.status === 409) break;
      }
    }
    setBusyCard(null);
    toast(failed ? `${fields.length - failed} bestätigt, ${failed} nicht gespeichert – bitte einzeln prüfen.` : `${pluralize(fields.length, "Angabe", "Angaben")} bestätigt.`, failed ? "error" : "success");
    onReload();
    if (detail?.field_review) setLive(detail.field_review);
  }

  return <section id="field-review-panel" className="frv" aria-labelledby="frv-title">
    <header className="frv-top">
      <div>
        <h2 id="frv-title">Prüfung</h2>
        <p className="fd-muted">Hier stehen die Angaben der Vertragsakte, über die Sie entscheiden. Jede Angabe wird einmal entschieden – Belege, die denselben Wert stützen, zählen nicht einzeln.</p>
      </div>
      <div className="frv-top-state">
        {essential && essential.total > 0 ? <strong className="frv-count">{essential.decided} von {essential.total} wesentlichen entschieden</strong> : null}
        {headline ? <Signal tone={headline.tone}>{headline.text}</Signal> : null}
        {firstOpen ? <button type="button" className="btn btn-primary" onClick={() => onStartGuided(firstOpen)}>{firstOpen === "essential" ? "Wesentliches prüfen" : `${TIER_NAME[firstOpen]} prüfen`} · {stageOf(review, firstOpen)?.open}</button> : null}
      </div>
    </header>

    <div className="frv-tools">
      <label className="frv-search"><span className="visually-hidden">Angabe oder Wert suchen</span>{SEARCH}
        <input type="search" placeholder="Angabe oder Wert suchen …" value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <div className="frv-filter" role="group" aria-label="Stufe wählen">
        {TIER_ORDER.map((item) => {
          const info = stageOf(review, item);
          if (!info || (info.total === 0 && item !== "essential")) return null;
          return <button key={item} type="button" className="btn btn-sm" aria-pressed={tier === item} onClick={() => setTier(item)} title={TIER_HINT[item]}>
            {TIER_NAME[item]}<span className="evt-count" aria-hidden="true">{info.decided}/{info.total}</span>
          </button>;
        })}
        <button type="button" className="btn btn-sm" aria-pressed={tier === "all"} onClick={() => setTier("all")}>Alle</button>
      </div>
      <button type="button" className="btn btn-sm" aria-pressed={onlyOpen} onClick={() => setOnlyOpen(!onlyOpen)}>Nur offene ({allOpen.filter((field) => tier === "all" || field.tier === tier).length})</button>
    </div>
    {tier !== "all" ? <p className="fd-muted frv-hint">{TIER_HINT[tier]}</p> : null}

    <div className="frv-layout">
      <div className="frv-cards">
        {CARDS.map((card) => {
          const fields = visible.filter((field) => field.card === card.key);
          if (!fields.length) return null;
          const decided = fields.filter((field) => !field.decision_needed).length;
          const easy = confirmable(fields);
          const section = sectionByKey(card.key);
          return <section key={card.key} className="frv-card" aria-label={card.title}>
            <header className="frv-card-head">
              <span className={`frv-card-icon erm-tone--${section.tone}`} aria-hidden="true">{icon(SECTION_ICON[card.key] ?? SECTION_ICON.other, "frv-card-svg")}</span>
              <h3>{card.title}</h3>
              <span className="frv-card-count">{decided} von {fields.length} entschieden</span>
            </header>
            <ul className="frv-rows">
              {fields.map((field) => <li key={field.fact_key}>
                <button type="button" className={`frv-row${field.fact_key === selected ? " is-selected" : ""}`} aria-current={field.fact_key === selected ? "true" : undefined} onClick={() => setSelected(field.fact_key)}>
                  <span className="frv-row-label">{field.label}</span>
                  <span className="frv-row-value">{field.current ?? "–"}</span>
                  {BADGE[field.status] ? <span className={`frv-badge frv-badge--${field.status}`}>{BADGE[field.status]}</span> : null}
                  <span className="frv-row-mark" role="img" aria-label={field.status_label}>{mark(field)}</span>
                  {CHEVRON}
                </button>
              </li>)}
            </ul>
            {canReview && easy.length ? <button type="button" className="btn btn-primary frv-card-action" disabled={busyCard !== null}
              title="Eindeutiger Wert, Fundstelle genau belegt, kein Widerspruch – bestätigt wird nur, was hier steht."
              onClick={() => void confirmCard(card.key, easy)}>{busyCard === card.key ? "Wird gespeichert…" : `${pluralize(easy.length, "Angabe", "Angaben")} bestätigen`}</button>
              : decided === fields.length ? <p className="frv-card-done">{CHECK}Abgeschlossen</p> : null}
          </section>;
        })}
        {visible.length === 0 ? <p className="fd-muted frv-empty">{onlyOpen ? "Nichts offen in dieser Auswahl." : "Keine Angaben in dieser Auswahl."}</p> : null}
        <p className="fd-muted frv-foot">Eine Angabe anklicken, um Details zu öffnen.</p>

        {calculated.length ? <section className="frv-extra" aria-label="Berechnete Werte">
          <h3>Berechnete Werte</h3>
          <p className="fd-muted">Diese Werte entstehen aus den Angaben oben und werden nicht einzeln bestätigt.</p>
          <ul className="frv-calc">{calculated.map((field) => <li key={field.fact_key}>
            <button type="button" className="evt-link" onClick={() => setSelected(field.fact_key)}>{field.label}</button>
            <span className="evt-muted">{field.current ?? "–"}</span>
            <Signal tone="neutral" size="sm">{field.status === "derived" ? "Berechnet" : "Wartet auf Angaben"}</Signal>
          </li>)}</ul>
        </section> : null}
        {notFound.length ? <details className="frv-extra frv-notfound">
          <summary>{pluralize(notFound.length, "Angabe", "Angaben")} im Dokument nicht gefunden (nicht erforderlich)</summary>
          <ul>{notFound.map((field) => <li key={field.fact_key}>{field.label}</li>)}</ul>
        </details> : null}
        <FindingsSection contractId={data.contract_id} orgSlug={orgSlug} review={review} canReview={canReview} onReload={onReload} onShowPage={onShowPage} />
      </div>

      <div className="frv-detail" role="group" aria-label="Details zur Angabe">
        {current ? <>
          <div className="frv-detail-nav">
            <span className="frv-crumb">{CARDS.find((card) => card.key === current.card)?.title ?? current.card_label}</span>
            <button type="button" className="btn btn-ghost btn-icon" aria-label="Details schließen" onClick={() => setSelected(null)}>×</button>
          </div>
          <FieldDecision key={`${current.fact_key}|${current.version ?? ""}|${current.status}`} contractId={data.contract_id} orgSlug={orgSlug} field={current} review={review} canReview={canReview}
            level={2} onChanged={afterDecision} onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />
          <div className="frv-detail-foot">
            <button type="button" className="btn" onClick={() => step(-1, false)}>Vorherige</button>
            <button type="button" className="btn" onClick={() => onStartGuided(current.tier, current.fact_key)}>Geführt weiter</button>
            <button type="button" className="btn" onClick={() => step(1, true)} disabled={openInView.filter((field) => field.fact_key !== current.fact_key).length === 0}>Nächste offene</button>
          </div>
        </> : <div className="frv-detail-empty">
          <p><strong>Details zur Angabe</strong></p>
          <p className="fd-muted">Wählen Sie links eine Angabe. Hier sehen Sie den Wert aus dem Dokument, den gespeicherten Wert, die Belege und entscheiden.</p>
          {openInView.length ? <button type="button" className="btn" onClick={() => step(1, true)}>Erste offene Angabe öffnen</button> : null}
        </div>}
      </div>
    </div>
  </section>;
}
