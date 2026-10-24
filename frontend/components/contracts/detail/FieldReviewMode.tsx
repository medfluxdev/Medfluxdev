"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Drawer from "@/components/ui/Drawer";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, ContractReviewDto, EvidenceRef, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto, FieldTier } from "@/lib/contract-detail-types";
import { decideField } from "@/lib/domain-api/contracts";
import {
  LEVEL_NAME, LEVEL_ORDER, STATUS_TONE, TIER_NAME, TIER_ORDER, fieldByKey, fieldsOf, groupConfirmable, levelCounts, levelFields, levelOf, nextDecisionInLevel, nextOpenLevel,
  pluralize, refOf, type ReviewLevel,
} from "@/lib/field-review";
import FieldValuePanel from "./FieldValuePanel";
import { ReleaseDialog } from "./ReviewCompletion";
import { icon } from "./ReviewParts";

const BACK = icon(<path d="m15 6-6 6 6 6" />);
const LIST = icon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />);
const CHECK = icon(<path d="M20 6 9 17l-5-5" />);
const CHECK_CIRCLE = icon(<><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);

/**
 * Geführte Prüfung nach Feldern: ein Feld nach dem anderen, zwei Stufen – Pflicht zuerst, danach Optional.
 * Links das Original an der Fundstelle, rechts die Entscheidung (`FieldValuePanel`: Werte als Karten, ein Hauptknopf).
 * Was entschieden ist, kommt nicht wieder; Berechnetes wird nicht einzeln bestätigt; Weitere Informationen
 * aus dem Dokument sind kein Teil dieses Ablaufs.
 */
