"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
import Dialog from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, FieldEvidenceDto, FieldFindingDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import {
  LEVEL_NAME, LEVEL_ORDER, decisionFields, fieldByKey, levelOf, nextDecisionInLevel, nextOpenLevel, nextOpenTier, pluralize, reviewedFields, shownValue, stageCounts, stageFindings,
  type ReviewLevel,
} from "@/lib/field-review";
import FieldValuePanel from "./FieldValuePanel";
import FilterSelect from "./FilterSelect";
import FindingPanel from "./FindingPanel";
import ReviewHeader from "./ReviewCompletion";
import { icon } from "./ReviewParts";

type StatusFilter = "all" | "open" | "decided" | "deferred" | "conflict" | "changed" | "missing" | "absent" | "multi" | "finding" | "linked" | "note" | "dismissed";
const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "Alle" }, { value: "open", label: "Offen" }, { value: "decided", label: "Entschieden" },
  { value: "deferred", label: "Zurückgestellt" }, { value: "conflict", label: "Widerspruch" }, { value: "changed", label: "Neu zu prüfen" },
  { value: "missing", label: "Nicht gefunden" }, { value: "absent", label: "Nicht im Vertrag" }, { value: "multi", label: "Mehrere Fundstellen" },
  // Nur Weitere Informationen (Stufe Optional)
  { value: "finding", label: "Weitere Informationen" }, { value: "linked", label: "Einer Angabe zugeordnet" }, { value: "note", label: "Als Notiz gesichert" }, { value: "dismissed", label: "Ausgeblendet" },
];
const FINDING_PREFIX = "finding:";

function matchesStatus(field: FieldReviewFieldDto, status: StatusFilter): boolean {
  if (status === "all") return true;
  if (status === "open") return field.decision_needed;
  if (status === "multi") return field.active_evidence_count > 1;
  if (status === "finding" || status === "linked" || status === "note" || status === "dismissed") return false;
  return field.status === status;
}

function findingMatches(finding: FieldFindingDto, status: StatusFilter): boolean {
  if (status === "all") return true;
  if (status === "open") return finding.decision === null;
  if (status === "decided") return finding.decision !== null;
  if (status === "finding") return true;
  if (status === "linked" || status === "note" || status === "dismissed") return finding.decision === status;
  return false;
}

const CHECK = icon(<><circle cx="12" cy="12" r="10" /><path d="m7.5 12.5 3 3 6-7" /></>, "frv-mark frv-mark--done");
const CIRCLE = icon(<circle cx="12" cy="12" r="9" />, "frv-mark frv-mark--open");
const WARN = icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>, "frv-mark frv-mark--warn");
const CLOCK = icon(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>, "frv-mark frv-mark--later");
const SEARCH = icon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>, "frv-search-icon");
const DOCS = icon(<><path d="M8 4h9a2 2 0 0 1 2 2v11" /><path d="M5 7h9a2 2 0 0 1 2 2v10a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z" /></>, "frv-mark frv-mark--open");
const TICK = icon(<path d="M20 6 9 17l-5-5" />);

function mark(field: FieldReviewFieldDto) {
  if (field.status === "decided" || field.status === "absent" || field.status === "derived") return CHECK;
  if (field.status === "conflict" || field.status === "changed" || field.status === "missing") return WARN;
  if (field.status === "deferred") return CLOCK;
  return CIRCLE;
}

/** Angaben, die ohne Nachdenken bestätigt werden können: ein Wert, genau belegte Fundstelle, kein Widerspruch. */
function confirmable(fields: FieldReviewFieldDto[]): FieldReviewFieldDto[] {
  return fields.filter((field) => field.kind === "extracted" && field.status === "open" && field.present && field.candidates.length === 1
    && field.source_state === "verified" && field.active_evidence_count >= 1);
}

type Item = { key: string; number: number; label: string; field?: FieldReviewFieldDto; finding?: FieldFindingDto };

