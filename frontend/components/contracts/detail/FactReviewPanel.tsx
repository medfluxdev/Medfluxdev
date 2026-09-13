"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import type {
  ContractDetailResponse,
  EvidenceRef,
  FactReviewStateDto,
  FactReviewDto,
} from "@/lib/contract-detail-types";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload: () => void;
  onNavigate?: (ev: EvidenceRef) => void;
}

type AuthIdentity = {
  user_id: string;
  organization_id: string;
  organization_slug: string;
  username: string;
  display_name: string;
  role: string;
};

function valueText(v: unknown): string {
  if (v == null || v === "") return "–";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  const text = JSON.stringify(v);
  if (!text) return "–";
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

function stampAttr(iso: string): string {
  return iso.slice(0, 10);
}

function stampTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return stampAttr(iso);
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(d);
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
};

function reviewResultLabel(state: string): string {
  return RESULT_VERB[state] ?? "Geprüft";
}

const STATE_TONE: Record<string, string> = {
  unreviewed: "",
  needs_review: "",
  confirmed: " ok",
  corrected: " ok",
  voided: "",
};

function identityHint(identity: string | null): string {
  if (!identity || identity === "manual_unverified") return "manuell, unverifiziert";
  if (identity === "authenticated_local") return "authentifiziert";
  return identity;
}

