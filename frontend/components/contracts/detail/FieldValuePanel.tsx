"use client";

import { useEffect, useId, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import ActionMenu from "@/components/ui/ActionMenu";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, DetailDocument, FieldCandidateDto, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto } from "@/lib/contract-detail-types";
import { decideField, setFieldEvidence, type FieldDecision as Decision } from "@/lib/domain-api/contracts";
import { LEVEL_NAME, candidateEvidence, levelOf, shownValue } from "@/lib/field-review";
import { formatDateTime } from "@/lib/format";
import { preselectCandidate } from "@/lib/review/preselect";
import { roleLabel } from "./DocumentList";
import PageTextPicker from "./PageTextPicker";
import { icon } from "./ReviewParts";

const CHECK = icon(<path d="M20 6 9 17l-5-5" />);
const CHECK_CIRCLE = icon(<><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>);
const DOC = icon(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></>);
const PEN = icon(<><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></>);
const SEARCH = icon(<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>);
const MARK = icon(<path d="M4 20h16M6 16l10-10 2 2-10 10H6z" />);
const WARN = icon(<><path d="M12 4 2.5 20h19z" /><path d="M12 10v4M12 17.2v.1" /></>);
const HISTORY = icon(<><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5M12 7v5l3 2" /></>);
const BACK = icon(<path d="M15 6l-6 6 6 6" />);
const SKIP = icon(<path d="M5 5l9 7-9 7zM19 5v14" />);
const NEXT = icon(<path d="M5 12h14M13 6l6 6-6 6" />);

const OTHER = "__other";
const NONE = "__none";
/** Standard-Begründungen des Backends: sie sind keine Begründung der Person und werden nicht als solche gezeigt. */
const AUTO_NOTE = /^(Von Hand eingetragen|Wert gewählt \(|Wert aus dem Dokument übernommen|Abweichung geklärt)/;

function Kbd({ children }: { children: string }) {
  return <kbd className="vp-kbd" aria-hidden="true">{children}</kbd>;
}

interface Card {
  candidate: FieldCandidateDto;
  shown: string;
  entry: FieldEvidenceDto | null;
  page: number | null;
  quote: string | null;
  where: string;
  count: number;
}

/** Wortlaut-Zusatz für die einzelne Karte: 100 % des Zitats steht auf der Seite. */
const literal = (entry: FieldEvidenceDto | null) => (entry?.text_match != null && entry.text_match >= 1 ? " · wörtlich im Dokument" : "");

/**
 * Entscheidung zu einem Feld in der geführten Prüfung – ein Panel mit drei Zuständen (Übereinstimmung, mehrere Werte, entschieden).
 * Jeder gefundene Wert ist eine Karte mit Seite, Abschnitt und Zitat; der gespeicherte Wert ist eine davon („in MedFlux“).
 * Eine Auswahl, ein Hauptknopf, der die Handlung nennt. „Selbst eintragen“ und „Nicht im Vertrag“ sind immer erreichbar.
 * Alles läuft über die Feldprüfung der API (`decideField`, `setFieldEvidence`).
 */
export default function FieldValuePanel({
  contractId, orgSlug, field, review, documents, canReview, position, nextLabel, onChanged, onShowEvidence, onShowPage, onOpenAnalysis, onPrev, onNext, headingRef, children,
}: {
  contractId: string;
  orgSlug: string;
  field: FieldReviewFieldDto;
  review: FieldReviewDto;
  documents: DetailDocument[];
  canReview: boolean;
  /** Stelle in der Stufe („3 / 12“). */
  position: { index: number; total: number };
  nextLabel: string | null;
  onChanged: (detail: ContractDetailResponse | null, info: { decided: boolean }) => void;
  onShowEvidence?: (evidence: FieldEvidenceDto) => void;
  onShowPage?: (page: number | null, quote: string | null) => void;
  onOpenAnalysis?: () => void;
  onPrev: () => void;
  onNext: () => void;
  headingRef?: RefObject<HTMLHeadingElement>;
  /** Zusatz unter den Werten (z. B. Gruppenbestätigung). */
  children?: ReactNode;
}) {
  const toast = useToast();
  const ids = useId();
  const documentOf = (entry: FieldEvidenceDto | null) => documents.find((doc) => doc.document_version_id === entry?.document_version_id) ?? null;

  const cards: Card[] = useMemo(() => {
    const built = field.candidates.map((candidate) => {
      const entries = candidateEvidence(field, candidate);
      const active = entries.filter((entry) => !entry.excluded);
      const entry = active.find((item) => item.primary) ?? active[0] ?? entries[0] ?? null;
      const inline = candidate.inline_evidence[0] ?? null;
      const doc = entry ? documents.find((item) => item.document_version_id === entry.document_version_id) ?? null : null;
      const page = entry?.page ?? inline?.page ?? null;
      const label = doc ? roleLabel(doc, null) : entry?.original_filename ?? null;
      return {
        candidate, shown: shownValue(review, field.fact_key, candidate.display) ?? candidate.display, entry, page,
        quote: entry?.snippet ?? inline?.quote ?? null,
        where: [page != null ? `Seite ${page}` : entry || inline ? "Ohne Seite" : "Kein Beleg im Dokument", label].filter(Boolean).join(" · "),
        count: active.length + candidate.inline_evidence.length,
      } satisfies Card;
    });
    // Der gespeicherte Wert zuerst, danach nach Seite.
    return built.sort((a, b) => Number(b.candidate.is_current) - Number(a.candidate.is_current) || (a.page ?? 999) - (b.page ?? 999));
  }, [field, review, documents]);

  const preselected = useMemo(() => preselectCandidate(field.candidates.map((candidate) => ({
    key: candidate.key, isCurrent: candidate.is_current,
    evidence: candidateEvidence(field, candidate).filter((entry) => !entry.excluded).map((entry) => ({ role: documentOf(entry)?.role ?? null, page: entry.page })),
  }))), // eslint-disable-next-line react-hooks/exhaustive-deps
  [field, documents]);

  const current = field.candidates.find((candidate) => candidate.is_current) ?? null;
  const decided = field.status === "decided" || field.status === "absent";
  const [editing, setEditing] = useState(false);
  const showDecided = decided && !editing;
  const startKey = (decided ? current?.key : preselected) ?? current?.key ?? null;
  const [picked, setPicked] = useState<string | null>(field.present ? startKey : OTHER);
  const [otherOpen, setOtherOpen] = useState(!field.present);
  const [otherValue, setOtherValue] = useState("");
  // „Nicht im Vertrag“ + eigener Wert: der Wert steht nicht im Dokument, gilt aber (z. B. mündlich vereinbart).
  const [noneValue, setNoneValue] = useState("");
  const [picker, setPicker] = useState(false);
  const [note, setNote] = useState("");
  const [exclude, setExclude] = useState<{ id: string; reason: string; note: string } | null>(null);
  const [fold, setFold] = useState<null | "alt" | "history">(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [announce, setAnnounce] = useState("");
  const otherInput = useRef<HTMLInputElement | null>(null);

  const selected = cards.find((card) => card.candidate.key === picked) ?? null;
  const isOther = picked === OTHER;
  const isNone = picked === NONE;
  // „Nicht im Vertrag“ ist immer wählbar: ohne Wert hält es das fest, mit gefundenem Wert verwirft es diesen ausdrücklich.
  const canNone = true;
  const canDefer = canReview && field.decision_needed && field.status !== "deferred" && field.status !== "missing";
  const needsReason = isOther || isNone || Boolean(selected && !selected.candidate.is_current);
  const analysisOnly = Boolean(selected?.candidate.proposal_id && !selected.candidate.is_current);
  const reviewer = field.reviewer;
  const unresolvedSource = field.present && field.source_state !== null && field.source_state !== "verified" && field.source_state !== "located";
  const primaryEntry = field.evidence.find((entry) => entry.primary && !entry.excluded) ?? field.evidence.find((entry) => !entry.excluded) ?? null;
  // „Stelle im Dokument markieren“: Start bei der Seite des Belegs, sonst Seite 1 des Hauptdokuments; jede Seite ist erreichbar.
  const pickerDocs = documents.filter((doc) => doc.viewer_supported).map((doc) => ({ id: doc.document_version_id, label: doc.original_filename ?? doc.role ?? "Dokument" }));
  const pickerStart = primaryEntry?.document_version_id && primaryEntry.page != null
    ? { documentVersionId: primaryEntry.document_version_id, page: primaryEntry.page }
    : pickerDocs[0] ? { documentVersionId: pickerDocs[0].id, page: 1 } : null;

  // Mehrere Fundstellen zur selben Angabe: sichtbar auflisten, einzeln ansehen und das Hauptnachweis wählen.
  const activeSources = field.evidence.filter((entry) => !entry.excluded).length;
  const sources = field.evidence.length > 1 ? <section className="vp-sources" aria-label="Fundstellen">
    <p className="vp-sources-head"><span className="vp-sources-icon" aria-hidden="true">{DOC}</span><b>{activeSources} {activeSources === 1 ? "Fundstelle" : "Fundstellen"} für diese Angabe</b></p>
    <ul className="vp-sources-list">{field.evidence.map((entry) => <li key={entry.evidence_id} className={`vp-source${entry.excluded ? " is-excluded" : ""}`}>
      <span className="vp-where">{entry.page != null ? `Seite ${entry.page}` : "Ohne Seite"}{entry.primary ? " · Hauptnachweis" : ""}{entry.excluded ? " · ausgeschlossen" : ""}</span>
      {entry.snippet ? <span className="vp-quote" title={entry.snippet}>„{entry.snippet}“</span> : null}
      <span className="vp-alt-actions">
        <button type="button" className="vp-link" onClick={() => onShowEvidence?.(entry)}>{DOC}Im Dokument zeigen</button>
        {canReview && !entry.primary && !entry.excluded ? <button type="button" className="vp-link" disabled={busy} onClick={() => void evidenceAction(entry, "primary")}>Als Hauptnachweis</button> : null}
      </span>
    </li>)}</ul>
  </section> : null;

  // Berechnete Werte, die aus dieser Angabe entstehen: sie werden nicht einzeln bestätigt, aber hier sichtbar.
  const derived = review.fields.filter((item) => item.kind === "calculated" && item.present && item.inputs.some((input) => input.fact_key === field.fact_key));
  const derivedBlock = derived.length ? <section className="vp-derived" aria-label="Daraus berechnet">
    <p className="vp-derived-head">Daraus berechnet</p>
    <ul>{derived.map((item) => <li key={item.fact_key}><span>{item.label}</span><b>{shownValue(review, item.fact_key, item.current) ?? "–"}</b></li>)}</ul>
  </section> : null;

  async function send(work: () => Promise<ContractDetailResponse>, success: string, decidedAfter: boolean) {
    setBusy(true);
    setError(null);
    try {
      const detail = await work();
      toast(success, "success");
      setExclude(null);
      setEditing(false);
      onChanged(detail, { decided: decidedAfter });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setStale(true);
        toast("Das Feld wurde inzwischen geändert – Stand neu geladen.", "error");
        onChanged(null, { decided: false });
      } else {
        setError(err instanceof ApiError && err.message ? err.message : "Die Entscheidung konnte nicht gespeichert werden. Bitte erneut versuchen.");
      }
    } finally {
      setBusy(false);
    }
  }

  const decide = (decision: Decision, extra: { candidate_key?: string | null; value?: string | null; note?: string | null; confirm_change?: boolean } = {}, success = "Gespeichert.") =>
    send(() => decideField(contractId, orgSlug, { fact_key: field.fact_key, decision, expected_version: field.version, ...extra }), success, decision !== "defer");

  const evidenceAction = (entry: FieldEvidenceDto, action: "primary" | "exclude" | "restore", extra: { reason?: string; note?: string } = {}) =>
    send(() => setFieldEvidence(contractId, orgSlug, { fact_key: field.fact_key, evidence_id: entry.evidence_id, action, expected_version: field.version, ...extra }),
      action === "primary" ? "Hauptnachweis gewählt." : action === "exclude" ? "Fundstelle ausgeschlossen – der Wert bleibt unverändert." : "Fundstelle wiederhergestellt.", false);

  // Der Hauptknopf nennt die Handlung.
  const reason = needsReason ? note.trim() || null : null;
  let action: { label: string; run: () => void; disabled: boolean } | null = null;
  if (canReview) {
    if (isNone) {
      const own = noneValue.trim();
      action = own
        ? { label: "Wert speichern", disabled: busy, run: () => void decide("manual", { value: own, note: reason ?? "Nicht im Vertrag – Wert von Hand ergänzt." }, "Wert eingetragen – steht nicht im Vertrag.") }
        : { label: "Speichern", disabled: busy, run: () => void decide("not_in_document", { note: reason }, "Als „nicht im Vertrag“ festgehalten.") };
    }
    else if (isOther) {
      const text = otherValue.trim();
      action = { label: "Speichern", disabled: busy || !text, run: () => void decide("manual", { value: text, note: reason }, "Wert gespeichert.") };
    } else if (selected) {
      const stored = selected.candidate.is_current && field.present;
      action = stored
        ? { label: "Bestätigen", disabled: busy, run: () => void decide("keep", { candidate_key: selected.candidate.key, note: reason }, "Bestätigt.") }
        : { label: "Übernehmen", disabled: busy || analysisOnly,
          run: () => void decide("accept", { candidate_key: selected.candidate.key, confirm_change: true, note: reason }, `Wert geändert auf „${selected.shown}“.`) };
    }
  }

  function choose(key: string) {
    setPicked(key);
    setOtherOpen(false);
    setPicker(false);
    const card = cards.find((item) => item.candidate.key === key);
    setAnnounce(card ? `Ausgewählt: ${card.shown}` : "");
  }
  function openOther() {
    setOtherOpen(true);
    setPicked(OTHER);
    setAnnounce("Eigenen Wert eingeben");
    window.setTimeout(() => otherInput.current?.focus(), 0);
  }
  function chooseNone() {
    setPicked(NONE);
    setOtherOpen(false);
    setAnnounce("Nicht im Vertrag ausgewählt");
  }
  function closeOther() {
    setOtherValue("");
    setNoneValue("");
    setOtherOpen(false);
    setPicker(false);
    setPicked(field.present ? startKey : null);
  }
  function show(card: Card | null) {
    if (!card) return;
    if (card.entry) onShowEvidence?.(card.entry);
    else onShowPage?.(card.page, card.quote);
  }

  // Tasten (nicht in Eingabefeldern): ↑↓ Karten, Enter ausführen, A anderer Wert, N nicht im Vertrag, S später, D zeigen, Esc Feld schließen.
  const latest = useRef({ action, openOther, chooseNone, closeOther, show, defer: () => void decide("defer", {}, "Zurückgestellt."), cards, picked, selected, otherOpen, canNone, canDefer });
  latest.current = { action, openOther, chooseNone, closeOther, show, defer: () => void decide("defer", {}, "Zurückgestellt."), cards, picked, selected, otherOpen, canNone, canDefer };
  useEffect(() => {
    if (!canReview || showDecided) return undefined;
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || busy || document.querySelector('[role="dialog"]')) return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      const type = (target as HTMLInputElement | null)?.type;
      const typing = tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable || (tag === "INPUT" && type !== "radio");
      const now = latest.current;
      if (event.key === "Escape" && now.otherOpen) { event.preventDefault(); now.closeOther(); return; }
      if (typing) return;
      if (event.key === "Enter" && tag !== "BUTTON" && tag !== "A" && now.action && !now.action.disabled) { event.preventDefault(); now.action.run(); }
      else if ((event.key === "ArrowDown" || event.key === "ArrowUp") && now.cards.length > 1 && type !== "radio") {
        event.preventDefault();
        const at = now.cards.findIndex((card) => card.candidate.key === now.picked);
        const next = now.cards[(Math.max(at, 0) + (event.key === "ArrowDown" ? 1 : -1) + now.cards.length) % now.cards.length];
        choose(next.candidate.key);
      } else if (event.key === "a" || event.key === "A") { event.preventDefault(); now.openOther(); }
      else if ((event.key === "n" || event.key === "N") && now.canNone) { event.preventDefault(); now.chooseNone(); }
      else if ((event.key === "s" || event.key === "S") && now.canDefer) { event.preventDefault(); now.defer(); }
      else if (event.key === "d" || event.key === "D") { event.preventDefault(); now.show(now.selected ?? now.cards[0] ?? null); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canReview, showDecided, busy]);

  // ---- Kopf
  const level = levelOf(field.tier);
  const multi = cards.length > 1 || field.status === "conflict" || field.status === "changed";
  const chip = showDecided ? <Signal tone="done" size="sm">Geprüft</Signal>
    : field.status === "deferred" ? <Signal tone="neutral" size="sm">Zurückgestellt</Signal>
      : !field.present ? <Signal tone="warning" size="sm">Nicht gefunden</Signal>
        : multi ? <Signal tone="warning" size="sm">{cards.length > 1 ? `${cards.length} Werte` : "Abweichung"}</Signal>
          : <Signal tone="neutral" size="sm">Offen</Signal>;
  const subline = showDecided ? null
    : !field.present ? "Im Dokument wurde kein Wert gefunden. Nichts wird vermutet."
      : cards.length > 1 ? "Welcher gilt? Im Zweifel der spätere Nachtrag."
        : cards[0]?.candidate.sources.some((source) => source.source === "stored") && cards[0]?.candidate.sources.some((source) => source.source === "document")
          ? "Dokument und MedFlux sagen dasselbe"
          : cards[0]?.candidate.is_current ? "Wert aus MedFlux – bitte mit dem Dokument vergleichen" : "Wert aus dem Dokument – noch nicht gespeichert";

  const decisionNote = field.history.find((entry) => (entry.kind === "confirmed" || entry.kind === "corrected" || entry.kind === "decision") && entry.detail && !AUTO_NOTE.test(entry.detail))?.detail ?? null;
  const others = cards.filter((card) => !card.candidate.is_current);
  const decidedCard = cards.find((card) => card.candidate.is_current) ?? cards[0] ?? null;
  const placeholder = field.fact_key.startsWith("dates.") ? "TT.MM.JJJJ" : "Wert eingeben …";
  const mode = /^costs\./.test(field.fact_key) || /_(months|days|years|count|percent|rate)$/.test(field.fact_key) ? "decimal" : "text";

  return <div className={`vp${showDecided ? " is-decided" : ""}`}>
    <header className={`vp-head vp-head--${level}`}>
      <div className="vp-meta">
        <span className={`vp-level vp-level--${level}`}>{LEVEL_NAME[level]}</span>
        <span className="vp-bar" aria-hidden="true" />
        <span>Angabe {position.index + 1} von {position.total}</span>
        <span className="vp-sp" />
        <span className="vp-arrows">
          <button type="button" className="btn btn-sm vp-arrow" onClick={onPrev} disabled={position.index <= 0} aria-label="Vorherige Angabe" title="Vorherige Angabe">{BACK}</button>
          <button type="button" className="btn btn-sm vp-arrow" onClick={onNext} disabled={position.index >= position.total - 1} aria-label="Nächste Angabe" title={nextLabel ? `Nächste: ${nextLabel}` : "Nächste Angabe"}>{NEXT}</button>
        </span>
      </div>
      <div className="vp-titlerow">
        <h2 ref={headingRef} tabIndex={-1} className="vp-title">{field.label}</h2>
        <span className="vp-chip">{chip}</span>
      </div>
      {subline ? <p className="vp-sub">{subline}</p> : null}
    </header>

    <div className="vp-body">
      <p className="visually-hidden" aria-live="polite">{announce}</p>
      {stale ? <InlineAlert tone="info" role="status">Das Feld wurde inzwischen geändert. Der aktuelle Stand ist geladen – bitte neu entscheiden.</InlineAlert> : null}

      {showDecided ? <>
        <section className="vp-answer" aria-label="Geprüfter Wert">
          <span className="vp-answer-label">Geprüfter Wert</span>
          <p className="vp-big">{decidedCard?.shown ?? shownValue(review, field.fact_key, field.current) ?? (field.status === "absent" || field.fact_state === "voided" ? "Nicht im Vertrag" : "–")}</p>
        </section>
        {primaryEntry || decidedCard?.quote ? <div className="vp-src">
          <b>{decidedCard?.where}</b>
          {decidedCard?.quote ? <span className="vp-quote" title={decidedCard.quote}>„{decidedCard.quote}“</span> : null}
          <button type="button" className="vp-link" onClick={() => show(decidedCard)}>Im Dokument zeigen</button>
        </div> : null}
        {sources}
        {derivedBlock}
        <div className="vp-decided">
          {CHECK_CIRCLE}
          <span>{field.fact_state === "corrected" ? "Übernommen" : "Bestätigt"}{reviewer ? <> von <b>{reviewer}</b></> : null}{field.reviewed_at ? ` · ${formatDateTime(field.reviewed_at)}` : ""}</span>
          <span className="vp-sp" />
          {canReview ? <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setEditing(true); setPicked(current?.key ?? null); }}>{PEN}Ändern</button> : null}
        </div>
        {decisionNote ? <div className="vp-src vp-src--plain"><b>Begründung</b><span>{decisionNote}</span></div> : null}
        {others.length ? <section className="vp-alt" aria-label="Anderer Vorschlag">
          <p className="vp-alt-head">
            <span className="vp-alt-icon" aria-hidden="true">{WARN}</span>
            <b>{others.length === 1 ? "Anderer Vorschlag im Vertrag" : `${others.length} andere Vorschläge im Vertrag`}</b>
          </p>
          <ul className="vp-alt-list">{others.map((card) => <li key={card.candidate.key} className="vp-alt-item">
            <strong className="vp-alt-value">{card.shown}</strong>
            <span className="vp-where">{card.where}</span>
            {card.quote ? <span className="vp-quote" title={card.quote}>„{card.quote}“</span> : null}
            <span className="vp-alt-actions">
              {canReview ? <button type="button" className="btn btn-sm" onClick={() => { setEditing(true); setPicked(card.candidate.key); }}>Diesen Wert wählen</button> : null}
              <button type="button" className="vp-link" onClick={() => show(card)} disabled={!card.entry && card.page == null}>{DOC}Im Dokument zeigen</button>
            </span>
          </li>)}</ul>
        </section> : null}
        {field.history.length ? <>
          <button type="button" className="vp-fold" aria-expanded={fold === "history"} onClick={() => setFold(fold === "history" ? null : "history")}>
            {HISTORY}Verlauf<small>{field.history.length === 1 ? "1 Eintrag" : `${field.history.length} Einträge`}</small>
          </button>
          {fold === "history" ? <ul className="vp-fold-body">{field.history.map((entry, position2) => <li key={`${entry.at}-${position2}`}>
            <strong>{entry.label}</strong><span>{[entry.by, entry.at ? formatDateTime(entry.at) : null].filter(Boolean).join(" · ")}</span>
            {entry.detail ? <span className="vp-quote">{entry.detail}</span> : null}
          </li>)}</ul> : null}
        </> : null}
      </> : <>
        {cards.length ? <div className="vp-cards" role="radiogroup" aria-label="Welcher Wert gilt?">
          {cards.map((card) => {
            const id = `${ids}-${card.candidate.key}`;
            const on = picked === card.candidate.key;
            const same = cards.length === 1 && card.candidate.sources.some((source) => source.source === "stored") && card.candidate.sources.some((source) => source.source === "document");
            const excluded = Boolean(card.entry?.excluded);
            const menu = canReview && card.entry ? [
              ...(excluded ? [{ label: "Fundstelle wiederherstellen", onSelect: () => void evidenceAction(card.entry!, "restore") }]
                : [
                  ...(!card.entry.primary && card.count > 1 ? [{ label: "Als Hauptnachweis", onSelect: () => void evidenceAction(card.entry!, "primary") }] : []),
                  { label: "Diese Fundstelle ausschließen", onSelect: () => setExclude({ id: card.entry!.evidence_id, reason: "", note: "" }) },
                ]),
            ] : [];
            return <div key={card.candidate.key} className={`vp-card${on ? " is-on" : ""}${same ? " is-same" : ""}${excluded ? " is-excluded" : ""}`}>
              <input id={id} type="radio" name={`${ids}-pick`} className="vp-radio" checked={on} disabled={!canReview || busy} onChange={() => choose(card.candidate.key)} />
              <label htmlFor={id} className="vp-card-body">
                <span className="vp-value">{card.shown}{card.candidate.is_current ? <span className="vp-tag">in MedFlux</span> : null}{excluded ? <span className="vp-tag">ausgeschlossen</span> : null}</span>
                <span className="vp-where">{card.where}{cards.length === 1 ? literal(card.entry) : ""}{card.count > 1 ? ` · ${card.count} Fundstellen` : ""}</span>
                {card.quote ? <span className="vp-quote" title={card.quote}>„{card.quote}“</span> : null}
                {card.candidate.proposal_id ? <span className="vp-where">Aus Analyse #{card.candidate.run_number}.{" "}
                  {onOpenAnalysis ? <span className="vp-inline-link">Dort übernehmen</span> : "Übernehmen können Sie ihn in der KI-Analyse."}</span> : null}
              </label>
              <div className="vp-card-tools">
                <button type="button" className="vp-link" onClick={() => show(card)} disabled={!card.entry && card.page == null}>{DOC}Im Dokument zeigen</button>
                {card.candidate.proposal_id && onOpenAnalysis ? <button type="button" className="vp-link" onClick={onOpenAnalysis}>Dort übernehmen</button> : null}
                {menu.length ? <ActionMenu items={menu} label={`Weitere Aktionen zu ${card.shown}`} /> : null}
              </div>
            </div>;
          })}
        </div> : null}
        {sources}
        {derivedBlock}

        {unresolvedSource ? <InlineAlert tone="warning" role="status">
          {field.source_state === "unavailable" ? "Das Dokument ist nicht verfügbar." : "Die Fundstelle konnte nicht aufgelöst werden."} Der Wert gilt hier nicht als belegt – bestätigen Sie ihn nur, wenn Sie ihn anders prüfen können.
        </InlineAlert> : null}

        {exclude && canReview ? <form className="vp-form" aria-label="Fundstelle ausschließen" onSubmit={(event) => {
          event.preventDefault();
          const entry = field.evidence.find((item) => item.evidence_id === exclude.id);
          if (entry) void evidenceAction(entry, "exclude", { reason: exclude.reason, note: exclude.note });
        }}>
          <strong>Fundstelle ausschließen</strong>
          <p className="vp-muted">Die Fundstelle bleibt erhalten und sichtbar; der Wert des Felds ändert sich dadurch nicht.</p>
          <label className="vp-field">Grund
            <select value={exclude.reason} onChange={(event) => setExclude({ ...exclude, reason: event.target.value })} required>
              <option value="">Bitte wählen</option>
              {review.exclusion_reasons.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
            </select>
          </label>
          <label className="vp-field">Notiz{exclude.reason === "other" ? " (erforderlich)" : " (optional)"}
            <input value={exclude.note} onChange={(event) => setExclude({ ...exclude, note: event.target.value })} required={exclude.reason === "other"} />
          </label>
          <div className="vp-row">
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !exclude.reason}>{busy ? "Wird gespeichert…" : "Ausschließen"}</button>
            <button type="button" className="btn btn-sm" onClick={() => setExclude(null)}>Abbrechen</button>
          </div>
        </form> : null}

        {canReview ? <section className={`vp-other${isOther || isNone ? " is-on" : ""}`} aria-label="Selbst entscheiden">
          <p className="vp-other-title">{cards.length ? "Stimmt keiner dieser Werte?" : "Kein Wert gefunden"}</p>
          <div className={`vp-choices${canNone ? "" : " is-single"}`}>
            <button type="button" className={`vp-choice${isOther ? " is-on" : ""}`} aria-pressed={isOther} onClick={isOther && otherOpen ? closeOther : openOther}>
              <span className="vp-choice-icon" aria-hidden="true">{PEN}</span>
              <span className="vp-choice-text"><b>Selbst eintragen</b></span>
              <Kbd>A</Kbd>
            </button>
            {canNone ? <button type="button" className={`vp-choice${isNone ? " is-on" : ""}`} aria-pressed={isNone} onClick={isNone ? closeOther : chooseNone}>
              <span className="vp-choice-icon" aria-hidden="true">{SEARCH}</span>
              <span className="vp-choice-text"><b>Nicht im Vertrag</b></span>
              <Kbd>N</Kbd>
            </button> : null}
          </div>
          {isNone ? <div className="vp-entry">
            <div className="vp-entry-head"><label className="vp-entry-label" htmlFor="vp-none-value">Wert, der trotzdem gilt (optional)</label></div>
            <input id="vp-none-value" className="vp-input vp-input--lg" inputMode={mode === "decimal" ? "decimal" : "text"} placeholder="z. B. mündlich vereinbart – leer lassen, wenn es keinen Wert gibt" value={noneValue} onChange={(event) => setNoneValue(event.target.value)} />
          </div> : null}
          {otherOpen ? <div className="vp-entry">
            <div className="vp-entry-head"><span className="vp-entry-label" aria-hidden="true">Ihr Wert</span><button type="button" className="vp-link" onClick={closeOther}>Abbrechen</button></div>
            <input ref={otherInput} className="vp-input vp-input--lg" aria-label="Eigener Wert" inputMode={mode === "decimal" ? "decimal" : "text"} placeholder={placeholder} value={otherValue}
              onChange={(event) => setOtherValue(event.target.value)} onFocus={() => setPicked(OTHER)} />
            {pickerStart ? <>
              <button type="button" className="btn btn-sm vp-mark" aria-expanded={picker} onClick={() => setPicker(!picker)}>{MARK}Stelle im Dokument markieren</button>
              {picker ? <PageTextPicker contractId={contractId} orgSlug={orgSlug} documentVersionId={pickerStart.documentVersionId} page={pickerStart.page} documents={pickerDocs}
                onPick={(text) => { setOtherValue(text); setPicker(false); }} /> : null}
            </> : null}
          </div> : null}
        </section> : <p className="vp-muted">Nur Lesen – entscheiden dürfen Prüfende und das Vertragsmanagement.</p>}

        {needsReason && canReview ? <input className="vp-input vp-input--sm" aria-label="Begründung (optional)" placeholder="Begründung (optional)" value={note} onChange={(event) => setNote(event.target.value)} /> : null}
        {error ? <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => setError(null)}>Schließen</button>}>{error}</InlineAlert> : null}
        {children}
      </>}
    </div>

    <footer className="vp-foot">
      <div className="vp-actions">
        <div className="vp-foot-row">
          <button type="button" className="btn vp-arrow" onClick={onPrev} disabled={position.index <= 0} aria-label="Zur vorherigen Angabe" title="Vorherige Angabe">{BACK}</button>
          {!showDecided && action ? <button type="button" className="btn btn-primary vp-primary" disabled={action.disabled} onClick={action.run} title="Speichert und geht zur nächsten Angabe (Enter)">
            {busy ? "Wird gespeichert…" : action.label}
          </button> : showDecided ? <button type="button" className="btn btn-primary vp-primary" onClick={onNext}>
            Weiter
          </button> : <span className="vp-primary-spacer" />}
          <button type="button" className="btn vp-arrow" onClick={onNext} disabled={position.index >= position.total - 1} aria-label="Zur nächsten Angabe" title={nextLabel ? `Nächste: ${nextLabel}` : "Nächste Angabe"}>{NEXT}</button>
        </div>
        {!showDecided && action ? <div className="vp-secondary">
          {canDefer ? <button type="button" className="vp-link" disabled={busy} onClick={() => void decide("defer", {}, "Zurückgestellt.")}>Später prüfen<Kbd>S</Kbd></button> : null}
          {editing ? <button type="button" className="vp-link" onClick={() => { setEditing(false); setPicked(current?.key ?? null); }}>Abbrechen</button> : null}
        </div> : null}
      </div>
    </footer>
  </div>;
}
