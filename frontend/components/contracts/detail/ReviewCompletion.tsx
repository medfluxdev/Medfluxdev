"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ActionMenu from "@/components/ui/ActionMenu";
import Dialog from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";
import { apiPost } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/auth-types";
import type { ContractReviewDto } from "@/lib/contract-detail-types";
import { pluralize } from "@/lib/field-review";

const WARN = <svg className="frv-warn-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></svg>;

/**
 * Kopf der Vertragsprüfung: Stand und Fortschritt, wer prüft, ein Hinweis auf wesentliche Angaben, die den Abschluss sperren,
 * und im ⋯-Menü der Abschluss („Review abschließen“ mit Notiz und ausdrücklicher Annahme verbleibender Angaben) bzw. „Review
 * erneut öffnen“. Der Verlauf bleibt in jedem Fall erhalten.
 */
export default function ReviewHeader({ contractId, orgSlug, review, fallback, canReview, onReload, onBlocking, onGuided }: {
  contractId: string;
  orgSlug: string;
  review: ContractReviewDto | null | undefined;
  /** Zähler aus der Feldprüfung, falls die Vertragsebene fehlt. */
  fallback: { total: number; decided: number };
  canReview: boolean;
  onReload: () => void;
  /** „Angabe prüfen“: zur ersten wesentlichen offenen Angabe. */
  onBlocking: () => void;
  /** Geführte Prüfung im Dokument. */
  onGuided?: (() => void) | null;
}) {
  const toast = useToast();
  const { account, role } = useAuth();
  const [dialog, setDialog] = useState(false);

  const total = review?.relevant_count ?? fallback.total;
  const decided = review?.reviewed_count ?? fallback.decided;
  const open = Math.max(0, total - decided);
  const pct = total ? Math.round((decided / total) * 100) : 0;
  const reviewed = review?.status === "reviewed";
  const blocking = review?.critical_unreviewed_count ?? 0;
  const unresolved = review?.unresolved_count ?? open;
  const canFinish = canReview && !reviewed && blocking === 0;

  async function reopen() {
    try {
      await apiPost(`/api/contracts/${encodeURIComponent(contractId)}/review/start?organization_slug=${encodeURIComponent(orgSlug)}`, { note: null, acknowledge_unreviewed: false });
      toast("Review erneut geöffnet.", "success");
      onReload();
    } catch (err) {
      toast(err instanceof Error && err.message ? err.message : "Die Review-Aktion konnte nicht gespeichert werden.", "error");
    }
  }

  const menu = [
    ...(onGuided ? [{ label: "Im Dokument prüfen", onSelect: onGuided }] : []),
    ...(canFinish ? [{ label: "Review abschließen …", onSelect: () => setDialog(true) }] : []),
    ...(canReview && (reviewed || review?.status === "changed_after_review") ? [{ label: "Review erneut öffnen", onSelect: () => void reopen() }] : []),
  ];

  return <div className="frv-head">
    <div className="frv-head-main">
      <div className="frv-head-title">
        <h2 id="frv-title">Vertragsprüfung</h2>
        {review ? <span className={`frv-status frv-status--${review.status}`}>{review.status_label_de}</span> : null}
      </div>
      <p className="frv-head-count"><strong>{decided} von {total}</strong> Angaben entschieden · {open} offen</p>
      <div className="frv-head-bar">
        <span className="frv-bar" role="progressbar" aria-label={`${decided} von ${total} Angaben entschieden`} aria-valuemin={0} aria-valuemax={total} aria-valuenow={decided}><i style={{ width: `${pct}%` }} /></span>
        <span className="frv-pct">{pct} %</span>
      </div>
      <p className="fd-muted frv-reviewer">
        {reviewed && review?.reviewer_display_name ? <>Geprüft von <strong>{review.reviewer_display_name}</strong>{review.completion_note ? ` – ${review.completion_note}` : ""}</>
          : <>Prüfung durch <strong>{account?.display_name ?? "Angemeldeter Benutzer"}</strong>{role ? ` · ${ROLE_LABELS[role]}` : ""}</>}
      </p>
    </div>
    <div className="frv-head-side">
      {menu.length ? <ActionMenu items={menu} label="Weitere Aktionen zur Vertragsprüfung" /> : null}
      {blocking > 0 ? <div className="frv-block">
        <p role="alert">{WARN}{pluralize(blocking, "wesentliche Angabe blockiert", "wesentliche Angaben blockieren")} den Abschluss</p>
        <button type="button" className="btn frv-block-go" onClick={onBlocking}>Angabe prüfen →</button>
      </div> : null}
    </div>

    <ReleaseDialog open={dialog} onClose={() => setDialog(false)} contractId={contractId} orgSlug={orgSlug} unresolved={unresolved} onDone={onReload} />
  </div>;
}

/**
 * Abschluss der Vertragsprüfung („Review abschließen“): Notiz und, solange Angaben ungeprüft sind, die ausdrückliche Annahme.
 * Eine Stelle für Prüfkopf und geführte Prüfung („Jetzt freigeben“ / „Vertrag freigeben“).
 */
export function ReleaseDialog({ open, onClose, contractId, orgSlug, unresolved, onDone }: {
  open: boolean; onClose: () => void; contractId: string; orgSlug: string; unresolved: number; onDone: () => void;
}) {
  const toast = useToast();
  const [ack, setAck] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blocked = unresolved > 0 && (!ack || !note.trim());

  async function complete() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/api/contracts/${encodeURIComponent(contractId)}/review/complete?organization_slug=${encodeURIComponent(orgSlug)}`, { note, acknowledge_unreviewed: ack });
      toast("Review abgeschlossen.", "success");
      onClose();
      setNote("");
      setAck(false);
      onDone();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Review-Aktion konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <Dialog open={open} title="Review abschließen" onClose={onClose}
    description={unresolved > 0 ? `${pluralize(unresolved, "Angabe ist", "Angaben sind")} noch ungeprüft. Zum Abschluss bitte ausdrücklich akzeptieren und kurz begründen.` : "Alle Angaben sind entschieden."}
    actions={<><button type="button" className="btn" onClick={onClose}>Abbrechen</button>
      <button type="button" className="btn btn-primary" disabled={busy || blocked} onClick={() => void complete()}>Review abschließen</button></>}>
    {unresolved > 0 ? <label className="frv-ack"><input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} /> Verbleibende nicht-wesentliche ungeprüfte Angaben akzeptieren</label> : null}
    <label className="erm-field">Abschluss-Notiz{unresolved > 0 ? " (erforderlich)" : " (optional)"}
      <input value={note} onChange={(event) => setNote(event.target.value)} />
    </label>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
  </Dialog>;
}