export default function FieldReviewMode({
  contractId, orgSlug, contractTitle, data, review, startKey, startTier, canReview, contractReview = null, viewer, onShow, onShowPage, onExit, onReload, onOpenAnalysis, onOpenFindings
}: {
  contractId: string;
  orgSlug: string;
  contractTitle: string | null;
  data: Pick<ContractDetailResponse, "evidence" | "documents">;
  review: FieldReviewDto;
  startKey: string | null;
  startTier?: FieldTier | null;
  canReview: boolean;
  /** Stand der Vertragsprüfung (für „Jetzt freigeben“ / „Vertrag freigeben“); fehlt er, gibt es hier keine Freigabe. */
  contractReview?: ContractReviewDto | null;
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
  // Lokaler Stand: die Antwort jeder Entscheidung gilt sofort; der Arbeitsplatz lädt parallel neu.
  const [live, setLive] = useState(review);
  useEffect(() => setLive(review), [review]);

  const startField = fieldByKey(review, startKey);
  const initialLevel: ReviewLevel = startField ? levelOf(startField.tier) : startTier ? levelOf(startTier) : nextOpenLevel(review) ?? "pflicht";
  const [level, setLevel] = useState<ReviewLevel>(initialLevel);
  const [key, setKey] = useState<string | null>(() => startField?.fact_key ?? nextDecisionInLevel(review, initialLevel, null)?.fact_key ?? null);
  const [done, setDone] = useState(() => !startField && !nextDecisionInLevel(review, initialLevel, null));
  const [drawer, setDrawer] = useState(false);
  const [releaseOpen, setReleaseOpen] = useState(false);
  const [announce, setAnnounce] = useState("");
  const headingRef = useRef<HTMLHeadingElement | null>(null);

  // Reihenfolge der Stufe: alle gelesenen Felder (Entschiedene bleiben zum Zurückblättern erreichbar).
  const stageFields = useMemo(() => levelFields(live, level).filter((field) => field.kind === "extracted" && (field.present || field.decision_needed || field.status === "absent")), [live, level]);
  const current = !done ? fieldByKey(live, key) : undefined;
  const index = current ? stageFields.findIndex((field) => field.fact_key === current.fact_key) : -1;

  // Im Original zeigen; Fokus auf die Überschrift (Screenreader hört das neue Feld).
  useEffect(() => {
    if (!current || done) return;
    const entry = current.evidence.find((item) => item.primary) ?? current.evidence.find((item) => !item.excluded);
    const ref = refOf(data, entry?.evidence_id);
    if (ref) onShow(ref);
    headingRef.current?.focus({ preventScroll: true });
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
    const next = nextDecisionInLevel(detail.field_review, level, key);
    if (next) { setKey(next.fact_key); setAnnounce(`Gespeichert · weiter zu ${next.label}`); return; }
    // Nach der letzten Pflichtangabe geht die Prüfung von selbst zu Optional (nur wenn dort etwas wartet).
    const other = nextDecisionInLevel(detail.field_review, "optional", null);
    if (level === "pflicht" && other) { setLevel("optional"); setKey(other.fact_key); setDone(false); setAnnounce("Pflicht fertig – jetzt Optional"); return; }
    setDone(true);
    setAnnounce("Gespeichert · Stufe abgeschlossen");
  }

  function switchLevel(next: ReviewLevel) {
    setLevel(next);
    const first = nextDecisionInLevel(live, next, null);
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
      if (event.key === "1") { event.preventDefault(); switchLevel("pflicht"); }
      if (event.key === "2") { event.preventDefault(); switchLevel("optional"); }
      if (event.key === "ArrowRight") { event.preventDefault(); go(index + 1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); if (done) setDone(false); else go(index - 1); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const following = index >= 0 ? stageFields[index + 1] : undefined;
  const counts = Object.fromEntries(LEVEL_ORDER.map((item) => [item, levelCounts(live, item)])) as Record<ReviewLevel, ReturnType<typeof levelCounts>>;
  const allTotal = counts.pflicht.total + counts.optional.total;
  const allOpen = counts.pflicht.open + counts.optional.open;
  const allDone = allTotal > 0 && allOpen === 0;
  const pflichtDone = counts.pflicht.total > 0 && counts.pflicht.open === 0;
  // Freigabe: dieselbe Handlung wie „Review abschließen“ im Prüfkopf – nie bei offener wesentlicher Angabe oder bereits abgeschlossener Prüfung.
  const canRelease = canReview && contractReview != null && contractReview.status !== "reviewed" && contractReview.critical_unreviewed_count === 0;

  return <section className="erm frm" aria-labelledby="erm-title">
    <header className="erm-bar pst-bar">
      <button type="button" className="btn btn-ghost erm-icon-btn pst-back" onClick={onExit} aria-label="Zurück zum Vertrag">{BACK}</button>
      <div className="pst-ttl pst-cell"><h2 id="erm-title">Angaben prüfen</h2><span className="erm-file">{contractTitle ?? ""}</span></div>
      <div className="pst-cell pst-stage">
        {/* Stufe und Fortschritt in einem: zwei Karten, die aktive zeigt Zähler, Balken und Rest; die andere nur, wie viel offen ist. */}
        <div className="pst-cards" role="group" aria-label="Prüfstufe">
          {LEVEL_ORDER.map((item) => {
            const info = counts[item];
            if (info.total === 0) return null;
            const finished = info.open === 0;
            const selected = level === item;
            return <button key={item} type="button" className={`pst-card${selected ? " is-cur" : ""}${finished ? " is-done" : ""}`} aria-pressed={selected} onClick={() => switchLevel(item)}
              aria-label={finished ? `${LEVEL_NAME[item]}, alle entschieden` : `${LEVEL_NAME[item]}, ${info.decided} von ${info.total} geprüft, ${info.open} offen`}>
              <span className="pst-card-top">
                <span className="pst-card-title">{finished ? <span className="pst-card-check" aria-hidden="true">{CHECK}</span> : null}{LEVEL_NAME[item]}</span>
                {selected
                  ? <span className="pst-card-stat">{info.decided} / {info.total} geprüft{finished ? "" : ` · ${info.open} offen`}</span>
                  : <span className="pst-card-pill">{finished ? "erledigt" : `${info.open} offen`}</span>}
              </span>
              {selected
                ? <span className="pst-meter" aria-hidden="true"><i style={{ width: `${(info.decided / info.total) * 100}%` }} /></span>
                : null}
            </button>;
          })}
        </div>
      </div>
      <div className="pst-cell pst-actions">
        {canRelease && allDone ? <button type="button" className="btn btn-primary" onClick={() => setReleaseOpen(true)}>Vertrag freigeben</button> : null}
        {canRelease && !allDone && pflichtDone ? <button type="button" className="btn btn-ghost pst-link" onClick={() => setReleaseOpen(true)}>Jetzt freigeben</button> : null}
        <button type="button" className="btn pst-overview" onClick={() => setDrawer(true)}>{LIST}Übersicht</button>
      </div>
    </header>

    <div className="erm-body">
      <div className="erm-viewer">
        {viewer}
        {!done && following ? <p className="erm-next-card">Nächste Angabe: {following.label}</p> : null}
      </div>

      <div className="erm-panel" role="region" aria-label="Aktuelle Angabe">
        <p className="visually-hidden" aria-live="polite">{announce}</p>
        {done || !current
          ? <StageSummary headingRef={headingRef} review={live} level={level} onSwitch={switchLevel} onExit={onExit} onShowAll={() => setDrawer(true)} onOpenFindings={onOpenFindings} />
          : <FieldValuePanel key={`${current.fact_key}|${current.version ?? ""}|${current.status}`} contractId={contractId} orgSlug={orgSlug} field={current} review={live}
            documents={data.documents ?? []} canReview={canReview} headingRef={headingRef} position={{ index: Math.max(index, 0), total: stageFields.length }}
            nextLabel={following?.label ?? null} onPrev={() => go(index - 1)} onNext={() => go(index + 1)}
            onChanged={changed} onShowEvidence={showEvidence} onShowPage={onShowPage} onOpenAnalysis={onOpenAnalysis}>
            {canReview ? <GroupConfirm key={current.fact_key} contractId={contractId} orgSlug={orgSlug} review={live} current={current}
              onDone={(detail) => { onReload(); if (detail?.field_review) setLive(detail.field_review); }} /> : null}
          </FieldValuePanel>}
      </div>
    </div>

    <Drawer open={drawer} title="Alle Angaben" onClose={() => setDrawer(false)} wide>
      <FieldList review={live} currentKey={current?.fact_key ?? null} onPick={(field) => { setDrawer(false); setLevel(levelOf(field.tier)); setKey(field.fact_key); setDone(false); }} />
    </Drawer>
    {contractReview ? <ReleaseDialog open={releaseOpen} onClose={() => setReleaseOpen(false)} contractId={contractId} orgSlug={orgSlug} unresolved={contractReview.unresolved_count} onDone={onReload} /> : null}
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
    <h3 id="frm-group-title">Auch in „{current.card_label}“</h3>
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
function StageSummary({ headingRef, review, level, onSwitch, onExit, onShowAll, onOpenFindings }: {
  headingRef: React.RefObject<HTMLHeadingElement>; review: FieldReviewDto; level: ReviewLevel; onSwitch: (level: ReviewLevel) => void;
  onExit: () => void; onShowAll: () => void; onOpenFindings?: () => void;
}) {
  const stage = levelCounts(review, level);
  const inLevel = review.stages.filter((item) => levelOf(item.tier) === level);
  const deferred = inLevel.reduce((sum, item) => sum + item.deferred, 0);
  const missing = inLevel.reduce((sum, item) => sum + item.missing, 0);
  const open = stage.open;
  const pflichtOpen = levelCounts(review, "pflicht").open;
  const otherLevel: ReviewLevel = level === "pflicht" ? "optional" : "pflicht";
  const other = levelCounts(review, otherLevel);
  const title = open > 0 ? "Stufe beendet" : level === "pflicht" ? "Pflicht abgeschlossen" : "Optional: alles entschieden";
  return <div className="erm-done">
    <p className="erm-done-eyebrow">Prüfung</p>
    <h3 ref={headingRef} tabIndex={-1} className="erm-done-title">
      <span className={`erm-done-mark${open ? " is-open" : ""}`} aria-hidden="true">{open ? LIST : CHECK}</span>{title}
    </h3>
    <p className="erm-done-lead">
      {stage.total ? `${stage.decided} von ${stage.total} Angaben entschieden${deferred ? `, ${deferred} zurückgestellt` : ""}${missing ? `, ${missing} nicht gefunden` : ""}.` : "Keine Angaben in dieser Stufe."}
      {" "}Das heißt nicht, dass jede Angabe des Vertrags verifiziert ist.
    </p>
    {open > 0 ? <InlineAlert tone="info">{pluralize(open, "Entscheidung wartet", "Entscheidungen warten")} noch – sie bleiben unter „Offene Punkte“ sichtbar.</InlineAlert>
      : <p className="erm-done-clear">{CHECK_CIRCLE}Keine offene Entscheidung in dieser Stufe</p>}
    {level === "optional" && pflichtOpen > 0 ? <InlineAlert tone="warning">Pflichtangaben sind noch offen.</InlineAlert> : null}
    {review.findings_open > 0 ? <p className="fd-muted">{pluralize(review.findings_open, "Weitere Information", "Weitere Informationen")} aus dem Dokument liegen zur Ansicht bereit – Sie müssen dazu nichts entscheiden.{onOpenFindings ? <> <button type="button" className="rg-link" onClick={onOpenFindings}>Ansehen</button></> : null}</p> : null}
    <div className="erm-done-actions">
      {open > 0 ? <button type="button" className="btn btn-primary" onClick={() => onSwitch(level)}>Offene Entscheidungen prüfen</button> : null}
      {other.open > 0 ? <button type="button" className={open > 0 || otherLevel === "optional" ? "btn" : "btn btn-primary"} onClick={() => onSwitch(otherLevel)}>
        {LEVEL_NAME[otherLevel]} prüfen · {other.open}
      </button> : null}
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

