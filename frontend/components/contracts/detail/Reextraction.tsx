"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Button from "@/components/ui/Button";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Dialog from "@/components/ui/Dialog";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { sectionByKey, wordDiff, type EvidenceSection } from "@/lib/evidence";
import { MISSING_SEARCH, SEARCH_PARAM, baseFieldKey } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";
import {
  applyReextraction,
  cancelReextraction,
  confirmUnchanged,
  decideReextraction,
  discardReextraction,
  getReextraction,
  getReextractionModels,
  getRollbackPreview,
  rollbackToAnalysis,
  startReextraction,
  type AnalysisHistoryItem,
  type Proposal,
  type ProposalDecision,
  type ReextractionModel,
  type ReextractionRun,
  type ReextractionState,
  type RollbackEntry,
  type StartReextraction,
} from "@/lib/domain-api/reextraction";
import { Diff, SectionChip } from "./EvidenceReviewMode";

const POLL_MS = 4000;
const SAFE_CONFIDENCE = 0.95;

type FieldOption = { key: string; label: string };
type Mode = StartReextraction["mode"];

const svg = (body: ReactNode, className = "ra-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const SPARK = svg(<path d="M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z" />);
const PLUS = svg(<path d="M12 5v14M5 12h14" />);
const TARGET = svg(<><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>);
const REFRESH = svg(<><path d="M21 12a9 9 0 1 1-2.6-6.4" /><path d="M21 3v6h-6" /></>);
const UNDO = svg(<><path d="M9 14 4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></>);
const NEXT = svg(<path d="M5 12h14M13 6l6 6-6 6" />);
// Kachel im Kartenkopf: Größe und Strich kommen wie bei allen Karten aus `.collapsible-icon svg`.
const TILE = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z" /></svg>;

const MODES: { key: Mode; label: string; text: string; icon: ReactNode }[] = [
  { key: "supplement", label: "Ergänzen", text: "Nur leere oder nicht gefundene Angaben suchen. Bestätigte Werte bleiben unberührt.", icon: PLUS },
  { key: "sections", label: "Bereich neu erfassen", text: "Ausgewählte Bereiche komplett neu auswerten, der Rest bleibt wie er ist.", icon: TARGET },
  { key: "full", label: "Vollständig neu bewerten", text: "Alles neu auswerten und jede Angabe einzeln prüfen – alt gegen neu, Feld für Feld.", icon: REFRESH },
];

const DECISION: Record<Exclude<ProposalDecision, "pending">, { tone: SignalTone; label: string }> = {
  accepted: { tone: "done", label: "Übernommen" },
  kept_old: { tone: "neutral", label: "Behalten" },
  manual: { tone: "neutral", label: "Selbst erfasst" },
  rejected: { tone: "neutral", label: "Abgelehnt" },
  rolled_back: { tone: "neutral", label: "Zurückgenommen" },
};

/** Bereiche der erneuten Erfassung, benannt nach den Reitern der Vertragsakte (wie `facts.SECTIONS` im Backend). */
export const ANALYSIS_SECTION_LABEL: Record<string, string> = {
  partner: "Vertragsdaten",
  term: "Fristen & Aufgaben",
  cost: "Finanzen",
  services: "Leistungen & SLA",
  device: "Verknüpfungen (Geräte)",
};

/** Bereich eines Vorschlags: Kennfarbe wie in „Nachweise prüfen“, Name wie der Reiter. */
export function analysisSection(key: string): EvidenceSection {
  const section = sectionByKey(key);
  return { ...section, label: ANALYSIS_SECTION_LABEL[key] ?? section.label };
}

/** Vertragsdaten-Feld (Basisname, z. B. notice_period) → Angaben zum Suchen. */
export function fieldSearchMap(state: ReextractionState | null): Map<string, FieldOption[]> {
  const out = new Map<string, FieldOption[]>();
  for (const [key, options] of Object.entries(state?.field_search ?? {})) {
    const base = baseFieldKey(key);
    const known = out.get(base) ?? [];
    for (const option of options) if (!known.some((item) => item.key === option.key)) known.push(option);
    out.set(base, known);
  }
  return out;
}

/** „4“, „4-6“, „5–9, 12“ → Seitenzahlen; null bei ungültiger Eingabe. Höchstens 20 Seiten. */
export function parsePages(text: string): number[] | null {
  const trimmed = text.trim();
  if (!trimmed || /^alle$/i.test(trimmed)) return [];
  const pages = new Set<number>();
  for (const part of trimmed.split(/[,;\s]+/).filter(Boolean)) {
    const match = /^(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?$/.exec(part);
    if (!match) return null;
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    if (from < 1 || to < from || to - from > 19) return null;
    for (let page = from; page <= to; page += 1) pages.add(page);
  }
  return pages.size > 20 ? null : [...pages].sort((a, b) => a - b);
}

/** Entscheidbare Vorschläge, die noch offen sind (neu, abweichend, nicht mehr gefunden). */
export function openProposals(rows: Proposal[]): Proposal[] {
  return rows.filter((row) => row.decision === "pending" && row.kind !== "unchanged");
}

/** Unveränderte, nicht geschützte Angaben mit Sicherheit ≥ 0,95 (Sammelbestätigung). */
export function safeUnchanged(rows: Proposal[]): Proposal[] {
  return rows.filter((row) => row.kind === "unchanged" && !row.protected && row.decision === "pending" && row.confidence != null && row.confidence >= SAFE_CONFIDENCE);
}

function message(error: unknown, fallback: string) {
  return error instanceof ApiError && error.message ? error.message : fallback;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const dateDe = (iso: string | null) => (iso ? formatDate(iso) : "");
const timeDe = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "");
const confidenceTone = (value: number): SignalTone => (value >= 0.9 ? "done" : value >= 0.7 ? "warning" : "critical");

/** Fehlende Felder (z. B. von einem älteren Backend) mit leeren Werten auffüllen statt abzustürzen. */
export function withDefaults(state: ReextractionState): ReextractionState {
  return {
    ...state,
    missing: state.missing ?? [],
    rows: state.rows ?? [],
    open_fields: state.open_fields ?? 0,
    evidence_count: state.evidence_count ?? 0,
    review_minutes: state.review_minutes ?? 0,
    duration_minutes: state.duration_minutes ?? null,
    sections: state.sections ?? [],
    history: state.history ?? [],
    new_document: state.new_document ?? null,
    can_review: state.can_review ?? false,
  };
}

/** Stand der erneuten Erfassung; fragt nach, solange ein Lauf wartet oder läuft. */
export function useReextraction(contractId: string, orgSlug: string) {
  const [state, setState] = useState<ReextractionState | null>(null);
  // Fehler beim Laden (z. B. Datenbank noch nicht aktualisiert): sichtbar machen statt die Karte zu verstecken.
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    getReextraction(orgSlug, contractId)
      .then((value) => { setState(value ? withDefaults(value) : null); setError(null); })
      .catch((err) => { setState(null); setError(message(err, "Die KI-Analyse ist gerade nicht erreichbar.")); });
  }, [contractId, orgSlug]);
  useEffect(reload, [reload]);
  const active = state?.run?.status === "queued" || state?.run?.status === "running";
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [active, reload]);
  return { state, reload, error };
}