export default function FactReviewPanel({ data, orgSlug, onReload, onNavigate }: Props) {
  const toast = useToast();
  const panelRef = useRef<HTMLElement | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [authenticatedReviewer, setAuthenticatedReviewer] = useState<AuthIdentity | null>(null);
  const [note, setNote] = useState("");
  const [corrected, setCorrected] = useState<Record<string, string>>({});
  const [openFact, setOpenFact] = useState<string | null>(null);
  const [historyFact, setHistoryFact] = useState<string | null>(null);
  const [ack, setAck] = useState(false);
  const [completionNote, setCompletionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let mounted = true;
    apiGet<AuthIdentity>("/api/auth/me")
      .then((identity) => {
        if (mounted) setAuthenticatedReviewer(identity);
      })
      .catch(() => {
        if (mounted) setAuthenticatedReviewer(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const effectiveReviewer = authenticatedReviewer?.display_name ?? reviewer.trim();
  const cr = data.contract_review;

  const evidenceById = new Map<string, EvidenceRef>();
  for (const e of data.evidence) {
    if (e.evidence_id) evidenceById.set(e.evidence_id, e);
  }

  async function postFact(body: Record<string, unknown>): Promise<boolean> {
    if (!effectiveReviewer) {
      setMsg({
        ok: false,
        text: "Bitte zuerst Prüfer*in angeben. Im Anmeldemodus wird die serverseitig authentifizierte Identität automatisch verwendet.",
      });
      return false;
    }
    setBusy(true);
    setMsg(null);
    try {
      await apiPost(
        `/api/contracts/${encodeURIComponent(
          data.contract_id
        )}/fact-reviews?organization_slug=${encodeURIComponent(orgSlug)}`,
        { ...body, reviewer_display_name: effectiveReviewer }
      );
      setMsg({ ok: true, text: "Prüf-Aktion gespeichert." });
      toast("Prüf-Aktion gespeichert.", "success");
      onReload();
      window.setTimeout(() => panelRef.current?.focus({ preventScroll: true }), 30);
      return true;
    } catch {
      setMsg({ ok: false, text: "Prüf-Aktion konnte nicht gespeichert werden." });
      toast("Prüf-Aktion konnte nicht gespeichert werden.", "error");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function confirmFact(fk: string) {
    void postFact({
      fact_key: fk,
      action: "confirmed",
      note: note || null,
    });
  }

  async function correctFact(fk: string) {
    const value = corrected[fk];
    if (!value || String(value).trim() === "") {
      setMsg({ ok: false, text: "Bitte einen korrigierten Wert angeben." });
      return;
    }
    const ok = await postFact({
      fact_key: fk,
      action: "corrected",
      corrected_value: String(value).trim(),
      note: note || null,
    });
    if (ok) setOpenFact(null);
  }

  function reopenFact(fk: string) {
    void postFact({
      fact_key: fk,
      action: "reopened",
      note: note || null,
    });
  }

  async function postLifecycle(path: "start" | "complete"): Promise<boolean> {
    if (!effectiveReviewer) {
      setMsg({
        ok: false,
        text: "Bitte zuerst Prüfer*in angeben. Im Anmeldemodus wird die serverseitig authentifizierte Identität automatisch verwendet.",
      });
      return false;
    }
    setBusy(true);
    setMsg(null);
    try {
      await apiPost(
        `/api/contracts/${encodeURIComponent(
          data.contract_id
        )}/review/${path}?organization_slug=${encodeURIComponent(orgSlug)}`,
        {
          reviewer_display_name: effectiveReviewer,
          note: path === "complete" ? completionNote : note,
          acknowledge_unreviewed: path === "complete" ? ack : false,
        }
      );
      setMsg({
        ok: true,
        text: path === "complete" ? "Review abgeschlossen." : "Review erneut geöffnet.",
      });
      toast(
        path === "complete" ? "Review abgeschlossen." : "Review erneut geöffnet.",
        "success"
      );
      onReload();
      window.setTimeout(() => panelRef.current?.focus({ preventScroll: true }), 30);
      return true;
    } catch {
      setMsg({
        ok: false,
        text:
          path === "complete"
            ? "Abschluss nicht möglich – bitte ungeprüfte Angaben quittieren."
            : "Review konnte nicht geöffnet werden.",
      });
      toast("Review-Aktion konnte nicht gespeichert werden.", "error");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const states = (data.fact_review_states ?? []).filter(
    (s) => s.present || s.state !== "unreviewed" || s.has_history
  );
  const historyByFact = (fk: string): FactReviewDto[] =>
    (data.fact_reviews ?? []).filter((r) => r.fact_key === fk);

  if (!cr) {
    return (
      <section
        id="fact-review-panel"
        ref={panelRef}
        tabIndex={-1}
        className="detail-card"
        aria-label="Faktprüfung"
      >
        <h2>Faktprüfung</h2>
        <p className="muted">
          Für diesen Datensatz liegt noch keine Prüf-Übersicht vor.
        </p>
      </section>
    );
  }

  return (
    <section
      id="fact-review-panel"
      ref={panelRef}
      tabIndex={-1}
      className="detail-card"
      aria-label="Faktprüfung"
    >
      <h2>Faktprüfung</h2>
      <p className="muted small">
        Faktgenaue menschliche Prüfung der materialen Vertragsangaben.
        „Bestätigen“ ändert den Wert nie; „Korrigieren“ setzt einen neuen
        wirksamen Wert. Beides ist append-only im Audit sichtbar.
      </p>

      {msg && (
        <p className={msg.ok ? "form-ok" : "form-error"} role="status">
          {msg.text}
        </p>
      )}

      <div className="override-group">
        {authenticatedReviewer ? (
          <p className="muted small">
            Prüfer*in: <strong>{authenticatedReviewer.display_name}</strong> · authentifiziert
            · die gespeicherte Identität wird serverseitig aus der Anmeldung gebunden.
          </p>
        ) : (
          <>
            <label className="reviewer-label" htmlFor="fact-reviewer">
              Prüfer*in (Entwicklungsmodus ohne Anmeldung: manuell/unverifiziert)
            </label>
            <input
              id="fact-reviewer"
              type="text"
              placeholder="z. B. Klinik-Werksteam"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              aria-label="Name der prüfenden Person"
            />
          </>
        )}
      </div>

      <div className="override-group">
        <h3>Vertragsreview</h3>
        <p className="muted small">
          {cr.reviewed_count} von {cr.relevant_count} relevanten Angaben geprüft
          {cr.unresolved_count > 0 ? ` · ${cr.unresolved_count} ungeprüft` : ""}
          {cr.critical_unreviewed_count > 0 && (
            <span className="fact-review">
              {" "}· {cr.critical_unreviewed_count} kritisch ungeprüft
            </span>
          )}
          {" · "}
          <span className={`fact-review${cr.status === "reviewed" ? " ok" : ""}`}>
            {cr.status_label_de}
          </span>
        </p>
        {cr.status === "changed_after_review" && (
          <p className="muted small">
            Materiale Änderung nach Abschluss am{" "}
            {cr.changed_noted_at ? stampTime(cr.changed_noted_at) : "–"} – bitte
            erneut prüfen oder abschließen.
          </p>
        )}
        {cr.reviewer_display_name && (
          <p className="muted small">
            Abgeschlossen durch {cr.reviewer_display_name} (
            {identityHint(cr.reviewer_identity_type)})
            {cr.reviewed_at ? ` · ${stampTime(cr.reviewed_at)}` : ""}
          </p>
        )}
        {cr.completion_note && (
          <p className="muted small">Notiz: {cr.completion_note}</p>
        )}

        <div className="override-row">
          <label className="reviewer-label" htmlFor="fact-complete-ack">
            <input
              id="fact-complete-ack"
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
            />{" "}
            Verbleibende ungeprüfte Angaben akzeptieren
          </label>
        </div>
        <div className="override-row">
          <input
            type="text"
            placeholder="Abschluss-Notiz (optional)"
            value={completionNote}
            onChange={(e) => setCompletionNote(e.target.value)}
            aria-label="Notiz zum Review-Abschluss"
          />
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => void postLifecycle("complete")}
            disabled={busy || (!ack && cr.unresolved_count > 0)}
            title={
              !ack && cr.unresolved_count > 0
                ? "Bitte die ungeprüften Angaben quittieren"
                : "Review abschließen"
            }
          >
            Review abschließen
          </button>
          <button
            type="button"
            className="btn-link"
            onClick={() => void postLifecycle("start")}
            disabled={busy}
          >
            Review erneut öffnen
          </button>
        </div>
      </div>

      <div className="override-group">
        <h3>Materiale Angaben</h3>
        {states.length === 0 && <p className="muted">Keine Angaben vorhanden.</p>}
        <ul className="fact-states">
          {states.map((s: FactReviewStateDto) => {
            const fk = s.fact_key;
            const open = openFact === fk;
            const showHistory = historyFact === fk;
            return (
              <li key={fk} className="fact-state">
                <div className="fact-state-head">
                  <span className="fact-review-name">
                    {s.is_critical && (
                      <span className="fact-critical" title="Material-relevante Angabe">
                        kritisch{" "}
                      </span>
                    )}
                    {s.label_de}
                  </span>
                  <span className={`fact-review${STATE_TONE[s.state] ?? ""}`}>
                    {RESULT_VERB[s.state] ?? s.state_label_de}
                  </span>
                </div>
                <div className="fact-state-values">
                  <span className="muted">Original: {valueText(s.original_value)}</span>
                  <span className="muted">
                    Wirksam: <strong>{valueText(s.effective_value)}</strong>
                  </span>
                </div>
                {(s.needs_evidence || s.evidence_count > 0) && (
                  <div className="fact-evidence">
                    {s.evidence_count === 0 ? (
                      <span className="fact-review small">
                        Kein Quellen-Beleg verlinkt – bitte prüfen
                      </span>
                    ) : (
                      <>
                        <span className="muted small">
                          Quellen-Beleg{s.evidence_count > 1 ? `e (${s.evidence_count})` : ""}:{" "}
                        </span>
                        {s.linked_evidence_refs.map((eid) => {
                          const ev = evidenceById.get(eid);
                          if (!ev) return null;
                          return (
                            <button
                              key={eid}
                              type="button"
                              className="fact-cite-link"
                              onClick={() => onNavigate?.(ev)}
                              title={`${ev.snippet ?? ""}${
                                ev.requires_review ? " · Beleg einsehbar, aber zu prüfen" : ""
                              }`}
                            >
                              {ev.page != null ? `Seite ${ev.page}` : "Quelle"}
                              {ev.requires_review ? " · zu prüfen" : ""}
                            </button>
                          );
                        })}
                      </>
                    )}
                  </div>
                )}
                {s.reviewed_at && (
                  <div className="fact-review-result">
                    <span className="fact-review-result-action">
                      {reviewResultLabel(s.state)}
                    </span>
                    <span className="fact-review-result-meta">
                      {" "}· Prüfer: {s.reviewer_display_name ?? "–"} · {stampTime(s.reviewed_at)}
                    </span>
                  </div>
                )}
                <div className="override-row fact-state-actions">
                  <button type="button" className="btn btn-sm" onClick={() => confirmFact(fk)} disabled={busy}>
                    Bestätigen
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setOpenFact(open ? null : fk)}
                    disabled={busy}
                  >
                    {open ? "Abbrechen" : "Korrigieren"}
                  </button>
                  {s.state !== "unreviewed" && (
                    <button type="button" className="btn-link" onClick={() => reopenFact(fk)} disabled={busy}>
                      Erneut öffnen
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => setHistoryFact(showHistory ? null : fk)}
                  >
                    {showHistory ? "Historie ausblenden" : "Historie"}
                  </button>
                </div>
                {open && (
                  <div className="override-row">
                    <input
                      type="text"
                      placeholder="Korrigierter Wert"
                      value={corrected[fk] ?? ""}
                      onChange={(e) =>
                        setCorrected((prev) => ({ ...prev, [fk]: e.target.value }))
                      }
                      aria-label={`Korrigierter Wert für ${s.label_de}`}
                    />
                    <button type="button" className="btn btn-sm" onClick={() => correctFact(fk)} disabled={busy}>
                      Speichern
                    </button>
                  </div>
                )}
                {showHistory && (
                  <ul className="audit-list">
                    {historyByFact(fk).length === 0 && (
                      <li className="muted small">Noch keine Einträge.</li>
                    )}
                    {historyByFact(fk).map((r) => (
                      <li key={r.id}>
                        <span className={`audit-action audit-${r.action}`}>
                          {ACTION_LABEL[r.action] ?? r.action_label_de ?? r.action}
                        </span>
                        <span className="audit-key" title={r.fact_key}>
                          {r.fact_label_de || r.fact_key}
                        </span>
                        {r.action === "confirmed" && (
                          <span className="audit-value">Wert übernommen (kein Override)</span>
                        )}
                        {r.action === "corrected" && (
                          <>
                            <span className="audit-old">
                              {valueText(r.previous_effective_value)} →{" "}
                            </span>
                            <span className="audit-value">{valueText(r.new_effective_value)}</span>
                          </>
                        )}
                        {r.note && <span className="muted"> – {r.note}</span>}
                        <span className="audit-date">{stampTime(r.created_at)}</span>
                        <span className="audit-ref">{identityHint(r.reviewer_identity_type)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
