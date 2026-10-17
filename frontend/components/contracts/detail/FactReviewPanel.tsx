"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Signal, { SignalIcon, type SignalTone } from "@/components/ui/Signal";
import { ApiError, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { useToast } from "@/components/ui/Toast";
import { ROLE_LABELS } from "@/lib/auth-types";
import type { ContractDetailResponse, EvidenceRef, FactReviewStateDto, FactReviewDto } from "@/lib/contract-detail-types";
import AiOrigin from "@/components/ui/AiOrigin";
import { visibleReviewFacts } from "@/lib/review-facts";
import ValueOriginBadge, { type ValueOriginKind } from "./ValueOriginBadge";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload: () => void;
  onNavigate?: (ev: EvidenceRef) => void;
  /** Zu „Widerspruch klären“ (Übersicht). */
  onOpenConflict?: () => void;
  /** Diese Angabe zeigen (Klick auf eine KI-Plakette); `n` ändert sich bei jedem Klick. */
  focusFact?: { key: string; n: number } | null;
}

type ViewMode = "focus" | "table";

function valueText(v: unknown): string {
  if (v == null || v === "") return "–";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  const text = JSON.stringify(v);
  if (!text) return "–";
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

function hasValue(v: unknown): boolean {
  return !(v == null || v === "");
}

function originKind(state: FactReviewStateDto, target: "original" | "effective"): ValueOriginKind {
  const value = target === "original" ? state.original_value : state.effective_value;
  if (!hasValue(value)) return "missing";
  if (target === "effective" && state.state === "corrected") return "corrected";
  if (target === "effective" && state.state === "confirmed") return "reviewed";
  if (state.evidence_count > 0) return "extracted";
  return "system";
}

function stampTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(d);
}

const ACTION_LABEL: Record<string, string> = {
  confirmed: "Bestätigt",
  corrected: "Korrigiert",
  voided: "Verworfen",
  reopened: "Erneut geöffnet",
};
const RESULT_VERB: Record<string, string> = {
  confirmed: "Bestätigt",
  corrected: "Korrigiert",
  voided: "Verworfen",
  auto_accepted: "Automatisch übernommen",
};

function identityHint(identity: string | null) {
  if (identity === "authenticated_account") return "authentifiziert";
  if (!identity || identity === "manual_unverified") return "älterer manueller Eintrag";
  return identity;
}

// Ruhe & Signal: bestätigt/korrigiert = done, verworfen = neutral, automatisch übernommen = info
// (kein menschliches Ergebnis, daher nicht grün), sonst ungeprüfter KI-Wert = ai.
function stateSignal(state: string): SignalTone {
  if (state === "confirmed" || state === "corrected") return "done";
  if (state === "voided") return "neutral";
  return state === "auto_accepted" ? "info" : "ai";
}

/** Sicherheit der KI zu ihrem Vorschlag in Prozent (unter 70 % in Warnfarbe); ohne Angabe nichts. */
const RULE_TITLE = "Von festen Regeln wörtlich im Text gefunden – kein KI-Vorschlag, daher ohne KI-Sicherheit";

/** Hinweis in der Liste: KI-Sicherheit oder „Regel“ (wörtlich gefunden, ohne Prozent). */
function originNote(s: FactReviewStateDto): string {
  if (s.ai_confidence != null) return ` · KI ${Math.round(s.ai_confidence * 100)} %`;
  return s.found_by_rule ? " · Regel" : "";
}

export function ConfidenceBadge({ value, byRule }: { value: number | null | undefined; byRule?: boolean }) {
  if (value == null) return byRule ? <Signal tone="neutral" size="sm" title={RULE_TITLE}>Regel · wörtlich im Text</Signal> : null;
  const percent = Math.round(value * 100);
  return <Signal tone={percent < 70 ? "warning" : "neutral"} size="sm" title="Wie sicher die KI bei diesem Vorschlag ist (bester Beleg)">KI-Sicherheit {percent} %</Signal>;
}