/** Hinweis im Kopf der Vertragsakte: läuft gerade / Ergebnis liegt vor. */
export function ReextractionBanner({ state, onOpen }: { state: ReextractionState | null; onOpen: () => void }) {
  const run = state?.run;
  if (!run) return null;
  if (run.status === "queued" || run.status === "running") {
    return <InlineAlert tone="info" role="status" action={<Button size="sm" onClick={onOpen}>Anzeigen</Button>}>
      {run.status === "queued" ? `Analyse #${run.number} wartet auf die lokale KI.` : `Analyse #${run.number} läuft. Sie können weiterarbeiten.`}
    </InlineAlert>;
  }
  if (run.status === "ready" && !run.stale) {
    const open = openProposals(state?.rows ?? []).length;
    return <InlineAlert tone="info" role="status" action={<Button size="sm" onClick={onOpen}>{open ? "Prüfen" : "Ansehen"}</Button>}>
      {open ? `Analyse #${run.number} fertig: ${plural(open, "Vorschlag", "Vorschläge")} zum Prüfen.` : `Analyse #${run.number} fertig: keine neuen Vorschläge.`}
    </InlineAlert>;
  }
  return null;
}

interface PanelProps {
  contractId: string;
  orgSlug: string;
  state: ReextractionState | null;
  reload: () => void;
  /** Nach einer Übernahme oder Zurücknahme: Vertragsakte neu laden. */
  onApplied: () => void;
  /** Quelle im Dokument zeigen (Seite). */
  onShowPage?: (page: number) => void;
  /** „Selbst erfassen“: zu den Vertragsdaten (Feld, falls bekannt). */
  onEditManually?: (registerKey?: string) => void;
  /** „Stelle im Dokument markieren“: Angabe aus dem Text übernehmen. */
  onMarkInDocument?: () => void;
  /** „Vorschläge prüfen“ / „Vergleichen“ / „Prüfen“: geführter Modus, optional ab einer Angabe. */
  onReviewProposals?: (startKey: string | null) => void;
  /** Nach „Bestätigungen zurücksetzen“: alle Nachweise einzeln prüfen. */
  onReviewEvidence?: () => void;
  /** Ladefehler des Stands (wird angezeigt statt die Karte zu verstecken). */
  loadError?: string | null;
}

