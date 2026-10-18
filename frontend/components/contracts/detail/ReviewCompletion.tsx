"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { apiPost } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/auth-types";
import type { ContractReviewDto } from "@/lib/contract-detail-types";
import { pluralize } from "@/lib/field-review";

/**
 * Vertragsreview: Stand, wer prüft, und der ausdrückliche Abschluss mit Notiz. Wesentliche (kritische) Angaben müssen
 * einzeln entschieden sein; verbleibende nicht-wesentliche ungeprüfte Angaben nur mit ausdrücklicher Bestätigung und Notiz.
 * „Review erneut öffnen“ nimmt den Abschluss zurück (Verlauf bleibt erhalten).
 */
export default function ReviewCompletion({ contractId, orgSlug, review, canReview, onReload }: {
  contractId: string;
  orgSlug: string;
  review: ContractReviewDto;
  canReview: boolean;
  onReload: () => void;
}) {
  const toast = useToast();
  const { account, role } = useAuth();
  const [ack, setAck] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reviewed = review.status === "reviewed";
  const locked = review.critical_unreviewed_count > 0;
  const blocked = locked || (review.unresolved_count > 0 && (!ack || !note.trim()));

  async function post(path: "start" | "complete") {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/api/contracts/${encodeURIComponent(contractId)}/review/${path}?organization_slug=${encodeURIComponent(orgSlug)}`, {
        note: path === "complete" ? note : null,
        acknowledge_unreviewed: path === "complete" ? ack : false,
      });
      toast(path === "complete" ? "Review abgeschlossen." : "Review erneut geöffnet.", "success");
      setNote("");
      setAck(false);
      onReload();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Review-Aktion konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="frv-review" aria-labelledby="frv-review-title">
    <div className="frv-review-state">
      <h3 id="frv-review-title">Vertragsreview</h3>
      <p>{review.reviewed_count} von {review.relevant_count} Angaben entschieden · {review.unresolved_count} offen{" "}
        <Signal tone={reviewed ? "done" : "neutral"} size="sm">{review.status_label_de}</Signal></p>
      {reviewed && review.reviewer_display_name ? <p className="fd-muted">Abgeschlossen von {review.reviewer_display_name}{review.completion_note ? ` – ${review.completion_note}` : ""}</p> : null}
      <p className="fd-muted frv-reviewer">Prüfung durch <strong>{account?.display_name ?? "Angemeldeter Benutzer"}</strong>{role ? ` · ${ROLE_LABELS[role]}` : ""}</p>
    </div>
    {canReview ? <div className="frv-review-actions">
      {locked ? <p className="fd-muted" role="alert">Abschluss gesperrt: {pluralize(review.critical_unreviewed_count, "wesentliche Angabe muss", "wesentliche Angaben müssen")} zuerst einzeln entschieden werden.</p> : null}
      {!reviewed && !locked && review.unresolved_count > 0 ? <label className="frv-ack"><input type="checkbox" checked={ack} onChange={(event) => setAck(event.target.checked)} /> Verbleibende nicht-wesentliche ungeprüfte Angaben akzeptieren</label> : null}
      {!reviewed && !locked ? <input className="frv-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder={review.unresolved_count > 0 ? "Abschluss-Notiz (erforderlich)" : "Abschluss-Notiz (optional)"} aria-label="Abschluss-Notiz" /> : null}
      <div className="fd-row">
        {!reviewed && !locked ? <button type="button" className="btn" disabled={busy || blocked} onClick={() => void post("complete")}>Review abschließen</button> : null}
        {reviewed || review.status === "changed_after_review" ? <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void post("start")}>Review erneut öffnen</button> : null}
      </div>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </div> : null}
  </section>;
}
