"use client";

import { useMemo, useState } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import { sectionByKey } from "@/lib/evidence";
import { TIER_HINT, TIER_NAME, TIER_ORDER, decisionFields, nextOpenTier, pluralize, reviewHeadline, shownValue, stageOf } from "@/lib/field-review";
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
const CHEVRON = icon(<path d="m6 9 6 6 6-6" />, "frv-chevron");
const SEARCH = icon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>, "frv-search-icon");

function mark(field: FieldReviewFieldDto) {
  if (field.status === "decided" || field.status === "absent" || field.status === "derived") return CHECK;
  if (field.status === "conflict" || field.status === "changed" || field.status === "missing") return WARN;
  if (field.status === "deferred") return CLOCK;
  return CIRCLE;
}

const STATE_TEXT: Partial<Record<FieldReviewFieldDto["status"], string>> = {
  decided: "Entschieden", open: "Offen", conflict: "Widerspruch", changed: "Neu zu prüfen", missing: "Nicht gefunden", deferred: "Zurückgestellt", absent: "Nicht im Dokument",
};

/** Angaben, die ohne Nachdenken bestätigt werden können: ein Wert, genau belegte Fundstelle, kein Widerspruch. */
function confirmable(fields: FieldReviewFieldDto[]): FieldReviewFieldDto[] {
  return fields.filter((field) => field.kind === "extracted" && field.status === "open" && field.present && field.candidates.length === 1
    && field.source_state === "verified" && field.active_evidence_count >= 1);
}

/**
 * Dokumente → Prüfung: eine ruhige Liste der Angaben nach Karten, mit Wert, Seite und Stand je Zeile. Eine Zeile klappt
 * die Entscheidung auf (dieselbe Ansicht wie in der geführten Prüfung); eindeutige Angaben lassen sich mit einem Klick
 * bestätigen. Gezählt werden Angaben, nicht Belege; Berechnetes und Weitere Informationen zählen nicht.
 */
