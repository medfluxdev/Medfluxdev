"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Drawer from "@/components/ui/Drawer";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, EvidenceRef, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import { sectionByKey } from "@/lib/evidence";
import {
  STATUS_TONE, TIER_HINT, TIER_NAME, TIER_ORDER, fieldByKey, fieldsOf, groupConfirmable, nextDecision, nextOpenTier, pluralize, refOf, stageOf,
} from "@/lib/field-review";
import FieldDecision from "./FieldDecision";
import { SectionChip, icon } from "./ReviewParts";

const BACK = icon(<path d="m15 6-6 6 6 6" />);
const LIST = icon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />);
const CHECK = icon(<path d="M20 6 9 17l-5-5" />);
const CHECK_CIRCLE = icon(<><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>);
const PREV = icon(<path d="M19 12H5M11 6l-6 6 6 6" />);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);
const FILE = icon(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>);

/**
 * Geführte Prüfung nach Feldern: ein Feld nach dem anderen, wesentliche Angaben zuerst, danach die nächste Stufe.
 * Links das Original an der Fundstelle, rechts die Entscheidung (`FieldDecision` – dieselbe wie in der Karte).
 * Was entschieden ist, kommt nicht wieder; Berechnetes wird nicht einzeln bestätigt; Weitere Informationen
 * aus dem Dokument sind kein Teil dieses Ablaufs.
 */