function StateSignal({ state, label, present, factKey }: { state: string; label: string; present: boolean; factKey: string }) {
  // KI-Werte tragen die einheitliche Plakette; Korrigiert/Verworfen und fehlende Angaben bleiben Signale.
  if (present && state === "confirmed") return <AiOrigin state="confirmed" size="md" factKey={factKey} />;
  if (present && state === "auto_accepted") return <AiOrigin state="auto" size="md" factKey={factKey} />;
  if (present && stateSignal(state) === "ai") return <AiOrigin state="unreviewed" size="md" factKey={factKey} />;
  return <Signal tone={stateSignal(state)}>{RESULT_VERB[state] ?? (stateSignal(state) === "ai" ? "KI-Vorschlag" : label)}</Signal>;
}

export default function FactReviewPanel({ data, orgSlug, onReload, onNavigate, onOpenConflict, focusFact }: Props) {
  const toast = useToast();
  const panelRef = useRef<HTMLElement | null>(null);
  const { account, role } = useAuth();
  const canReview = role === "admin" || role === "contract_manager" || role === "reviewer";
  const [corrected, setCorrected] = useState<Record<string, string>>({});
  const [correctionNotes, setCorrectionNotes] = useState<Record<string, string>>({});
  const [activeFact, setActiveFact] = useState<string | null>(null);
  const [editFact, setEditFact] = useState<string | null>(null);
  const [historyFact, setHistoryFact] = useState<string | null>(null);
  const [ack, setAck] = useState(false);
  const [completionNote, setCompletionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [view, setView] = useState<ViewMode>("focus");
  // Liste links: nur offene oder alle Angaben; folgt der ausgewählten Angabe.
  const [navFilter, setNavFilter] = useState<"open" | "all">("all");
  const navRef = useRef<HTMLElement | null>(null);
  const cr = data.contract_review;

  const states = useMemo(
    () => visibleReviewFacts({ fact_review_states: data.fact_review_states }),
    [data.fact_review_states]
  );

  // Klick auf eine KI-Plakette: genau diese Angabe zeigen (Einzelansicht, alle Angaben in der Liste).
  useEffect(() => {
    if (!focusFact) return;
    setActiveFact(focusFact.key);
    setView("focus");
    setNavFilter("all");
    setEditFact(null);
    setHistoryFact(null);
    panelRef.current?.scrollIntoView?.({ block: "start" });
  }, [focusFact]);
  const openStates = useMemo(() => states.filter((s) => s.present && !["confirmed", "corrected", "voided", "auto_accepted"].includes(s.state)), [states]);
  const navStates = navFilter === "open" ? openStates : states;
  const selected = states.find((s) => s.fact_key === (activeFact ?? states[0]?.fact_key)) ?? states[0] ?? null;
  const selectedIndex = selected ? states.findIndex((s) => s.fact_key === selected.fact_key) : -1;
  const evidenceById = useMemo(() => {
    const m = new Map<string, EvidenceRef>();
    for (const e of data.evidence) if (e.evidence_id) m.set(e.evidence_id, e);
    return m;
  }, [data.evidence]);
  const historyByFact = (fk: string): FactReviewDto[] => (data.fact_reviews ?? []).filter((r) => r.fact_key === fk);
  const hasUnsavedCorrection = Boolean(editFact && ((corrected[editFact] ?? "").trim() || (correctionNotes[editFact] ?? "").trim()));

  useEffect(() => {
    if (!hasUnsavedCorrection) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const scopeChange = (event: Event) => {
      if (!window.confirm("Es gibt eine noch nicht gespeicherte Korrektur. Arbeitsbereich trotzdem wechseln?")) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("medflux:scope-change", scopeChange);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("medflux:scope-change", scopeChange);
    };
  }, [hasUnsavedCorrection]);

  useEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>("button.active");
    if (active && typeof active.scrollIntoView === "function") active.scrollIntoView({ block: "nearest" });
  }, [selected?.fact_key, navFilter]);

  function navKey(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const index = navStates.findIndex((s) => s.fact_key === selected?.fact_key);
    const next = navStates[index + (event.key === "ArrowDown" ? 1 : -1)];
    if (!next) return;
    event.preventDefault();
    selectFact(next.fact_key);
    window.setTimeout(() => navRef.current?.querySelector<HTMLElement>("button.active")?.focus(), 0);
  }

  async function postFact(body: Record<string, unknown>): Promise<boolean> {
    if (!canReview) {
      setMsg({ ok: false, text: "Für diese Aktion fehlt die Berechtigung." });
      return false;
    }
    setBusy(true);
    setMsg(null);
    try {
      // Versionsstand mitsenden: hat jemand die Angabe inzwischen geprüft, antwortet der Server mit 409.
      const seen = states.find((item) => item.fact_key === body.fact_key);
      await apiPost(`/api/contracts/${encodeURIComponent(data.contract_id)}/fact-reviews?organization_slug=${encodeURIComponent(orgSlug)}`, { ...body, expected_reviewed_at: seen?.reviewed_at ?? null });
      setMsg({ ok: true, text: "Prüf-Aktion gespeichert." });
      toast("Prüf-Aktion gespeichert.", "success");
      onReload();
      window.setTimeout(() => panelRef.current?.focus({ preventScroll: true }), 30);
      return true;
    } catch (err) {
      const conflict = err instanceof ApiError && err.status === 409;
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Prüf-Aktion konnte nicht gespeichert werden." });
      toast(conflict ? "Die Angabe wurde inzwischen geändert – Stand neu geladen." : "Prüf-Aktion konnte nicht gespeichert werden.", "error");
      if (conflict) onReload();
      return false;
    } finally {
      setBusy(false);
    }
  }

  function nextFact() {
    // Mit Filter „Offen“ springt „Weiter“ zur nächsten offenen Angabe.
    const list = navFilter === "open" ? navStates : states;
    const index = list.findIndex((s) => s.fact_key === selected?.fact_key);
    const next = index >= 0 ? list[index + 1] : list.find((s) => states.indexOf(s) > selectedIndex);
    if (next) setActiveFact(next.fact_key);
  }
  function previousFact() {
    if (selectedIndex > 0) setActiveFact(states[selectedIndex - 1].fact_key);
  }
  async function confirmFact(fk: string) {
    const ok = await postFact({ fact_key: fk, action: "confirmed" });
    if (ok) nextFact();
  }
  async function correctFact(fk: string) {
    const value = corrected[fk];
    const note = correctionNotes[fk];
    if (!value || !String(value).trim()) {
      setMsg({ ok: false, text: "Bitte einen korrigierten Wert angeben." });
      return;
    }
    if (!note || !String(note).trim()) {
      setMsg({ ok: false, text: "Bitte begründen Sie die Korrektur." });
      return;
    }
    const ok = await postFact({
      fact_key: fk,
      action: "corrected",
      corrected_value: String(value).trim(),
      note: String(note).trim(),
    });
    if (ok) {
      setCorrected((current) => ({ ...current, [fk]: "" }));
      setCorrectionNotes((current) => ({ ...current, [fk]: "" }));
      setEditFact(null);
      nextFact();
    }
  }
  function reopenFact(fk: string) {
    void postFact({ fact_key: fk, action: "reopened" });
  }

  async function postLifecycle(path: "start" | "complete") {
    if (!canReview) {
      setMsg({ ok: false, text: "Für diese Aktion fehlt die Berechtigung." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await apiPost(`/api/contracts/${encodeURIComponent(data.contract_id)}/review/${path}?organization_slug=${encodeURIComponent(orgSlug)}`, {
        note: path === "complete" ? completionNote : null,
        acknowledge_unreviewed: path === "complete" ? ack : false,
      });
      toast(path === "complete" ? "Review abgeschlossen." : "Review erneut geöffnet.", "success");
      onReload();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Review-Aktion konnte nicht gespeichert werden." });
      toast("Review-Aktion konnte nicht gespeichert werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  function selectFact(fk: string) {
    if (hasUnsavedCorrection && editFact !== fk && !window.confirm("Nicht gespeicherte Korrektur verwerfen?")) return;
    setActiveFact(fk);
    setEditFact(null);
    setHistoryFact(null);
    setView("focus");
  }

  function EvidenceButtons({ s }: { s: FactReviewStateDto }) {
    if (!s.needs_evidence && s.evidence_count === 0) return null;
    if (s.evidence_count === 0) return <span className="fact-review small">Kein Quellen-Beleg verlinkt – bitte prüfen</span>;
    return (
      <div className="fr-evidence-links">
        {s.linked_evidence_refs.map((eid) => {
          const ev = evidenceById.get(eid);
          if (!ev) return null;
          return <button key={eid} type="button" className="fact-cite-link" onClick={() => onNavigate?.(ev)}>{ev.page != null ? `Seite ${ev.page}` : "Quelle"}{ev.requires_review ? " · zu prüfen" : ""}</button>;
        })}
      </div>
    );
  }

  function History({ s }: { s: FactReviewStateDto }) {
    const rows = historyByFact(s.fact_key);
    return (
      <ul className="audit-list fr-history">
        {rows.length === 0 && <li className="muted small">Noch keine Einträge.</li>}
        {rows.map((r) => (
          <li key={r.id}>
            <span className={`audit-action audit-${r.action}`}>{ACTION_LABEL[r.action] ?? r.action_label_de ?? r.action}</span>
            <span className="audit-key">{r.fact_label_de || r.fact_key}</span>
            {r.action === "confirmed" && <span className="audit-value">Wert übernommen</span>}
            {r.action === "corrected" && <><span className="audit-old">{valueText(r.previous_effective_value)} → </span><span className="audit-value">{valueText(r.new_effective_value)}</span></>}
            {r.note && <span className="muted"> – {r.note}</span>}
            <span className="audit-date">{stampTime(r.created_at)}</span>
            <span className="audit-ref">{r.reviewer_display_name ?? "–"} · {identityHint(r.reviewer_identity_type)}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (!cr) return <section id="fact-review-panel" ref={panelRef} tabIndex={-1} className="detail-card"><h2>Faktprüfung</h2><p className="muted">Für diesen Datensatz liegt noch keine Prüf-Übersicht vor.</p></section>;

  return (
    <section id="fact-review-panel" ref={panelRef} tabIndex={-1} className="detail-card fr-workspace" aria-label="Faktprüfung">
      <div className="fr-title-row">
        <div><h2>Faktprüfung</h2><p className="muted small">Prüfen Sie die automatisch erkannten Vertragsangaben und bestätigen oder korrigieren Sie die Werte. Alle Änderungen werden mit dem angemeldeten Benutzer protokolliert.</p></div>
        <div className="fr-view-toggle"><button className={view === "focus" ? "active" : ""} onClick={() => setView("focus")}>Einzelprüfung</button><button className={view === "table" ? "active" : ""} onClick={() => setView("table")}>Alle Angaben</button></div>
      </div>
      {msg && <p className={msg.ok ? "form-ok" : "form-error"} role="status">{msg.text}</p>}
      <div className="fr-review-summary">
        <div className="fr-review-meta"><strong>Vertragsreview</strong><span>{cr.reviewed_count} von {cr.relevant_count} Angaben geprüft · {cr.unresolved_count} ungeprüft</span><span className={`fact-review${cr.status === "reviewed" ? " ok" : ""}`}>{cr.critical_unreviewed_count > 0 ? `${cr.critical_unreviewed_count} kritisch ungeprüft · ` : ""}{cr.status_label_de}</span></div>
        <div className="fr-current-reviewer"><span>Prüfung durch</span><strong>{account?.display_name ?? "Angemeldeter Benutzer"}</strong><small>{role ? ROLE_LABELS[role] : ""}</small></div>
        {cr.critical_unreviewed_count > 0 ? <p className="form-error" role="alert">Review-Abschluss gesperrt: kritische Angaben müssen zuerst einzeln geprüft werden.</p> : null}\n        {canReview ? <><label className="fr-ack"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> Verbleibende nicht-kritische ungeprüfte Angaben akzeptieren</label><div className="fr-complete"><input type="text" placeholder="Abschluss-Notiz (optional)" value={completionNote} onChange={(e) => setCompletionNote(e.target.value)} /><button type="button" className="btn btn-sm" onClick={() => void postLifecycle("complete")} disabled={busy || cr.critical_unreviewed_count > 0 || (!ack && cr.unresolved_count > 0)}>Review abschließen</button><button type="button" className="btn-link" onClick={() => void postLifecycle("start")} disabled={busy}>Review erneut öffnen</button></div></> : <p className="fr-readonly-note">Nur-Lese-Zugriff: Prüfschritte können nicht verändert werden.</p>}
      </div>

      {states.length === 0 ? <p className="muted">Keine Angaben vorhanden.</p> : view === "table" ? (
        <div className="fr-table-wrap"><table className="fr-table"><thead><tr><th>Angabe</th><th>Original</th><th>Wirksam</th><th>Quelle</th><th>Status</th>{canReview ? <th>Aktion</th> : null}</tr></thead><tbody>{states.map((s) => <tr key={s.fact_key}><td><button className="fr-table-name" onClick={() => selectFact(s.fact_key)}>{s.label_de}</button>{s.is_critical && <small>kritisch</small>}</td><td><span className="fr-value-with-origin">{valueText(s.original_value)}<ValueOriginBadge kind={originKind(s, "original")} /><ConfidenceBadge value={s.ai_confidence} byRule={s.found_by_rule} /></span></td><td><span className="fr-value-with-origin"><strong>{valueText(s.effective_value)}</strong><ValueOriginBadge kind={originKind(s, "effective")} /></span></td><td><EvidenceButtons s={s} /></td><td><StateSignal state={s.state} label={s.state_label_de} present={s.present} factKey={s.fact_key} />{s.reopen_note ? <small className="fr-reopen-note">{s.reopen_note}</small> : null}</td>{canReview ? <td><div className="fr-table-actions"><button title="Bestätigen" aria-label={`${s.label_de} bestätigen`} onClick={() => void confirmFact(s.fact_key)} disabled={busy}><span aria-hidden="true">✓</span></button><button title="Korrigieren" aria-label={`${s.label_de} korrigieren`} onClick={() => { setActiveFact(s.fact_key); setEditFact(s.fact_key); setView("focus"); }} disabled={busy}><span aria-hidden="true">✎</span></button><button title="Historie" aria-label={`Historie von ${s.label_de}`} onClick={() => { setActiveFact(s.fact_key); setHistoryFact(s.fact_key); setView("focus"); }}><span aria-hidden="true">◷</span></button></div></td> : null}</tr>)}</tbody></table></div>
      ) : (
        <div className="fr-focus-layout">
          <nav ref={navRef} className="fr-fact-nav" aria-label="Materiale Angaben" onKeyDown={navKey}><div className="fr-nav-head"><strong>Angaben</strong><span className="fr-nav-filter" role="group" aria-label="Angaben filtern"><button type="button" aria-pressed={navFilter === "open"} onClick={() => setNavFilter("open")}>Offen {openStates.length}</button><button type="button" aria-pressed={navFilter === "all"} onClick={() => setNavFilter("all")}>Alle {states.length}</button></span></div>{data.evidence.length ? <p className="fr-nav-note">{data.evidence.length} Nachweise in {states.length} Angaben – mehrere Belege zum selben Wert stehen bei einer Angabe.</p> : null}{navFilter === "open" && !openStates.length ? <p className="fr-nav-note">Keine offenen Angaben – alles geprüft.</p> : null}{navStates.map((s) => <button key={s.fact_key} type="button" className={selected?.fact_key === s.fact_key ? "active" : ""} onClick={() => selectFact(s.fact_key)}><span className="fr-nav-index">{states.indexOf(s) + 1}</span><span><strong>{s.label_de}</strong><small>{s.is_critical ? "Kritisch" : s.is_evidence_item ? "Weiterer Nachweis" : "Standard"}{originNote(s)}</small></span><SignalIcon tone={stateSignal(s.state)} className={`fr-status-icon fr-status-icon--${stateSignal(s.state)}`} /><span className="sr-only">{RESULT_VERB[s.state] ?? "KI-Vorschlag"}</span></button>)}</nav>
          {selected && <article className="fr-fact-detail">
            <div className="fr-detail-head"><div><span className="fr-step">Angabe {selectedIndex + 1} von {states.length}</span><h3>{selected.label_de}</h3>{selected.is_critical && <span className="fr-critical-label">Kritische Angabe</span>}</div><StateSignal state={selected.state} label={selected.state_label_de} present={selected.present} factKey={selected.fact_key} /></div>{selected.reopen_note ? <p className="fr-reopen-note" role="status">{selected.reopen_note}</p> : null}
            {(data.warnings ?? []).filter((warning) => warning.requires_review && warning.conflict?.fact_key === selected.fact_key).map((warning) => <p key={warning.conflict!.title_de} className="fr-conflict-note" role="status"><Signal tone="warning" size="sm">Widerspruch</Signal><span>{warning.conflict!.explanation_de}</span>{onOpenConflict ? <button type="button" className="rg-link" onClick={onOpenConflict}>Widerspruch klären</button> : null}</p>)}
            <div className="fr-value-grid">
              <div><label>Original aus Dokument <ValueOriginBadge kind={originKind(selected, "original")} factKey={selected.fact_key} /> <ConfidenceBadge value={selected.ai_confidence} byRule={selected.found_by_rule} /></label><div className="fr-value-box">{valueText(selected.original_value)}</div></div>
              <div><label>Wirksam im System <ValueOriginBadge kind={originKind(selected, "effective")} factKey={selected.fact_key} /></label><div className="fr-value-box effective">{valueText(selected.effective_value)}</div></div>
            </div>
            <div className="fr-source-block"><strong>Quellen-Beleg</strong><EvidenceButtons s={selected} /></div>
            {selected.reviewed_at && <p className="fr-reviewed"><strong>{RESULT_VERB[selected.state] ?? "Geprüft"}</strong> · {selected.reviewer_display_name ?? "–"} · {stampTime(selected.reviewed_at)}</p>}
            {canReview ? <div className="fr-detail-actions"><button type="button" className="fr-confirm" onClick={() => void confirmFact(selected.fact_key)} disabled={busy}><SignalIcon tone="done" /> Bestätigen</button><button type="button" className="btn btn-sm" onClick={() => setEditFact(editFact === selected.fact_key ? null : selected.fact_key)} disabled={busy}>✎ Korrigieren</button>{selected.state !== "unreviewed" && selected.state !== "auto_accepted" && <button type="button" className="btn-link" onClick={() => reopenFact(selected.fact_key)} disabled={busy}>Erneut öffnen</button>}<button type="button" className="btn-link" onClick={() => setHistoryFact(historyFact === selected.fact_key ? null : selected.fact_key)}>◷ Historie</button></div> : <div className="fr-detail-actions"><button type="button" className="btn-link" onClick={() => setHistoryFact(historyFact === selected.fact_key ? null : selected.fact_key)}>◷ Historie</button></div>}
            {editFact === selected.fact_key && canReview ? (
              <div className="fr-edit-row fr-edit-stack">
                <label>Korrigierter Wert<input type="text" autoFocus placeholder="Korrigierter Wert" value={corrected[selected.fact_key] ?? ""} onChange={(e) => setCorrected((prev) => ({ ...prev, [selected.fact_key]: e.target.value }))} /></label>
                <label>Begründung der Korrektur<input type="text" placeholder="Warum wird der Wert geändert?" value={correctionNotes[selected.fact_key] ?? ""} onChange={(e) => setCorrectionNotes((prev) => ({ ...prev, [selected.fact_key]: e.target.value }))} /></label>
                <div className="fr-edit-actions"><button className="btn btn-sm" onClick={() => void correctFact(selected.fact_key)} disabled={busy}>Korrektur speichern</button><button type="button" className="btn-link" onClick={() => { setCorrected((current) => ({ ...current, [selected.fact_key]: "" })); setCorrectionNotes((current) => ({ ...current, [selected.fact_key]: "" })); setEditFact(null); }} disabled={busy}>Abbrechen</button></div>
              </div>
            ) : null}
            {historyFact === selected.fact_key && <History s={selected} />}
            <div className="fr-pager"><button type="button" onClick={previousFact} disabled={selectedIndex <= 0}>← Vorherige Angabe</button><span>{selectedIndex + 1} / {states.length}</span><button type="button" onClick={nextFact} disabled={selectedIndex >= states.length - 1}>Nächste Angabe →</button></div>
          </article>}
        </div>
      )}
    </section>
  );
}