export default function FieldReviewOverview({
  data, orgSlug, canReview, focusKey, onReload, onStartGuided, onShowEvidence, onShowPage, onOpenAnalysis,
}: {
  data: ContractDetailResponse;
  orgSlug: string;
  canReview: boolean;
  /** Diese Angabe gleich aufklappen (Klick auf eine KI-Plakette); `n` ändert sich bei jedem Klick. */
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
  const [busy, setBusy] = useState<string | null>(null);
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
      && (!onlyOpen || field.decision_needed || field.fact_key === selected)
      && (!needle || `${field.label} ${field.current ?? ""}`.toLocaleLowerCase("de-DE").includes(needle)));
  }, [review, tier, onlyOpen, query, selected]);

  if (!review) return <section className="detail-card frv" aria-label="Prüfung"><h2>Prüfung</h2><p className="fd-muted">Für diesen Vertrag liegt noch keine Prüfung vor.</p></section>;

  const headline = reviewHeadline(review);
  const firstOpen = nextOpenTier(review);
  const essential = stageOf(review, "essential");
  const calculated = review.fields.filter((field) => field.kind === "calculated" && field.present);
  const openInTier = decisionFields(review).filter((field) => tier === "all" || field.tier === tier).length;
  const easyAll = confirmable(visible);
  const pct = essential && essential.total ? Math.round((essential.decided / essential.total) * 100) : 0;

  function afterDecision(detail: ContractDetailResponse | null) {
    onReload();
    if (!detail?.field_review) return;
    setLive(detail.field_review);
    // Weiter zur nächsten offenen Angabe der Auswahl.
    const open = decisionFields(detail.field_review).filter((field) => tier === "all" || field.tier === tier);
    const index = open.findIndex((field) => field.fact_key === selected);
    const next = open.find((field) => field.fact_key !== selected && open.indexOf(field) > index) ?? open.find((field) => field.fact_key !== selected);
    setSelected(next?.fact_key ?? null);
  }

  async function confirm(key: string, fields: FieldReviewFieldDto[]) {
    setBusy(key);
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
    setBusy(null);
    toast(failed ? `${fields.length - failed} bestätigt, ${failed} nicht gespeichert – bitte einzeln prüfen.` : `${pluralize(fields.length, "Angabe", "Angaben")} bestätigt.`, failed ? "error" : "success");
    onReload();
    if (detail?.field_review) setLive(detail.field_review);
  }

  return <section id="field-review-panel" className="frv" aria-labelledby="frv-title">
    <header className="frv-top">
      <div className="frv-top-main">
        <h2 id="frv-title">Prüfung</h2>
        {essential && essential.total > 0
          ? <>
            <p className="frv-count"><strong>{essential.decided} von {essential.total}</strong> wesentlichen Angaben entschieden{headline && essential.open === 0 ? <> · <Signal tone="done" size="sm">Wesentliche Prüfung abgeschlossen</Signal></> : null}</p>
            <span className="frv-bar" role="progressbar" aria-label={`Wesentliche Angaben: ${essential.decided} von ${essential.total} entschieden`} aria-valuemin={0} aria-valuemax={essential.total} aria-valuenow={essential.decided}><i style={{ width: `${pct}%` }} /></span>
          </>
          : <p className="fd-muted">Keine wesentlichen Angaben gefunden.</p>}
      </div>
      {firstOpen ? <button type="button" className="btn btn-primary frv-go" onClick={() => onStartGuided(firstOpen)}>
        {firstOpen === "essential" ? "Wesentliches prüfen" : `${TIER_NAME[firstOpen]} prüfen`} · {stageOf(review, firstOpen)?.open}
      </button> : null}
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
      <button type="button" className="btn btn-sm" aria-pressed={onlyOpen} onClick={() => setOnlyOpen(!onlyOpen)}>Nur offene ({openInTier})</button>
    </div>
    {tier !== "all" ? <p className="fd-muted frv-hint">{TIER_HINT[tier]}</p> : null}

    {canReview && easyAll.length > 1 ? <div className="frv-bulk">
      <span><strong>{pluralize(easyAll.length, "Angabe ist", "Angaben sind")} eindeutig</strong> – ein Wert, Fundstelle genau belegt, kein Widerspruch.</span>
      <button type="button" className="btn" disabled={busy !== null} onClick={() => void confirm("all", easyAll)}>{busy === "all" ? "Wird gespeichert…" : `Diese ${easyAll.length} bestätigen`}</button>
    </div> : null}

    <div className="frv-cards">
      {CARDS.map((card) => {
        const fields = visible.filter((field) => field.card === card.key);
        if (!fields.length) return null;
        const decided = fields.filter((field) => !field.decision_needed).length;
        const section = sectionByKey(card.key);
        return <section key={card.key} className="frv-card" aria-label={card.title}>
          <header className="frv-card-head">
            <span className={`frv-card-icon erm-tone--${section.tone}`} aria-hidden="true">{icon(SECTION_ICON[card.key] ?? SECTION_ICON.other, "frv-card-svg")}</span>
            <h3>{card.title}</h3>
            <span className="frv-card-count">{decided} von {fields.length} entschieden</span>
          </header>
          <ul className="frv-rows">
            {fields.map((field) => {
              const open = field.fact_key === selected;
              const primary = field.evidence.find((entry) => entry.primary && !entry.excluded);
              const easy = canReview && confirmable([field]).length === 1;
              return <li key={field.fact_key} className={open ? "is-open" : undefined}>
                <div className="frv-row">
                  <button type="button" className="frv-row-main" aria-expanded={open} onClick={() => setSelected(open ? null : field.fact_key)}>
                    <span className="frv-row-label">{field.label}</span>
                    <span className={`frv-row-value${field.current ? "" : " is-empty"}`}>{shownValue(review, field.fact_key, field.current) ?? "nicht gefunden"}</span>
                    <span className="frv-row-page">{primary?.page != null ? `S. ${primary.page}` : ""}</span>
                    <span className={`frv-row-state frv-row-state--${field.status}`}>
                      <span role="img" aria-label={field.status_label}>{mark(field)}</span>{STATE_TEXT[field.status] ?? field.status_label}
                    </span>
                    {CHEVRON}
                  </button>
                  {easy ? <button type="button" className="btn btn-sm frv-row-confirm" disabled={busy !== null} aria-label={`${field.label} bestätigen`} onClick={() => void confirm(field.fact_key, [field])}>Bestätigen</button> : null}
                </div>
                {open ? <div className="frv-expand">
                  <FieldDecision key={`${field.fact_key}|${field.version ?? ""}|${field.status}`} contractId={data.contract_id} orgSlug={orgSlug} field={field} review={review} canReview={canReview} compact
                    onChanged={afterDecision} onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />
                  <p className="frv-expand-foot"><button type="button" className="rg-link" onClick={() => onStartGuided(field.tier, field.fact_key)}>Im Dokument weiter prüfen →</button></p>
                </div> : null}
              </li>;
            })}
          </ul>
        </section>;
      })}
      {visible.length === 0 ? <p className="fd-muted frv-empty">{onlyOpen ? "Nichts offen in dieser Auswahl." : "Keine Angaben in dieser Auswahl."}</p> : null}
    </div>

    {calculated.length ? <section className="frv-extra" aria-label="Berechnete Werte">
      <h3>Berechnete Werte</h3>
      <p className="fd-muted">Diese Werte entstehen aus den Angaben oben und werden nicht einzeln bestätigt.</p>
      <ul className="frv-calc">{calculated.map((field) => <li key={field.fact_key}>
        <button type="button" className="evt-link" onClick={() => setSelected(selected === field.fact_key ? null : field.fact_key)} aria-expanded={selected === field.fact_key}>{field.label}</button>
        <span className="evt-muted">{shownValue(review, field.fact_key, field.current) ?? "–"}</span>
        <Signal tone="neutral" size="sm">{field.status === "derived" ? "Berechnet" : "Wartet auf Angaben"}</Signal>
        {selected === field.fact_key ? <div className="frv-expand frv-expand--calc"><FieldDecision contractId={data.contract_id} orgSlug={orgSlug} field={field} review={review} canReview={canReview} onChanged={afterDecision} /></div> : null}
      </li>)}</ul>
    </section> : null}

    <FindingsSection contractId={data.contract_id} orgSlug={orgSlug} review={review} canReview={canReview} onReload={onReload} onShowPage={onShowPage} />
  </section>;
}