/** Karte „Erneut aus dem Dokument erfassen“ (Dokumente → Dokument): Auswahl → läuft → Ergebnis. */
export default function ReextractionPanel({ contractId, orgSlug, state: given, reload, onApplied, onShowPage, onEditManually, onMarkInDocument, onReviewProposals, onReviewEvidence, loadError = null }: PanelProps) {
  const state = useMemo(() => (given ? withDefaults(given) : null), [given]);
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchFor = searchParams?.get(SEARCH_PARAM) ?? null;
  const [preset, setPreset] = useState<FieldOption[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSafe, setConfirmSafe] = useState(false);
  const [rollback, setRollback] = useState<AnalysisHistoryItem | null>(null);
  const run = state?.run ?? null;
  const rows = useMemo(() => state?.rows ?? [], [state?.rows]);

  // „Im Dokument suchen“ am leeren Feld: Ergänzen mit genau diesem Feld vorbereiten, Parameter danach entfernen.
  const handledSearch = useRef<string | null>(null);
  useEffect(() => {
    if (!searchFor || !state || handledSearch.current === searchFor) return;
    handledSearch.current = searchFor;
    if (searchFor === MISSING_SEARCH) setPreset(state.missing.length ? state.missing : null);
    else {
      const fields = fieldSearchMap(state).get(baseFieldKey(searchFor));
      if (fields?.length) setPreset(fields);
    }
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.delete(SEARCH_PARAM);
    router.replace(`${pathname ?? ""}?${params.toString()}`, { scroll: false });
  }, [searchFor, state, pathname, router, searchParams]);

  // Eigener Unterreiter „KI-Analyse“: nie leer, immer mit Grund.
  if (!state) {
    return <section className="cw-section ra-unavailable" aria-labelledby="ra-unavailable-heading">
      <h2 id="ra-unavailable-heading">Erneut aus dem Dokument erfassen</h2>
      {loadError
        ? <InlineAlert tone="warning" role="alert" action={<Button size="sm" onClick={reload}>Erneut laden</Button>}>
          {`Die KI-Analyse ist gerade nicht verfügbar (${loadError}). Ist MedFlux auf dem neuesten Stand (Datenbank aktualisiert)?`}
        </InlineAlert>
        : <p className="cw-muted" role="status">Wird geladen…</p>}
    </section>;
  }

  async function act(work: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    try {
      await work();
      if (done) toast(done, "success");
      reload();
    } catch (err) {
      setError(message(err, "Die Aktion ist fehlgeschlagen."));
    } finally {
      setBusy(false);
    }
  }

  const active = run?.status === "queued" || run?.status === "running";
  const ready = run?.status === "ready";
  const open = openProposals(rows);
  const safe = safeUnchanged(rows);
  const accepted = run?.summary.accepted ?? 0;
  const last = state.history.find((item) => item.mode !== "rollback") ?? null;

  const title = ready && run ? `Ergebnis der Analyse #${run.number}`
    : state.first_analysis ? "Mit der KI aus dem Dokument erfassen" : "Erneut aus dem Dokument erfassen";
  const description = ready && run
    ? [run.mode_label, `${dateDe(run.finished_at)} ${timeDe(run.finished_at)}`.trim(), accepted ? `${accepted} übernommen` : "noch nichts übernommen"].filter(Boolean).join(" · ")
    : active ? "Während der Analyse"
      : state.first_analysis
        ? "Die lokale KI wertet das Dokument aus. Sie sehen jeden gefundenen Wert und übernehmen nur, was Sie auswählen."
        : "Ergebnisse werden als Vorschläge gesammelt. Ihre Vertragsdaten ändern sich erst, wenn Sie sie übernehmen.";
  const headerActions = ready && run
    ? <div className="ra-head-actions">
      <Button size="sm" onClick={() => act(() => discardReextraction(orgSlug, contractId, run.id), "Offene Vorschläge verworfen.")} disabled={busy}>Alles verwerfen</Button>
      <Button size="sm" variant="primary" disabled={busy || run.stale || open.length === 0} onClick={() => onReviewProposals?.(null)}>{NEXT}Vorschläge prüfen ({open.length})</Button>
    </div>
    : active ? <Signal tone="info" size="sm">{run?.status === "queued" ? "Wartet" : "Läuft"}</Signal>
      : last ? <Signal tone="neutral" size="sm">{`Letzte Analyse #${last.number}${last.date ? ` · ${dateDe(last.date)}` : ""}`}</Signal> : null;

  return <CollapsibleSection
    id="rg-reextraction"
    title={title}
    description={description}
    tone="ai"
    icon={TILE}
    actions={headerActions}
    forceOpen
    className="ra"
  >
    <div className="ra-body">
      {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
      {!state.can_start && !run ? <p className="cw-muted">{state.blocked_reason
        ?? "Eine neue Analyse starten dürfen das Vertragsmanagement und die Administration. Ergebnisse und Verlauf sehen Sie hier."}</p> : null}

      {active && run ? <RunningBox run={run} durationMinutes={state.duration_minutes} busy={busy}
        onCancel={() => act(() => cancelReextraction(orgSlug, contractId, run.id), "Die Analyse wird abgebrochen.")} /> : null}

      {ready && run ? <ResultView
        run={run}
        rows={rows}
        busy={busy}
        canReview={state.can_review}
        safeCount={safe.length}
        onConfirmSafe={() => setConfirmSafe(true)}
        onShowPage={onShowPage}
        onReview={(key) => onReviewProposals?.(key)}
        onReviewEvidence={onReviewEvidence}
        onAccept={(row) => act(async () => {
          const result = await applyReextraction(orgSlug, contractId, run.id, [row.key]);
          toast(result.message, "success");
          onApplied();
        })}
        onKeep={(row) => act(() => decideReextraction(orgSlug, contractId, run.id, [row.key], "kept_old"), `${row.label}: bisheriger Wert bleibt.`)}
        onRetry={() => act(() => discardReextraction(orgSlug, contractId, run.id))}
        onEditManually={onEditManually}
        onMarkInDocument={onMarkInDocument}
      /> : null}

      {!active && !ready && run?.status === "failed" ? <InlineAlert tone="critical" role="alert">{run.message ?? `Analyse #${run.number} ist fehlgeschlagen.`}</InlineAlert> : null}

      {!active && !ready && state.can_start ? <Chooser
        contractId={contractId}
        orgSlug={orgSlug}
        state={state}
        preset={preset}
        onClearPreset={() => setPreset(null)}
        onStarted={() => { setPreset(null); toast("Analyse gestartet. Sie läuft im Hintergrund.", "info"); reload(); }}
      /> : null}

      {state.history.length ? <History items={state.history} currentId={ready ? run?.id ?? null : null} canRollback={state.can_start && !active} onRollback={setRollback} /> : null}
    </div>

    <Dialog open={confirmSafe} title="Alle unveränderten bestätigen?" onClose={() => setConfirmSafe(false)}
      description={`${plural(safe.length, "Angabe ist", "Angaben sind")} im Dokument unverändert erkannt worden (Sicherheit ab 95 %). Sie gelten danach als geprüft; die Werte ändern sich nicht.`}
      actions={<>
        <Button onClick={() => setConfirmSafe(false)}>Abbrechen</Button>
        <Button variant="primary" onClick={() => { setConfirmSafe(false); if (run) void act(() => confirmUnchanged(orgSlug, contractId, run.id), `${plural(safe.length, "Angabe", "Angaben")} bestätigt.`); }}>{safe.length} bestätigen</Button>
      </>} />

    {rollback ? <RollbackDialog contractId={contractId} orgSlug={orgSlug} item={rollback} onClose={() => setRollback(null)}
      onDone={(text) => { setRollback(null); toast(text, "success"); reload(); onApplied(); }} /> : null}
  </CollapsibleSection>;
}

function Chooser({ contractId, orgSlug, state, preset, onClearPreset, onStarted }: {
  contractId: string;
  orgSlug: string;
  state: ReextractionState;
  /** Gezielt gesuchte Angaben („Im Dokument suchen“), sonst null. */
  preset: FieldOption[] | null;
  onClearPreset: () => void;
  onStarted: () => void;
}) {
  const canSupplement = state.open_fields > 0 || Boolean(preset?.length) || Boolean(state.first_analysis);
  const [mode, setMode] = useState<Mode>(canSupplement ? "supplement" : "sections");
  useEffect(() => { if (preset?.length) setMode("supplement"); }, [preset]);
  const [sections, setSections] = useState<Set<string>>(new Set());
  const [protect, setProtect] = useState(true);
  const [reset, setReset] = useState(false);
  const [askReset, setAskReset] = useState(false);
  const [hint, setHint] = useState("");
  const [pagesText, setPagesText] = useState("");
  const pages = parsePages(pagesText);
  const [reread, setReread] = useState(state.reread_suggested);
  const [models, setModels] = useState<ReextractionModel[] | null>(null);
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getReextractionModels(orgSlug, contractId)
      .then((result) => { if (alive) { setModels(result.models); setModel(result.current_model ?? ""); } })
      .catch(() => { if (alive) setModels([]); });
    return () => { alive = false; };
  }, [contractId, orgSlug]);
  useEffect(() => { if (mode !== "full") setReset(false); }, [mode]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await startReextraction(orgSlug, contractId, {
        mode,
        fields: mode === "supplement" ? (preset ?? []).map((item) => item.key) : [],
        sections: mode === "sections" ? [...sections] : [],
        page_hint: pages ?? [],
        hint: hint.trim() || null,
        protect_manual: protect,
        reset_confirmations: mode === "full" && reset,
        reread_document: reread,
        model_id: model || null,
      });
      onStarted();
    } catch (err) {
      setError(message(err, "Die Analyse konnte nicht gestartet werden."));
    } finally {
      setBusy(false);
    }
  }

  const tag = (key: Mode) => {
    if (key === "supplement") {
      return preset?.length ? <Signal tone="done" size="sm">{`Sicher · ${plural(preset.length, "gesuchte Angabe", "gesuchte Angaben")}`}</Signal>
        : <Signal tone="done" size="sm">{`Sicher · ${plural(state.open_fields, "offenes Feld", "offene Felder")}`}</Signal>;
    }
    if (key === "sections") return <Signal tone="neutral" size="sm">{sections.size ? plural(sections.size, "Bereich gewählt", "Bereiche gewählt") : "Bereiche wählen"}</Signal>;
    return state.evidence_count
      ? <Signal tone="warning" size="sm">{`${state.evidence_count} Nachweise · ca. ${state.review_minutes} Min. Prüfung`}</Signal>
      : <Signal tone="warning" size="sm">Alle Angaben neu</Signal>;
  };
  const invalid = pages === null || (mode === "sections" && sections.size === 0) || (mode === "supplement" && !canSupplement);
  const duration = state.duration_minutes;

  return <div className="ra-choose">
    <fieldset className="ra-modes">
      <legend className="visually-hidden">Modus</legend>
      {MODES.map((item) => {
        const disabled = item.key === "supplement" && !canSupplement;
        return <label key={item.key} className={`ra-mode${mode === item.key ? " is-on" : ""}${disabled ? " is-disabled" : ""}`}>
          <input type="radio" name="ra-mode" value={item.key} checked={mode === item.key} disabled={disabled} onChange={() => setMode(item.key)} />
          <span className="ra-mode-body">
            <span className="ra-mode-title">{item.icon}{item.label}</span>
            <span className="ra-mode-text">{item.key === "supplement" && disabled ? "Es gibt keine leeren Angaben zum Ergänzen." : item.text}</span>
            <span className="ra-mode-tag">{tag(item.key)}</span>
          </span>
        </label>;
      })}
    </fieldset>

    <div className="ra-opts">
      <p className="ra-opts-title">Optionen</p>
      {preset?.length && mode === "supplement" ? <p className="ra-preset">Gesucht: {preset.map((item) => item.label).join(", ")} <button type="button" className="rg-link" onClick={onClearPreset}>Alle leeren Angaben suchen</button></p> : null}
      <div className="ra-chips" role="group" aria-label="Bereiche (nur bei „Bereich neu erfassen“)">
        {state.sections.map((item) => {
          const on = sections.has(item.key);
          return <button key={item.key} type="button" className={`ra-chip erm-section erm-tone--${sectionByKey(item.key).tone}${on ? " is-on" : ""}`}
            aria-pressed={on} disabled={mode !== "sections"}
            onClick={() => setSections((prev) => { const next = new Set(prev); if (next.has(item.key)) next.delete(item.key); else next.add(item.key); return next; })}>{item.label}</button>;
        })}
      </div>
      <label className="ra-check">
        <input type="checkbox" checked={protect} onChange={(event) => setProtect(event.target.checked)} />
        <span>Manuell gesetzte Werte schützen<small>Felder mit Herkunft „Manuell“ werden nicht vorgeschlagen (empfohlen)</small></span>
      </label>
      {mode === "full" ? <label className="ra-check">
        <input type="checkbox" checked={reset} onChange={(event) => { if (event.target.checked) setAskReset(true); else setReset(false); }} />
        <span>Bestätigungen zurücksetzen<small>{`Alle ${state.evidence_count ? `${state.evidence_count} ` : ""}Nachweise gelten wieder als ungeprüft – Sie gehen sie einzeln durch. Die Werte bleiben.`}</small></span>
      </label> : null}
      <div className="ra-inputs">
        <label className="field ra-hint">
          <span className="field-label">Hinweis an die KI (optional)</span>
          <input type="text" value={hint} maxLength={500} onChange={(event) => setHint(event.target.value)} placeholder="z. B. „Preisstaffel steht auf Seite 7“, „Reaktionszeit in Anlage 2“" />
        </label>
        <div className="field ra-pages">
          <label htmlFor="ra-pages" className="field-label">Seiten</label>
          <input id="ra-pages" type="text" inputMode="numeric" value={pagesText} onChange={(event) => setPagesText(event.target.value)} placeholder="alle" aria-invalid={pages === null} aria-describedby="ra-pages-hint" />
          <span id="ra-pages-hint" className="field-hint">{pages === null ? "Bitte wie „5–9, 12“ angeben (höchstens 20)." : "z. B. 5–9, 12"}</span>
        </div>
      </div>
      <details className="reextraction-advanced" open={state.reread_suggested}>
        <summary>Erweitert</summary>
        <label className="md-check"><input type="checkbox" checked={reread} onChange={(event) => setReread(event.target.checked)} /> Dokument neu lesen (Texterkennung)</label>
        {state.reread_suggested ? <p className="field-hint">Empfohlen: Das Dokument wurde bisher ohne Texterkennung gelesen.</p> : null}
        <label className="field">
          <span className="field-label">Modell</span>
          <select value={model} onChange={(event) => setModel(event.target.value)} disabled={models === null}>
            {models === null ? <option value="">Wird geladen…</option> : null}
            {models?.map((item) => <option key={item.model_id} value={item.model_id}>{item.label}{item.parameter_size ? ` · ${item.parameter_size}` : ""}{item.vision ? " · liest Bilder" : ""}{item.current ? " (aktuell)" : ""}</option>)}
          </select>
        </label>
        <p className="field-hint">Ein anderes installiertes Modell gilt nur für diese Analyse.</p>
      </details>
    </div>

    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    <div className="ra-start">
      <Button variant="primary" onClick={submit} loading={busy} loadingLabel="Wird gestartet…" disabled={invalid}>{SPARK}Analyse starten</Button>
      <span className="ra-est">{duration ? `Dauer ca. ${plural(duration, "Minute", "Minuten")}` : "Dauer einige Minuten"} · läuft im Hintergrund · Sie können weiterarbeiten</span>
    </div>

    <Dialog open={askReset} title="Bestätigungen zurücksetzen?" onClose={() => setAskReset(false)}
      description={`Nach der Analyse gelten ${state.evidence_count ? `alle ${state.evidence_count} Nachweise` : "alle Nachweise"} und alle geprüften Angaben wieder als ungeprüft. Die Werte selbst bleiben unverändert; Sie gehen sie anschließend einzeln durch.`}
      actions={<>
        <Button onClick={() => setAskReset(false)}>Abbrechen</Button>
        <Button variant="primary" onClick={() => { setReset(true); setAskReset(false); }}>Zurücksetzen</Button>
      </>} />
  </div>;
}

