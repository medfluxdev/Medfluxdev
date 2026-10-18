"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import { sectionByKey } from "@/lib/evidence";
import { TIER_HINT, TIER_NAME, TIER_ORDER, TIER_SHORT, decisionFields, nextOpenTier, pluralize, reviewHeadline, shownValue, stageOf } from "@/lib/field-review";
import FieldDecision from "./FieldDecision";
import FindingsSection from "./FindingsSection";
import Dialog from "@/components/ui/Dialog";
import ReviewHeader from "./ReviewCompletion";
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
type StatusFilter = "all" | "open" | "decided" | "deferred" | "conflict" | "missing";
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "Alle" }, { value: "open", label: "Offen" }, { value: "decided", label: "Entschieden" },
  { value: "deferred", label: "Zurückgestellt" }, { value: "conflict", label: "Widerspruch / geändert" }, { value: "missing", label: "Nicht gefunden" },
];
const TIER_OPTIONS: { value: TierFilter; label: string }[] = [
  { value: "all", label: "Alle Prioritäten" }, { value: "essential", label: "Wesentlich" }, { value: "important", label: "Weitere wichtige" }, { value: "optional", label: "Optional" },
];

function matchesStatus(field: FieldReviewFieldDto, status: StatusFilter): boolean {
  if (status === "all") return true;
  if (status === "open") return field.decision_needed;
  if (status === "decided") return field.status === "decided" || field.status === "absent";
  if (status === "conflict") return field.status === "conflict" || field.status === "changed";
  return field.status === status;
}
type View = "single" | "list";
const VIEW_KEY = "medflux.review.view";