export default function FieldReviewMode({
  contractId, orgSlug, contractTitle, data, review, startKey, startTier, canReview, viewer, onShow, onShowPage, onExit, onReload, onOpenAnalysis, onOpenFindings,
}: {
  contractId: string;
  orgSlug: string;
  contractTitle: string | null;
  data: Pick<ContractDetailResponse, "evidence">;
  review: FieldReviewDto;
  startKey: string | null;
  startTier?: FieldTier | null;
  canReview: boolean;
  /** Die Ansicht des Originals (vom Arbeitsplatz, damit Zoom/Seite erhalten bleiben). */
  viewer: ReactNode;
  onShow: (ref: EvidenceRef) => void;
  onShowPage: (page: number | null, quote: string | null) => void;
  onExit: () => void;
  onReload: () => void;
  onOpenAnalysis?: () => void;
  /** Weitere Informationen aus dem Dokument ansehen (nicht erforderlich). */
  onOpenFindings?: () => void;
}) {
  const toast = useToast();
  // Lokaler Stand: die Antwort jeder Entscheidung gilt sofort; der Arbeitsplatz lädt parallel neu.
  const [live, setLive] = useState(review);
  useEffect(() => setLive(review), [review]);

  const startField = fieldByKey(review, startKey);
  const [tier, setTier] = useState<FieldTier>(() => startField?.tier ?? startTier ?? nextOpenTier(review) ?? "essential");
  const [key, setKey] = useState<string | null>(() => startField?.fact_key ?? nextDecision(review, startField?.tier ?? startTier ?? nextOpenTier(review) ?? "essential", null)?.fact_key ?? null);
  const [done, setDone] = useState(() => !startField && !nextDecision(review, startTier ?? nextOpenTier(review) ?? "essential", null));
  const [drawer, setDrawer] = useState(false);
  const [announce, setAnnounce] = useState("");
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  // Reihenfolge der Stufe: alle gelesenen Felder (Entschiedene bleiben zum Zurückblättern erreichbar).
  const stageFields = useMemo(() => fieldsOf(live, tier).filter((field) => field.kind === "extracted" && (field.present || field.decision_needed || field.status === "absent")), [live, tier]);
  const current = !done ? fieldByKey(live, key) : undefined;
  const index = current ? stageFields.findIndex((field) => field.fact_key === current.fact_key) : -1;
  const stage = stageOf(live, tier);
  const section = current ? sectionByKey(current.card) : null;

  // Im Original zeigen; Fokus auf die Überschrift (Screenreader hört das neue Feld).
  useEffect(() => {
    if (!current || done) return;
    const entry = current.evidence.find((item) => item.primary) ?? current.evidence.find((item) => !item.excluded);
    const ref = refOf(data, entry?.evidence_id);
    if (ref) onShow(ref);
    headingRef.current?.focus();
    // onShow wechselt nur die Ansicht; neu auslösen soll nur ein anderes Feld.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.fact_key, done]);

  function go(target: number) {
    if (target < 0) return;
    if (target >= stageFields.length) { setDone(true); return; }
    setDone(false);
    setKey(stageFields[target].fact_key);
  }

  function showEvidence(entry: FieldEvidenceDto) {
    const ref = refOf(data, entry.evidence_id);
    if (ref) onShow(ref);
    else onShowPage(entry.page, entry.snippet);
  }

  function changed(detail: ContractDetailResponse | null) {
    onReload();
    if (!detail?.field_review) return;
    setLive(detail.field_review);
    // Entschieden oder zurückgestellt: weiter zum nächsten offenen Feld; ist keines mehr offen, ist die Stufe fertig.
    const next = nextDecision(detail.field_review, tier, key);
    if (next) { setKey(next.fact_key); setAnnounce(`Gespeichert · weiter zu ${next.label}`); }
    else { setDone(true); setAnnounce("Gespeichert · Stufe abgeschlossen"); }
  }

  function switchTier(next: FieldTier) {
    setTier(next);
    const first = nextDecision(live, next, null);
    setKey(first?.fact_key ?? null);
    setDone(!first);
  }

  // Tasten: ←/→ blättern (nicht in Eingabefeldern).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (drawer || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) return;
      if (event.key === "ArrowRight") { event.preventDefault(); go(index + 1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); if (done) setDone(false); else go(index - 1); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const following = index >= 0 ? stageFields[index + 1] : undefined;
  const total = stage?.total ?? stageFields.length;
  const open = stage?.open ?? 0;

  return <section className="erm frm" aria-labelledby="erm-title">
    <header className="erm-bar">
      <button type="button" className="btn btn-ghost erm-icon-btn" onClick={onExit} aria-label="Zurück zum Vertrag">{BACK}</button>
      <h2 id="erm-title">{TIER_NAME[tier]} prüfen</h2>
      <span className="erm-file">{FILE}{contractTitle ?? ""}</span>
      <div className="erm-progress">
        <span>{done ? `${total - open} von ${total} entschieden` : `Angabe ${Math.max(index, 0) + 1} von ${stageFields.length}`}</span>
        <span className="erm-seg" aria-hidden="true">{stageFields.map((field) => <i key={field.fact_key} className={field.fact_key === current?.fact_key ? "is-current" : field.decision_needed ? "is-open" : "is-confirmed"} />)}</span>
        <Signal tone={open ? "ai" : "done"} size="sm">{open ? `${pluralize(open, "Entscheidung", "Entscheidungen")} offen` : "Alles entschieden"}</Signal>
      </div>
      <div className="frm-tiers" role="group" aria-label="Stufe wählen">
        {TIER_ORDER.map((item) => {
          const info = stageOf(live, item);
          if (!info || info.total === 0) return null;
          return <button key={item} type="button" className="btn btn-sm" aria-pressed={tier === item} onClick={() => switchTier(item)}>
            {TIER_NAME[item]}<span className="evt-count" aria-hidden="true">{info.open}</span>
          </button>;
        })}
      </div>
      <button type="button" className="btn erm-all" onClick={() => setDrawer(true)}>{LIST}Alle Angaben</button>
    </header>

    <div className="erm-body">
      <div className="erm-viewer">
        {viewer}
        {!done && following ? <p className="erm-next-card">Nächste Angabe: {following.label}</p> : null}
      </div>

      <div className="erm-panel" role="region" aria-label="Aktuelle Angabe">
        <p className="visually-hidden" aria-live="polite">{announce}</p>
        {done || !current
          ? <StageSummary headingRef={headingRef} review={live} tier={tier} onSwitch={switchTier} onExit={onExit} onShowAll={() => setDrawer(true)} onOpenFindings={onOpenFindings} />
          : <>
            <div className="erm-head">
              <div className="erm-head-top">
                {section ? <SectionChip section={section} /> : null}
                <span className="erm-pos">{index + 1} / {stageFields.length}</span>
              </div>
              <p className="erm-where"><span>{TIER_HINT[tier]}</span></p>
            </div>
            <div className="erm-main">
              <FieldDecision key={`${current.fact_key}|${current.version ?? ""}|${current.status}`} contractId={contractId} orgSlug={orgSlug} field={current} review={live} canReview={canReview}
                headingRef={headingRef} onChanged={changed} onShowEvidence={showEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis} />
              {canReview ? <GroupConfirm key={current.fact_key} contractId={contractId} orgSlug={orgSlug} review={live} current={current}
                onDone={(detail) => { onReload(); if (detail?.field_review) setLive(detail.field_review); }} /> : null}
            </div>
          </>}

        {done || !current ? null : <nav className="erm-foot" aria-label="Angaben blättern">
          <button type="button" className="btn btn-sm" disabled={index <= 0} onClick={() => go(index - 1)}>{PREV}Zurück</button>
          <span className="erm-foot-next">{following ? `Nächste: ${following.label}` : "Letzte Angabe der Stufe"}</span>
          <button type="button" className="btn btn-sm" onClick={() => go(index + 1)}>Weiter{NEXT}</button>
        </nav>}
      </div>
    </div>

    <Drawer open={drawer} title="Alle Angaben" onClose={() => setDrawer(false)} wide>
      <FieldList review={live} currentKey={current?.fact_key ?? null} onPick={(field) => { setDrawer(false); setTier(field.tier); setKey(field.fact_key); setDone(false); }} />
    </Drawer>
  </section>;
}

/** Gruppenbestätigung: nur Werte, die hier sichtbar stehen – eindeutig, genau belegt, nicht umstritten. */
function GroupConfirm({ contractId, orgSlug, review, current, onDone }: {
  contractId: string; orgSlug: string; review: FieldReviewDto; current: FieldReviewFieldDto;
  onDone: (detail: ContractDetailResponse | null) => void;
}) {
  const toast = useToast();
  const rows = groupConfirmable(review, current);
  const [skip, setSkip] = useState<Set<string>>(() => new Set());
  const [busy, setBusy] = useState(false);
  if (rows.length === 0) return null;
  const chosen = rows.filter((row) => !skip.has(row.fact_key));

  async function confirmAll() {
    setBusy(true);
    let detail: ContractDetailResponse | null = null;
    let failed = 0;
    for (const row of chosen) {
      try {
        detail = await decideField(contractId, orgSlug, { fact_key: row.fact_key, decision: "keep", expected_version: row.version });
      } catch (err) {
        failed += 1;
        if (err instanceof ApiError && err.status === 409) break;
      }
    }
    setBusy(false);
    toast(failed ? `${chosen.length - failed} bestätigt, ${failed} nicht gespeichert – bitte einzeln prüfen.` : `${pluralize(chosen.length, "Angabe", "Angaben")} bestätigt.`, failed ? "error" : "success");
    onDone(detail);
  }

  return <section className="frm-group" aria-labelledby="frm-group-title">
    <h4 id="frm-group-title">Auch in „{current.card_label}“</h4>
    <p className="fd-muted">Eindeutiger Wert, Fundstelle genau belegt, kein Widerspruch. Bestätigt wird nur, was hier steht.</p>
    <ul>
      {rows.map((row) => {
        const primary = row.evidence.find((entry) => entry.primary);
        return <li key={row.fact_key}>
          <label>
            <input type="checkbox" checked={!skip.has(row.fact_key)} onChange={(event) => setSkip((before) => { const next = new Set(before); if (event.target.checked) next.delete(row.fact_key); else next.add(row.fact_key); return next; })} />
            <span><strong>{row.label}</strong> <span className="fd-value">{row.current}</span>{primary?.page != null ? <small className="fd-muted"> · Seite {primary.page}</small> : null}</span>
          </label>
        </li>;
      })}
    </ul>
    <button type="button" className="btn" disabled={busy || chosen.length === 0} onClick={() => void confirmAll()}>
      {busy ? "Wird gespeichert…" : `${pluralize(chosen.length, "angezeigte Angabe", "angezeigte Angaben")} bestätigen`}
    </button>
  </section>;
}

/** Ende einer Stufe: sagt ehrlich, was entschieden ist und was noch wartet – nie „alles verifiziert“. */
function StageSummary({ headingRef, review, tier, onSwitch, onExit, onShowAll, onOpenFindings }: {
  headingRef: React.RefObject<HTMLHeadingElement>; review: FieldReviewDto; tier: FieldTier; onSwitch: (tier: FieldTier) => void;
  onExit: () => void; onShowAll: () => void; onOpenFindings?: () => void;
}) {
  const stage = stageOf(review, tier);
  const open = stage?.open ?? 0;
  const essentialDone = review.essential_complete;
  const others = TIER_ORDER.filter((item) => item !== tier).map((item) => ({ tier: item, stage: stageOf(review, item) })).filter((entry) => entry.stage && entry.stage.open > 0);
  const title = open > 0 ? "Stufe beendet" : tier === "essential" ? "Wesentliche Prüfung abgeschlossen" : `${TIER_NAME[tier]}: alles entschieden`;
  return <div className="erm-done">
    <p className="erm-done-eyebrow">Prüfung</p>
    <h3 ref={headingRef} tabIndex={-1} className="erm-done-title">
      <span className={`erm-done-mark${open ? " is-open" : ""}`} aria-hidden="true">{open ? LIST : CHECK}</span>{title}
    </h3>
    <p className="erm-done-lead">
      {stage ? `${stage.decided} von ${stage.total} Angaben entschieden${stage.deferred ? `, ${stage.deferred} zurückgestellt` : ""}${stage.missing ? `, ${stage.missing} nicht gefunden` : ""}.` : "Keine Angaben in dieser Stufe."}
      {" "}Das heißt nicht, dass jede Angabe des Vertrags verifiziert ist.
    </p>
    {open > 0 ? <InlineAlert tone="info">{pluralize(open, "Entscheidung wartet", "Entscheidungen warten")} noch – sie bleiben unter „Offene Punkte“ sichtbar.</InlineAlert>
      : <p className="erm-done-clear">{CHECK_CIRCLE}Keine offene Entscheidung in dieser Stufe</p>}
    {tier !== "essential" && !essentialDone ? <InlineAlert tone="warning">Wesentliche Angaben sind noch offen.</InlineAlert> : null}
    {review.findings_open > 0 ? <p className="fd-muted">{pluralize(review.findings_open, "Weitere Information", "Weitere Informationen")} aus dem Dokument liegen zur Ansicht bereit – Sie müssen dazu nichts entscheiden.{onOpenFindings ? <> <button type="button" className="rg-link" onClick={onOpenFindings}>Ansehen</button></> : null}</p> : null}
    <div className="erm-done-actions">
      {open > 0 ? <button type="button" className="btn btn-primary" onClick={() => onSwitch(tier)}>Offene Entscheidungen prüfen</button> : null}
      {others.map((entry) => <button key={entry.tier} type="button" className={open > 0 || entry.tier === "optional" ? "btn" : "btn btn-primary"} onClick={() => onSwitch(entry.tier)}>
        {TIER_NAME[entry.tier]} prüfen · {entry.stage!.open}
      </button>)}
      <button type="button" className="btn" onClick={onShowAll}>Alle Angaben ansehen</button>
      <button type="button" className="btn" onClick={onExit}>Vertrag ansehen{NEXT}</button>
    </div>
  </div>;
}

/** Alle Angaben nach Stufe und Karte; ein Klick springt zur Angabe. */
export function FieldList({ review, currentKey, onPick }: { review: FieldReviewDto; currentKey: string | null; onPick: (field: FieldReviewFieldDto) => void }) {
  return <div className="frm-list">
    {TIER_ORDER.map((tier) => {
      const fields = fieldsOf(review, tier).filter((field) => field.present || field.decision_needed || field.status === "absent");
      if (!fields.length) return null;
      return <section key={tier} aria-label={TIER_NAME[tier]}>
        <h3>{TIER_NAME[tier]}</h3>
        <table className="evt-table">
          <caption className="visually-hidden">{TIER_NAME[tier]}</caption>
          <thead><tr><th scope="col">Angabe</th><th scope="col">Wert</th><th scope="col">Stand</th></tr></thead>
          <tbody>{fields.map((field) => <tr key={field.fact_key} className={field.fact_key === currentKey ? "is-current" : undefined} aria-current={field.fact_key === currentKey ? "true" : undefined}>
            <td><button type="button" className="evt-link" onClick={() => onPick(field)}>{field.label}</button><span className="evt-sub">{field.card_label}</span></td>
            <td className="evt-muted">{field.current ?? "–"}</td>
            <td><Signal tone={STATUS_TONE[field.status]} size="sm">{field.status_label}</Signal></td>
          </tr>)}</tbody>
        </table>
      </section>;
    })}
  </div>;
}