function RunningBox({ run, durationMinutes, busy, onCancel }: { run: ReextractionRun; durationMinutes: number | null; busy: boolean; onCancel: () => void }) {
  const { step, steps, label, found } = run.progress ?? {};
  const queued = run.status === "queued";
  const share = queued || !step || !steps ? 0.04 : Math.min(0.96, (step - 0.5) / steps);
  const elapsed = run.started_at ? (Date.now() - Date.parse(run.started_at)) / 60_000 : 0;
  const remaining = durationMinutes && !queued ? Math.max(1, Math.round(durationMinutes - elapsed)) : null;
  const detail = queued
    ? run.queue_position > 0 ? `wartet – ${plural(run.queue_position, "Analyse", "Analysen")} vor dieser` : "wartet auf die lokale KI"
    : step && steps ? `Schritt ${step} von ${steps} · ${label} · bisher ${plural(found ?? 0, "Angabe", "Angaben")} erkannt` : "wird vorbereitet";
  return <>
    <div className="ra-run" role="status">
      <div className="ra-run-line">
        {SPARK}
        <span><b>{`Analyse #${run.number} · ${run.mode_label}`}</b> – {detail}</span>
        <Button size="sm" onClick={onCancel} loading={busy}>Abbrechen</Button>
      </div>
      <span className="ra-run-bar" role="progressbar" aria-label="Fortschritt der Analyse" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)}><i style={{ width: `${Math.round(share * 100)}%` }} /></span>
      <div className="ra-run-meta">
        <span>{run.started_at ? `Gestartet ${timeDe(run.started_at)}${run.requested_by_name ? ` von ${run.requested_by_name}` : ""}` : `Angefordert${run.requested_by_name ? ` von ${run.requested_by_name}` : ""}`}</span>
        {remaining ? <span>{`noch ca. ${plural(remaining, "Minute", "Minuten")}`}</span> : null}
      </div>
    </div>
    <p className="ra-legend">Sie können den Tab verlassen. Wenn die Analyse fertig ist, erscheint hier und in „Offene Punkte“ die Zusammenfassung.</p>
  </>;
}