/**
 * Dokumente → Prüfung: dieselben Karten wie in der geführten Prüfung, aber ohne das Dokument daneben. Links Pflicht und
 * Optional mit allen Angaben (gleiche Nummern wie „Angabe n von N“) – man wählt, wo man anfängt und was man prüft;
 * rechts die Karte der gewählten Angabe mit Weiter und Pfeilen. Gezählt werden Angaben, nicht Belege.
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
  const [level, setLevel] = useState<ReviewLevel>(() => nextOpenLevel(data.field_review) ?? "pflicht");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [bulkOpen, setBulkOpen] = useState(false);
  const [skipped, setSkipped] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  if (focusKey && focusKey.n !== seenFocus) {
    setSeenFocus(focusKey.n);
    setSelected(focusKey.key);
    setStatus("all");
    setQuery("");
    const target = review?.fields.find((item) => item.fact_key === focusKey.key);
    if (target) setLevel(levelOf(target.tier));
  }

  // Alle Angaben der Stufe mit fester Nummer; sichtbar ist, was Suche und Status durchlassen.
  const stageItems: Item[] = useMemo(() => {
    const fields: Item[] = reviewedFields(review, level).map((field) => ({ key: field.fact_key, number: 0, label: field.label, field }));
    const findings: Item[] = stageFindings(review, level).map((finding) => ({ key: `${FINDING_PREFIX}${finding.finding_key}`, number: 0, label: finding.label, finding }));
    return [...fields, ...findings].map((item, index) => ({ ...item, number: index + 1 }));
  }, [review, level]);
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    return stageItems.filter((item) => {
      if (item.key === selected) return true;
      const text = item.field ? `${item.label} ${item.field.current ?? ""}` : `${item.label} ${item.finding?.snippet ?? ""}`;
      if (needle && !text.toLocaleLowerCase("de-DE").includes(needle)) return false;
      return item.field ? matchesStatus(item.field, status) : findingMatches(item.finding!, status);
    });
  }, [stageItems, query, status, selected]);
  const effectiveKey = selected && visible.some((item) => item.key === selected) ? selected
    : (visible.find((item) => item.field?.decision_needed || (item.finding && item.finding.decision === null)) ?? visible[0])?.key ?? null;

  if (!review) return <section className="detail-card frv" aria-label="Prüfung"><h2>Prüfung</h2><p className="fd-muted">Für diesen Vertrag liegt noch keine Prüfung vor.</p></section>;

  const firstOpen = nextOpenTier(review);
  const easyAll = confirmable(stageItems.flatMap((item) => (item.field ? [item.field] : [])));
  const counts = Object.fromEntries(LEVEL_ORDER.map((item) => [item, stageCounts(review, item)])) as Record<ReviewLevel, ReturnType<typeof stageCounts>>;
  const filtered = status !== "all" || query.trim() !== "";
  const statusCount = (value: StatusFilter) => stageItems.filter((item) => (item.field ? matchesStatus(item.field, value) : findingMatches(item.finding!, value))).length;
  const statusLead: Record<StatusFilter, ReactNode> = { all: null, open: CIRCLE, decided: CHECK, deferred: CLOCK, conflict: WARN, changed: WARN, missing: WARN, absent: CHECK, multi: DOCS, finding: DOCS, linked: CHECK, note: CHECK, dismissed: CLOCK };
  const statusOptions = STATUS_OPTIONS.filter((option) => option.value === "all" || option.value === "open" || option.value === "decided" || statusCount(option.value) > 0 || option.value === status)
    .map((option) => ({ value: option.value, label: option.label, count: statusCount(option.value), lead: statusLead[option.value] }));
  const current = visible.find((item) => item.key === effectiveKey) ?? null;
  const position = current ? visible.indexOf(current) : -1;
  const nextLabel = current ? visible[position + 1]?.label ?? null : null;
  const panelPosition = { index: current ? current.number - 1 : 0, total: stageItems.length };

  function firstBlocking() {
    const target = decisionFields(review, "essential")[0];
    if (!target) return;
    setLevel("pflicht");
    setStatus("all");
    setQuery("");
    setSelected(target.fact_key);
  }
  function switchLevel(next: ReviewLevel) {
    setLevel(next);
    setSelected(null);
  }
  function step(offset: number) {
    const target = visible[position + offset];
    if (target) setSelected(target.key);
  }

  function afterDecision(detail: ContractDetailResponse | null) {
    onReload();
    if (!detail?.field_review) return;
    setLive(detail.field_review);
    // Weiter zur nächsten offenen Angabe der Stufe, danach zu den offenen Weiteren Informationen.
    const next = nextDecisionInLevel(detail.field_review, level, selected);
    if (next) { setSelected(next.fact_key); return; }
    const finding = stageFindings(detail.field_review, level).find((item) => item.decision === null);
    if (finding) setSelected(`${FINDING_PREFIX}${finding.finding_key}`);
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

    <section className="frv-toolbar" aria-label="Auswahl">
      <div className="lvl-switch" role="group" aria-label="Prüfstufe">
        {LEVEL_ORDER.map((item) => {
          const info = counts[item];
          if (info.total === 0) return null;
          const finished = info.open === 0;
          const active = level === item;
          return <button key={item} type="button" className={`lvl-tab lvl-tab--${item}${active ? " is-cur" : ""}${finished ? " is-done" : ""}`} aria-pressed={active} onClick={() => switchLevel(item)}
            aria-label={finished ? `${LEVEL_NAME[item]}, alle entschieden` : `${LEVEL_NAME[item]}, ${info.decided} von ${info.total} geprüft, ${info.open} offen`}>
            <span className="lvl-tab-name">{LEVEL_NAME[item]}</span>
            <span className="lvl-tab-count" aria-hidden="true">{finished ? TICK : info.open}</span>
          </button>;
        })}
      </div>
      <div className="frv-toolbar-right">
      <label className="frv-search"><span className="visually-hidden">Angabe oder Wert suchen</span>{SEARCH}
        <input type="search" placeholder="Angabe oder Wert suchen …" value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <FilterSelect label="Status" value={status} onChange={(value) => setStatus(value as StatusFilter)} options={statusOptions} />
      </div>
    </section>

    {canReview && easyAll.length > 0 ? <div className="frv-bulk">
      <span className="frv-bulk-icon" aria-hidden="true">{icon(<path d="M8 6h13M8 12h13M8 18h13M3 6l1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2" />, "frv-bulk-svg")}</span>
      <div><strong>{pluralize(easyAll.length, "Angabe", "Angaben")} für gemeinsame Bestätigung verfügbar</strong><span className="fd-muted">Werte ansehen und gezielt auswählen.</span></div>
      <button type="button" className="btn" onClick={() => { setSkipped(new Set()); setBulkOpen(true); }}>{pluralize(easyAll.length, "Angabe", "Angaben")} ansehen →</button>
    </div> : null}

    <div className="frv-single">
      <nav className="frv-nav" aria-label="Angaben" onKeyDown={(event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        const next = visible[position + (event.key === "ArrowDown" ? 1 : -1)];
        if (!next) return;
        event.preventDefault();
        setSelected(next.key);
      }}>
        <p className="fd-muted frv-nav-note">{filtered ? `${visible.length} von ${stageItems.length}` : stageItems.length} Angaben · {LEVEL_NAME[level]}</p>
        <ol>
          {visible.map((item) => <li key={item.key}>
            <button type="button" className={`frv-nav-item${item.key === effectiveKey ? " is-active" : ""}`} aria-current={item.key === effectiveKey ? "true" : undefined} onClick={() => setSelected(item.key)}>
              <span className="frv-nav-num">{item.number}</span>
              <span className="frv-nav-text">
                <span className="frv-nav-label">{item.label}</span>
                <span className="frv-nav-meta">{item.field ? (shownValue(review, item.field.fact_key, item.field.current) ?? "nicht gefunden") : "Weitere Information"}</span>
              </span>
              <span role="img" aria-label={item.field ? item.field.status_label : item.finding?.decision ? "Entschieden" : "Offen"}>{item.field ? mark(item.field) : item.finding?.decision ? CHECK : CIRCLE}</span>
            </button>
          </li>)}
        </ol>
      </nav>
      <div className="frv-detail frv-panel" role="region" aria-label="Aktuelle Angabe">
        {!current ? <p className="fd-muted frv-empty">{status === "open" ? "Nichts offen in dieser Auswahl." : "Keine Angaben in dieser Auswahl."}</p>
          : current.finding
            ? <FindingPanel key={current.finding.finding_key} contractId={data.contract_id} orgSlug={orgSlug} finding={current.finding} review={review} canReview={canReview} headingRef={headingRef}
              position={panelPosition} nextLabel={nextLabel} onPrev={() => step(-1)} onNext={() => step(1)} onShowPage={onShowPage}
              onDecided={(decision, targetKey) => {
                onReload();
                const target = decision === "link" ? fieldByKey(review, targetKey) : undefined;
                if (target) { setLevel(levelOf(target.tier)); setSelected(target.fact_key); return; }
                step(1);
              }} />
            : <FieldValuePanel key={`${current.field!.fact_key}|${current.field!.version ?? ""}|${current.field!.status}`} contractId={data.contract_id} orgSlug={orgSlug} field={current.field!} review={review}
              documents={data.documents ?? []} canReview={canReview} headingRef={headingRef} position={panelPosition} nextLabel={nextLabel} onPrev={() => step(-1)} onNext={() => step(1)}
              onChanged={afterDecision} onShowEvidence={onShowEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />}
        {current?.field ? <p className="frv-expand-foot"><button type="button" className="rg-link" onClick={() => onStartGuided(current.field!.tier, current.field!.fact_key)}>Im Dokument weiter prüfen →</button></p> : null}
      </div>
    </div>

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