function storedView(): View {
  try { return window.localStorage.getItem(VIEW_KEY) === "list" ? "list" : "single"; } catch { return "single"; }
}

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
  const [tier, setTier] = useState<TierFilter>("all");
  // Wie im Entwurf: zuerst die offenen Angaben (gibt es keine, alle).
  const [status, setStatus] = useState<StatusFilter>(() => (decisionFields(data.field_review).length > 0 ? "open" : "all"));
  const [bulkOpen, setBulkOpen] = useState(false);
  const [skipped, setSkipped] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // Einzelprüfung (Liste der Angaben + Entscheidung) oder Alle Angaben (Karten); die Wahl bleibt erhalten.
  const [view, setView] = useState<View>("single");
  useEffect(() => { setView(storedView()); }, []);
  const navRef = useRef<HTMLElement | null>(null);
  function chooseView(next: View) {
    setView(next);
    try { window.localStorage.setItem(VIEW_KEY, next); } catch { /* ohne Speicher: gilt für diese Sitzung */ }
  }
  if (focusKey && focusKey.n !== seenFocus) {
    setSeenFocus(focusKey.n);
    setSelected(focusKey.key);
    const target = review?.fields.find((item) => item.fact_key === focusKey.key);
    if (target && tier !== "all" && target.tier !== tier) setTier("all");
  }

  // Basis: Priorität und Suche (Zähler der Karten); sichtbar: zusätzlich der Status.
  const base = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    return (review?.fields ?? []).filter((field) => field.kind === "extracted" && (field.present || field.decision_needed || field.status === "absent")
      && (tier === "all" || field.tier === tier)
      && (!needle || `${field.label} ${field.current ?? ""}`.toLocaleLowerCase("de-DE").includes(needle)));
  }, [review, tier, query]);
  const visible = useMemo(() => base.filter((field) => matchesStatus(field, status) || field.fact_key === selected), [base, status, selected]);

  const effectiveKey = selected && visible.some((field) => field.fact_key === selected) ? selected : (visible.find((field) => field.decision_needed) ?? visible[0])?.fact_key ?? null;

  if (!review) return <section className="detail-card frv" aria-label="Prüfung"><h2>Prüfung</h2><p className="fd-muted">Für diesen Vertrag liegt noch keine Prüfung vor.</p></section>;

  const firstOpen = nextOpenTier(review);
  const calculated = review.fields.filter((field) => field.kind === "calculated" && field.present);
  const easyAll = confirmable(base);
  const total = base.length;
  const filtered = status !== "all" || tier !== "all" || query.trim() !== "";
  function reset() { setStatus("all"); setTier("all"); setQuery(""); }
  function firstBlocking() {
    const target = decisionFields(review, "essential")[0];
    if (!target) return;
    setTier("all"); setStatus("all"); setQuery("");
    setSelected(target.fact_key);
  }

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

  return <section id="field-review-panel" className="frv" aria-label="Prüfung">
    <ReviewHeader contractId={data.contract_id} orgSlug={orgSlug} review={data.contract_review} canReview={canReview} onReload={onReload}
      fallback={{ total: review.stages.reduce((sum, item) => sum + item.total, 0), decided: review.stages.reduce((sum, item) => sum + item.decided, 0) }}
      onBlocking={firstBlocking} onGuided={firstOpen ? () => onStartGuided(firstOpen) : null} />

    <section className="frv-filters" aria-label="Filter">
      <div className="frv-filter-row">
        <label className="frv-search"><span className="visually-hidden">Angabe oder Wert suchen</span>{SEARCH}
          <input type="search" placeholder="Angabe oder Wert suchen …" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className="frv-select">Status
          <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>
            {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}{option.value === "open" ? ` (${decisionFields(review).filter((field) => tier === "all" || field.tier === tier).length})` : ""}</option>)}
          </select>
        </label>
        <label className="frv-select">Priorität
          <select value={tier} onChange={(event) => setTier(event.target.value as TierFilter)}>
            {TIER_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <div className="frv-view" role="group" aria-label="Ansicht">
          <button type="button" className="btn btn-sm" aria-pressed={view === "list"} onClick={() => chooseView("list")}>Übersicht</button>
          <button type="button" className="btn btn-sm" aria-pressed={view === "single"} onClick={() => chooseView("single")}>Einzelprüfung</button>
        </div>
      </div>
      <div className="frv-chips">
        {status !== "all" ? <span className="frv-chip">{STATUS_OPTIONS.find((option) => option.value === status)?.label}<button type="button" aria-label="Statusfilter entfernen" onClick={() => setStatus("all")}>×</button></span> : null}
        {tier !== "all" ? <span className="frv-chip">{TIER_OPTIONS.find((option) => option.value === tier)?.label}<button type="button" aria-label="Prioritätsfilter entfernen" onClick={() => setTier("all")}>×</button></span> : null}
        {query.trim() ? <span className="frv-chip">„{query.trim()}“<button type="button" aria-label="Suche entfernen" onClick={() => setQuery("")}>×</button></span> : null}
        {filtered ? <button type="button" className="rg-link" onClick={reset}>Zurücksetzen</button> : null}
        <span className="frv-chips-count">{visible.length} {visible.length === 1 ? "Angabe" : "Angaben"}</span>
      </div>
    </section>

    {canReview && easyAll.length > 0 ? <div className="frv-bulk">
      <span className="frv-bulk-icon" aria-hidden="true">{icon(<path d="M8 6h13M8 12h13M8 18h13M3 6l1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2" />, "frv-bulk-svg")}</span>
      <div><strong>{pluralize(easyAll.length, "Angabe", "Angaben")} für gemeinsame Bestätigung verfügbar</strong><span className="fd-muted">Werte ansehen und gezielt auswählen.</span></div>
      <button type="button" className="btn" onClick={() => { setSkipped(new Set()); setBulkOpen(true); }}>{pluralize(easyAll.length, "Angabe", "Angaben")} ansehen →</button>
    </div> : null}

    {view === "single" ? <div className="frv-single">
      <nav ref={navRef} className="frv-nav" aria-label="Angaben" onKeyDown={(event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        const index = visible.findIndex((field) => field.fact_key === effectiveKey);
        const next = visible[index + (event.key === "ArrowDown" ? 1 : -1)];
        if (!next) return;
        event.preventDefault();
        setSelected(next.fact_key);
        window.setTimeout(() => navRef.current?.querySelector<HTMLElement>("button[aria-current=true]")?.focus(), 0);
      }}>
        <p className="fd-muted frv-nav-note">{visible.length} Angaben – mehrere Belege zum selben Wert stehen bei einer Angabe.</p>
        <ol>
          {visible.map((field, index) => <li key={field.fact_key}>
            <button type="button" className={`frv-nav-item${field.fact_key === effectiveKey ? " is-active" : ""}`} aria-current={field.fact_key === effectiveKey ? "true" : undefined} onClick={() => setSelected(field.fact_key)}>
              <span className="frv-nav-num">{index + 1}</span>
              <span className="frv-nav-text">
                <span className="frv-nav-label">{field.label}</span>
                <span className="frv-nav-meta">{TIER_SHORT[field.tier]}{field.ai_confidence != null ? ` · KI ${Math.round(field.ai_confidence * 100)} %` : ""}</span>
              </span>
              <span role="img" aria-label={field.status_label}>{mark(field)}</span>
            </button>
          </li>)}
        </ol>
      </nav>
      <div className="frv-detail" role="region" aria-label="Aktuelle Angabe">
        {(() => {
          const field = visible.find((item) => item.fact_key === effectiveKey);
          if (!field) return <p className="fd-muted frv-empty">{status === "open" ? "Nichts offen in dieser Auswahl." : "Keine Angaben in dieser Auswahl."}</p>;
          const index = visible.indexOf(field);
          return <>
            <FieldDecision key={`${field.fact_key}|${field.version ?? ""}|${field.status}`} contractId={data.contract_id} orgSlug={orgSlug} field={field} review={review} canReview={canReview}
              onChanged={afterDecision} onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />
            <nav className="erm-foot frv-pager" aria-label="Angaben blättern">
              <button type="button" className="btn btn-sm" disabled={index <= 0} onClick={() => setSelected(visible[index - 1].fact_key)}>← Vorherige Angabe</button>
              <span className="erm-foot-next">{index + 1} / {visible.length}</span>
              <button type="button" className="btn btn-sm" disabled={index >= visible.length - 1} onClick={() => setSelected(visible[index + 1].fact_key)}>Nächste Angabe →</button>
            </nav>
            <p className="frv-expand-foot"><button type="button" className="rg-link" onClick={() => onStartGuided(field.tier, field.fact_key)}>Im Dokument weiter prüfen →</button></p>
          </>;
        })()}
      </div>
    </div> : null}

    {view === "list" ? <div className="frv-cards">
      {CARDS.map((card) => {
        const fields = visible.filter((field) => field.card === card.key);
        if (!fields.length) return null;
        const inCard = base.filter((field) => field.card === card.key);
        const decided = inCard.filter((field) => !field.decision_needed).length;
        const section = sectionByKey(card.key);
        return <section key={card.key} className="frv-card" aria-label={card.title}>
          <header className="frv-card-head">
            <span className={`frv-card-icon erm-tone--${section.tone}`} aria-hidden="true">{icon(SECTION_ICON[card.key] ?? SECTION_ICON.other, "frv-card-svg")}</span>
            <h3>{card.title}</h3>
            <span className="frv-card-count">{decided} von {inCard.length} entschieden</span>
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
      {visible.length === 0 ? <p className="fd-muted frv-empty">{status === "open" ? "Nichts offen in dieser Auswahl." : "Keine Angaben in dieser Auswahl."}</p> : null}
    </div> : null}

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
    <Dialog open={bulkOpen} title="Gemeinsame Bestätigung" onClose={() => setBulkOpen(false)}
      description="Eindeutiger Wert, Fundstelle genau belegt, kein Widerspruch. Bestätigt wird nur, was angehakt ist."
      actions={<><button type="button" className="btn" onClick={() => setBulkOpen(false)}>Abbrechen</button>
        <button type="button" className="btn btn-primary" disabled={busy !== null || easyAll.every((field) => skipped.has(field.fact_key))}
          onClick={() => { const chosen = easyAll.filter((field) => !skipped.has(field.fact_key)); setBulkOpen(false); void confirm("all", chosen); }}>
          {pluralize(easyAll.filter((field) => !skipped.has(field.fact_key)).length, "Angabe", "Angaben")} bestätigen</button></>}>
      <ul className="frv-bulk-list">{easyAll.map((field) => <li key={field.fact_key}>
        <label>
          <input type="checkbox" checked={!skipped.has(field.fact_key)} onChange={(event) => setSkipped((before) => { const next = new Set(before); if (event.target.checked) next.delete(field.fact_key); else next.add(field.fact_key); return next; })} />
          <span><strong>{field.label}</strong> <span className="fd-value">{shownValue(review, field.fact_key, field.current)}</span>{field.evidence.find((entry) => entry.primary)?.page != null ? <small className="fd-muted"> · Seite {field.evidence.find((entry) => entry.primary)?.page}</small> : null}</span>
        </label>
      </li>)}</ul>
    </Dialog>
  </section>;
}