function ResultView({ run, rows, busy, canReview, safeCount, onConfirmSafe, onShowPage, onReview, onReviewEvidence, onAccept, onKeep, onRetry, onEditManually, onMarkInDocument }: {
  run: ReextractionRun;
  rows: Proposal[];
  busy: boolean;
  canReview: boolean;
  safeCount: number;
  onConfirmSafe: () => void;
  onShowPage?: (page: number) => void;
  onReview: (key: string) => void;
  onReviewEvidence?: () => void;
  onAccept: (row: Proposal) => void;
  onKeep: (row: Proposal) => void;
  onRetry: () => void;
  onEditManually?: (registerKey?: string) => void;
  onMarkInDocument?: () => void;
}) {
  const count = (kind: Proposal["kind"]) => rows.filter((row) => row.kind === kind).length;
  const listed = rows.filter((row) => row.kind !== "unchanged");
  const protectedCount = rows.filter((row) => row.protected).length;

  if (run.stale) {
    return <InlineAlert tone="warning" role="status" action={<Button size="sm" onClick={onRetry} loading={busy}>Verwerfen</Button>}>
      Die Vertragsdaten wurden inzwischen geändert. Dieses Ergebnis kann nicht mehr übernommen werden.
    </InlineAlert>;
  }
  return <div className="ra-result">
    <div className="ra-tiles">
      <div className="ra-tile ra-tile--same"><span className="ra-tile-n">{count("unchanged")}</span><span>unverändert – nichts zu tun</span></div>
      <div className="ra-tile ra-tile--new"><span className="ra-tile-n">{count("new")}</span><span>neu gefunden</span></div>
      <div className="ra-tile ra-tile--dev"><span className="ra-tile-n">{count("deviating")}</span><span>weichen vom gespeicherten Wert ab</span></div>
      <div className="ra-tile ra-tile--gone"><span className="ra-tile-n">{count("missing")}</span><span>nicht mehr gefunden</span></div>
    </div>
    {run.reset_confirmations ? <InlineAlert tone="info" action={onReviewEvidence ? <Button size="sm" onClick={onReviewEvidence}>Nachweise prüfen</Button> : null}>
      Alle Bestätigungen wurden zurückgesetzt. Gehen Sie die Nachweise einzeln durch.
    </InlineAlert> : null}
    {canReview && safeCount > 0 ? <div><Button size="sm" onClick={onConfirmSafe} disabled={busy}>Alle unveränderten bestätigen ({safeCount})</Button></div> : null}

    {listed.length === 0 ? <div className="reextraction-empty">
      <p><strong>Keine zusätzlichen Angaben gefunden.</strong> Die bisherigen Werte bleiben unverändert.</p>
      <div className="reextraction-actions">
        {onMarkInDocument ? <Button size="sm" onClick={onMarkInDocument}>Stelle im Dokument markieren</Button> : null}
        {onEditManually ? <Button size="sm" onClick={() => onEditManually()}>Selbst erfassen</Button> : null}
      </div>
    </div> : <>
      <div className="ra-sec"><span>Vorschläge</span><span className="ra-sec-line" /><span className="ra-sec-note">Übernehmen geht einzeln oder über „Vorschläge prüfen“ Feld für Feld</span></div>
      <table className="ra-table">
        <colgroup><col className="ra-col-field" /><col /><col /><col className="ra-col-conf" /><col className="ra-col-act" /></colgroup>
        <thead><tr><th scope="col">Feld</th><th scope="col">Bisher</th><th scope="col">Neu erkannt</th><th scope="col">Sicherheit</th><th scope="col"><span className="visually-hidden">Aktionen</span></th></tr></thead>
        <tbody>{listed.map((row) => {
          const diff = row.kind === "deviating" && row.current && row.proposed ? wordDiff(row.current, row.proposed) : null;
          const page = row.evidence.find((item) => item.page != null)?.page ?? null;
          const decided = row.decision !== "pending" ? DECISION[row.decision] : null;
          return <tr key={row.key}>
            <th scope="row"><span className="ra-field"><SectionChip section={analysisSection(row.section)} /><span>{row.label}</span></span></th>
            <td className="ra-value">{row.current ? (row.kind === "deviating" ? <span className="ra-old">{row.current}</span> : row.current) : <span className="cw-muted">–</span>}</td>
            <td className="ra-value">{row.kind === "missing" ? <span className="ra-gone">nicht mehr gefunden</span> : diff ? <Diff tokens={diff.b} /> : row.proposed}</td>
            <td>{row.confidence != null ? <Signal tone={confidenceTone(row.confidence)} size="sm">{`${Math.round(row.confidence * 100)} %`}</Signal> : <span className="cw-muted">–</span>}</td>
            <td className="ra-actions">{decided ? <Signal tone={decided.tone} size="sm">{decided.label}</Signal> : <>
              {row.kind === "missing"
                ? <><Button size="sm" className="btn-ghost" onClick={() => onKeep(row)} disabled={busy}>Behalten</Button><Button size="sm" onClick={() => onReview(row.key)}>Prüfen</Button></>
                : <>
                  {page != null && onShowPage ? <Button size="sm" className="btn-ghost" onClick={() => onShowPage(page)}>Quelle</Button> : null}
                  {row.kind === "new"
                    ? <Button size="sm" onClick={() => onAccept(row)} disabled={busy}>Übernehmen</Button>
                    : <Button size="sm" onClick={() => onReview(row.key)}>Vergleichen</Button>}
                </>}
            </>}</td>
          </tr>;
        })}</tbody>
      </table>
    </>}
    {protectedCount ? <p className="ra-legend">{plural(protectedCount, "von Hand gepflegte Angabe ist", "von Hand gepflegte Angaben sind")} geschützt und wurden nicht vorgeschlagen.</p> : null}
  </div>;
}

function historyText(item: AnalysisHistoryItem, current: boolean): ReactNode {
  if (item.mode === "initial") return `Erstanalyse${item.date ? ` · ${dateDe(item.date)}` : ""} · beim Import`;
  const date = item.date ? ` · ${dateDe(item.date)}` : "";
  if (item.mode === "rollback") return `Zurückgenommen${date} · ${plural(item.summary.rolled_back ?? 0, "Angabe", "Angaben")} auf Stand #${item.summary.target ?? "?"}`;
  const parts = [
    item.summary.new ? `${item.summary.new} neu` : null,
    item.summary.deviating ? `${item.summary.deviating} abweichend` : null,
    item.summary.missing ? `${item.summary.missing} fehlt` : null,
    item.accepted ? `${item.accepted} übernommen` : null,
  ].filter(Boolean);
  const status = item.status === "failed" ? "fehlgeschlagen" : item.status === "cancelled" ? "abgebrochen" : null;
  return <>{`${item.mode_label}${date}`}{parts.length ? ` · ${parts.join(", ")}` : ""}{status ? ` · ${status}` : ""}{current ? <> · <b>offen</b></> : null}</>;
}

function History({ items, currentId, canRollback, onRollback }: { items: AnalysisHistoryItem[]; currentId: string | null; canRollback: boolean; onRollback: (item: AnalysisHistoryItem) => void }) {
  return <section className="ra-history" aria-label="Verlauf der Analysen">
    <div className="ra-sec"><span>Verlauf</span><span className="ra-sec-line" /></div>
    <ul className="ra-hist">
      {items.map((item) => {
        const current = item.id !== null && item.id === currentId;
        return <li key={`${item.number}`} className="ra-hrow">
          <span className="ra-hno">#{item.number}</span>
          <span>{historyText(item, current)}</span>
          {current ? <Signal tone="ai" size="sm">aktuell</Signal>
            : item.can_rollback && canRollback ? <Button size="sm" className="btn-ghost" onClick={() => onRollback(item)}>{UNDO}Auf diesen Stand zurück</Button> : <span />}
        </li>;
      })}
    </ul>
  </section>;
}

function RollbackDialog({ contractId, orgSlug, item, onClose, onDone }: {
  contractId: string; orgSlug: string; item: AnalysisHistoryItem; onClose: () => void; onDone: (message: string) => void;
}) {
  const [entries, setEntries] = useState<RollbackEntry[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    getRollbackPreview(orgSlug, contractId, item.number)
      .then((result) => { if (alive) setEntries(result.entries); })
      .catch((err) => { if (alive) { setEntries([]); setError(message(err, "Die Vorschau konnte nicht geladen werden.")); } });
    return () => { alive = false; };
  }, [contractId, item.number, orgSlug]);
  const changes = (entries ?? []).filter((entry) => !entry.conflict);
  const skipped = (entries ?? []).filter((entry) => entry.conflict);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const result = await rollbackToAnalysis(orgSlug, contractId, item.number);
      onDone(result.message);
    } catch (err) {
      setError(message(err, "Der Stand konnte nicht wiederhergestellt werden."));
      setBusy(false);
    }
  }

  return <Dialog open title={`Auf Stand von Analyse #${item.number} zurück?`} onClose={onClose}
    description="Werte, die spätere Analysen übernommen haben, bekommen ihren vorherigen Wert samt Nachweis zurück. Nichts wird gelöscht; die Zurücknahme steht im Verlauf."
    actions={<>
      <Button onClick={onClose} disabled={busy}>Abbrechen</Button>
      <Button variant="primary" onClick={run} loading={busy} loadingLabel="Wird zurückgesetzt…" disabled={entries === null || changes.length === 0}>{changes.length ? `${plural(changes.length, "Angabe", "Angaben")} zurücknehmen` : "Nichts zurückzunehmen"}</Button>
    </>}>
    {entries === null ? <p className="cw-muted">Wird geladen…</p> : <>
      {changes.length ? <ul className="ra-rollback">
        {changes.map((entry) => <li key={`${entry.number}-${entry.key}`}><strong>{entry.label}</strong>: {entry.current ?? "–"} → {entry.restored ?? "leer"} <span className="cw-muted">(aus Analyse #{entry.number})</span></li>)}
      </ul> : <p className="cw-muted">Es gibt nichts zurückzunehmen.</p>}
      {skipped.length ? <InlineAlert tone="warning">{`Bleiben unverändert, weil sie später geändert wurden: ${skipped.map((entry) => entry.label).join(", ")}.`}</InlineAlert> : null}
    </>}
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
  </Dialog>;
}
