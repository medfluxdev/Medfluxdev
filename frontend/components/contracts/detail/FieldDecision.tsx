"use client";

import { useId, useState, type RefObject } from "react";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import type { ContractDetailResponse, FieldCandidateDto, FieldEvidenceDto, FieldReviewDto, FieldReviewFieldDto } from "@/lib/contract-detail-types";
import { decideField, setFieldEvidence, type FieldDecision as Decision } from "@/lib/domain-api/contracts";
import { SOURCE_TONE, STATUS_TONE, TIER_SHORT, candidateEvidence } from "@/lib/field-review";
import { formatDateTime } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = { stored: "Gespeichert", document: "Aus dem Dokument", conflict: "Berechnung", analysis: "Neue Analyse", finding: "Weitere Information" };

/**
 * Entscheidung zu einem Feld – dieselbe Oberfläche in der Karte (Schublade) und in der geführten Prüfung.
 * Zeigt den gespeicherten Wert, die Kandidaten mit ihren Belegen und lässt entscheiden: Wert bestätigen/übernehmen,
 * von Hand korrigieren, zurückstellen oder „nicht im Dokument“ festhalten. Nachweise lassen sich zum Hauptnachweis
 * machen oder (mit Grund) ausschließen, ohne den Wert zu verändern. Alles läuft über die Feldprüfung der API.
 */
export default function FieldDecision({
  contractId, orgSlug, field, review, canReview, onChanged, onShowEvidence, onShowPage, onOpenAnalysis, headingRef, level = 3,
}: {
  contractId: string;
  orgSlug: string;
  field: FieldReviewFieldDto;
  review: FieldReviewDto;
  canReview: boolean;
  /** Eine Entscheidung wurde gespeichert (Antwort = neuer Stand des Vertrags). `decided` = das Feld ist jetzt abgeschlossen. */
  onChanged: (detail: ContractDetailResponse | null, info: { decided: boolean }) => void;
  /** Nachweis im Original zeigen. */
  onShowEvidence?: (evidence: FieldEvidenceDto) => void;
  onShowPage?: (page: number | null, quote: string | null) => void;
  /** Wert aus einer erneuten Analyse: dort übernehmen. */
  onOpenAnalysis?: () => void;
  headingRef?: RefObject<HTMLHeadingElement>;
  level?: 2 | 3;
}) {
  const toast = useToast();
  const ids = useId();
  const current = field.candidates.find((candidate) => candidate.is_current) ?? field.candidates[0] ?? null;
  const [picked, setPicked] = useState<string | null>(current?.key ?? null);
  const [mode, setMode] = useState<null | "manual" | "exclude">(null);
  const [manual, setManual] = useState({ value: "", note: "" });
  const [exclude, setExclude] = useState<{ id: string; reason: string; note: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  const selected = field.candidates.find((candidate) => candidate.key === picked) ?? current;
  const changes = Boolean(selected && current && selected.key !== current.key && field.present);
  const calculated = field.kind === "calculated";
  const decided = field.status === "decided" || field.status === "absent";
  const Heading = level === 2 ? "h2" : "h3";

  async function send(work: () => Promise<ContractDetailResponse>, success: string, decidedAfter: boolean) {
    setBusy(true);
    setError(null);
    try {
      const detail = await work();
      toast(success, "success");
      setMode(null);
      setExclude(null);
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

  const confirm = () => {
    if (!selected) return;
    void decide(changes ? "accept" : "keep", { candidate_key: selected.key, confirm_change: changes },
      changes ? `Wert geändert auf „${selected.display}“.` : "Bestätigt.");
  };

  const evidenceAction = (entry: FieldEvidenceDto, action: "primary" | "exclude" | "restore", extra: { reason?: string; note?: string } = {}) =>
    send(() => setFieldEvidence(contractId, orgSlug, { fact_key: field.fact_key, evidence_id: entry.evidence_id, action, expected_version: field.version, ...extra }),
      action === "primary" ? "Hauptnachweis gewählt." : action === "exclude" ? "Nachweis ausgeschlossen – der Wert bleibt unverändert." : "Nachweis wiederhergestellt.", false);

  const unresolvedSource = field.present && field.source_state !== null && field.source_state !== "verified" && field.source_state !== "located";

  return <div className="fd">
    <header className="fd-head">
      <Heading ref={headingRef} tabIndex={-1} className="fd-title">{field.label}</Heading>
      <div className="fd-chips">
        <span className={`fd-tier fd-tier--${field.tier}`}>{TIER_SHORT[field.tier]}</span>
        <span className="fd-card">{field.card_label}</span>
        <Signal tone={STATUS_TONE[field.status]} size="sm">{field.status_label}</Signal>
      </div>
    </header>

    {field.why && field.decision_needed ? <p className="fd-why">{field.why}</p> : null}
    {field.reason && field.status !== "decided" ? <InlineAlert tone={field.status === "conflict" || field.status === "changed" || field.status === "missing" ? "warning" : "info"} role="status">{field.reason}</InlineAlert> : null}
    {stale ? <InlineAlert tone="info" role="status">Das Feld wurde inzwischen geändert. Der aktuelle Stand ist geladen – bitte neu entscheiden.</InlineAlert> : null}

    {calculated ? <section className="fd-calc" aria-label="Berechneter Wert">
      <p className="fd-value">{field.current ?? <span className="fd-muted">Noch nicht berechenbar</span>}</p>
      <p className="fd-muted">{field.status === "derived" ? "Berechnet aus geprüften Angaben – keine eigene Bestätigung nötig." : "Wird berechnet, sobald die Angaben unten geklärt sind."}</p>
      {field.inputs.length ? <ul className="fd-inputs">{field.inputs.map((input) => <li key={input.fact_key}>
        <span>{input.label}</span><Signal tone={input.decided ? "done" : "ai"} size="sm">{input.decided ? "Geklärt" : "Offen"}</Signal>
      </li>)}</ul> : null}
    </section> : <>
      {!field.present && field.status !== "absent" ? <p className="fd-missing">Im Dokument wurde kein Wert gefunden. Nichts wird vermutet.</p> : null}
      {field.candidates.length > 1
        ? <fieldset className="fd-cands" disabled={!canReview || busy}>
          <legend>Welcher Wert gilt?</legend>
          {field.candidates.map((candidate) => <CandidateCard key={candidate.key} name={`${ids}-cand`} field={field} candidate={candidate} picked={picked === candidate.key}
            onPick={() => setPicked(candidate.key)} {...{ canReview, busy, onShowEvidence, onShowPage, onOpenAnalysis }}
            onExclude={(entry) => { setMode("exclude"); setExclude({ id: entry.evidence_id, reason: "", note: "" }); }}
            onPrimary={(entry) => void evidenceAction(entry, "primary")} onRestore={(entry) => void evidenceAction(entry, "restore")} />)}
        </fieldset>
        : selected ? <div className="fd-cands">
          <CandidateCard name={`${ids}-cand`} field={field} candidate={selected} picked single {...{ canReview, busy, onShowEvidence, onShowPage, onOpenAnalysis }}
            onPick={() => undefined}
            onExclude={(entry) => { setMode("exclude"); setExclude({ id: entry.evidence_id, reason: "", note: "" }); }}
            onPrimary={(entry) => void evidenceAction(entry, "primary")} onRestore={(entry) => void evidenceAction(entry, "restore")} />
        </div> : null}

      {unresolvedSource ? <InlineAlert tone="warning" role="status">
        {field.source_state === "unavailable" ? "Das Dokument ist nicht verfügbar." : "Die Fundstelle konnte nicht aufgelöst werden."} Der Wert gilt hier nicht als belegt – bestätigen Sie ihn nur, wenn Sie ihn anders prüfen können.
      </InlineAlert> : null}

      {changes && selected ? <div className="fd-change" role="status">
        <strong>Das ändert den gespeicherten Wert</strong>
        <span><span className="fd-from">{current?.display ?? "leer"}</span> → <span className="fd-to">{selected.display}</span></span>
        <small>Der bisherige Wert bleibt mit seinen Belegen im Verlauf erhalten.</small>
      </div> : null}

      {mode === "exclude" && exclude ? <form className="fd-form" aria-label="Nachweis ausschließen" onSubmit={(event) => {
        event.preventDefault();
        const entry = field.evidence.find((item) => item.evidence_id === exclude.id);
        if (entry) void evidenceAction(entry, "exclude", { reason: exclude.reason, note: exclude.note });
      }}>
        <h4>Nachweis ausschließen</h4>
        <p className="fd-muted">Der Nachweis bleibt erhalten und sichtbar; der Wert des Felds ändert sich dadurch nicht.</p>
        <label className="fd-field">Grund
          <select value={exclude.reason} onChange={(event) => setExclude({ ...exclude, reason: event.target.value })} required>
            <option value="">Bitte wählen</option>
            {review.exclusion_reasons.map((reason) => <option key={reason.key} value={reason.key}>{reason.label}</option>)}
          </select>
        </label>
        <label className="fd-field">Notiz{exclude.reason === "other" ? " (erforderlich)" : " (optional)"}
          <input value={exclude.note} onChange={(event) => setExclude({ ...exclude, note: event.target.value })} required={exclude.reason === "other"} />
        </label>
        <div className="fd-row">
          <button type="submit" className="btn btn-primary" disabled={busy || !exclude.reason}>{busy ? "Wird gespeichert…" : "Ausschließen"}</button>
          <button type="button" className="btn" onClick={() => { setMode(null); setExclude(null); }}>Abbrechen</button>
        </div>
      </form> : null}

      {mode === "manual" ? <form className="fd-form" aria-label={field.present ? "Von Hand korrigieren" : "Wert eintragen"} onSubmit={(event) => { event.preventDefault(); void decide("manual", { value: manual.value, note: manual.note }, "Wert gespeichert."); }}>
        <h4>{field.present ? "Von Hand korrigieren" : "Wert eintragen"}</h4>
        <label className="fd-field">Richtiger Wert
          <input value={manual.value} onChange={(event) => setManual({ ...manual, value: event.target.value })} required autoFocus />
        </label>
        <label className="fd-field">Notiz (optional)
          <input value={manual.note} onChange={(event) => setManual({ ...manual, note: event.target.value })} />
        </label>
        <div className="fd-row">
          <button type="submit" className="btn btn-primary" disabled={busy || !manual.value.trim()}>{busy ? "Wird gespeichert…" : "Speichern"}</button>
          <button type="button" className="btn" onClick={() => setMode(null)}>Abbrechen</button>
        </div>
      </form> : null}

      {error ? <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => setError(null)}>Schließen</button>}>{error}</InlineAlert> : null}

      {!canReview ? <p className="fd-muted">Nur Lesen – entscheiden dürfen Prüfende und das Vertragsmanagement.</p>
        : mode === null ? <div className="fd-actions">
          {field.present && selected ? <button type="button" className="btn btn-primary" disabled={busy || (decided && !changes)} onClick={confirm}>
            {busy ? "Wird gespeichert…" : changes ? "Änderung übernehmen" : decided ? "Entschieden" : field.candidates.length > 1 ? "Diesen Wert bestätigen" : "Bestätigen"}
          </button> : null}
          <button type="button" className="btn" disabled={busy} onClick={() => { setManual({ value: "", note: "" }); setMode("manual"); }}>{field.present ? "Von Hand korrigieren" : "Wert eintragen"}</button>
          {field.decision_needed && field.status !== "deferred" && field.status !== "missing" ? <button type="button" className="btn" disabled={busy} onClick={() => void decide("defer", {}, "Zurückgestellt.")}>Zurückstellen</button> : null}
          {!field.present && field.status !== "absent" ? <button type="button" className="btn" disabled={busy} onClick={() => void decide("not_in_document", {}, "Als „nicht im Dokument“ festgehalten.")}>Nicht im Dokument</button> : null}
        </div> : null}
      {field.reviewer && field.reviewed_at ? <p className="fd-muted fd-by">Zuletzt entschieden von {field.reviewer} · {formatDateTime(field.reviewed_at)}</p> : null}
    </>}

    {field.history.length ? <details className="fd-history">
      <summary>Verlauf ({field.history.length})</summary>
      <ul>{field.history.map((entry, position) => <li key={`${entry.at}-${position}`}>
        <strong>{entry.label}</strong>{entry.by ? ` · ${entry.by}` : ""}{entry.at ? ` · ${formatDateTime(entry.at)}` : ""}
        {entry.detail ? <span className="fd-muted"> – {entry.detail}</span> : null}
        {entry.from != null || entry.to != null ? <span className="fd-muted"> ({String(entry.from ?? "–")} → {String(entry.to ?? "–")})</span> : null}
        {entry.alternatives?.length ? <span className="fd-muted"> · Nicht gewählt: {entry.alternatives.map((alt) => alt.display).join("; ")}</span> : null}
      </li>)}</ul>
    </details> : null}
  </div>;
}

function CandidateCard({
  name, field, candidate, picked, single = false, canReview, busy, onPick, onShowEvidence, onShowPage, onOpenAnalysis, onExclude, onPrimary, onRestore,
}: {
  name: string;
  field: FieldReviewFieldDto;
  candidate: FieldCandidateDto;
  picked: boolean;
  single?: boolean;
  canReview: boolean;
  busy: boolean;
  onPick: () => void;
  onShowEvidence?: (evidence: FieldEvidenceDto) => void;
  onShowPage?: (page: number | null, quote: string | null) => void;
  onOpenAnalysis?: () => void;
  onExclude: (entry: FieldEvidenceDto) => void;
  onPrimary: (entry: FieldEvidenceDto) => void;
  onRestore: (entry: FieldEvidenceDto) => void;
}) {
  const entries = candidateEvidence(field, candidate);
  const active = entries.filter((entry) => !entry.excluded).length;
  const sources = candidate.sources.map((source) => source.label || SOURCE_LABEL[source.source]).join(" · ");
  const body = <>
    <span className="fd-cand-head">
      <span className="fd-value">{candidate.display}</span>
      {candidate.is_current ? <Signal tone="neutral" size="sm">Aktuell</Signal> : null}
    </span>
    <span className="fd-muted">{sources}{candidate.detail ? ` – ${candidate.detail}` : ""}</span>
    {entries.length || candidate.inline_evidence.length
      ? <span className="fd-support">{active + candidate.inline_evidence.length === 1 ? "1 Fundstelle" : `${active + candidate.inline_evidence.length} übereinstimmende Fundstellen`}{active + candidate.inline_evidence.length > 1 ? " – eine Entscheidung genügt" : ""}</span>
      : <span className="fd-support fd-support--none">Kein Beleg im Dokument{candidate.sources.some((source) => source.source === "conflict") ? " (berechnet)" : ""}</span>}
  </>;
  return <div className={`fd-cand${picked ? " is-picked" : ""}`}>
    {single
      ? <div className="fd-cand-main">{body}</div>
      : <label className="fd-cand-main"><input type="radio" name={name} checked={picked} onChange={onPick} /><span className="fd-cand-body">{body}</span></label>}
    {entries.length ? <ul className="fd-evidence" aria-label={`Belege zu ${candidate.display}`}>
      {entries.map((entry) => <li key={entry.evidence_id} className={entry.excluded ? "is-excluded" : undefined}>
        <div className="fd-ev-head">
          <button type="button" className="fd-ev-page" onClick={() => onShowEvidence?.(entry)} disabled={!entry.document_available && !entry.page}
            aria-label={`${entry.page != null ? `Seite ${entry.page}` : "Fundstelle"} im Dokument zeigen`}>{entry.page != null ? `Seite ${entry.page}` : "Ohne Seite"}</button>
          <Signal tone={SOURCE_TONE[entry.source_state]} size="sm" title={entry.source_state_label}>{entry.source_state_label}</Signal>
          {entry.primary ? <Signal tone="info" size="sm">Hauptnachweis</Signal> : null}
          {entry.excluded ? <Signal tone="neutral" size="sm">Ausgeschlossen</Signal> : null}
        </div>
        {entry.snippet ? <blockquote className="fd-quote">„{entry.snippet}“</blockquote> : null}
        {entry.excluded ? <p className="fd-muted">{entry.exclusion_reason_label}{entry.exclusion_note ? ` – ${entry.exclusion_note}` : ""}{entry.excluded_by ? ` · ${entry.excluded_by}` : ""}</p> : null}
        {canReview ? <div className="fd-ev-actions">
          {entry.excluded
            ? <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onRestore(entry)}>Wiederherstellen</button>
            : <>
              {!entry.primary && active > 1 ? <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onPrimary(entry)}>Als Hauptnachweis</button> : null}
              <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onExclude(entry)}>Ausschließen</button>
            </>}
        </div> : null}
      </li>)}
    </ul> : null}
    {candidate.inline_evidence.length ? <ul className="fd-evidence" aria-label="Belege aus der Analyse">
      {candidate.inline_evidence.map((entry, position) => <li key={position}>
        <div className="fd-ev-head"><button type="button" className="fd-ev-page" onClick={() => onShowPage?.(entry.page, entry.quote)}>{entry.page != null ? `Seite ${entry.page}` : "Ohne Seite"}</button></div>
        {entry.quote ? <blockquote className="fd-quote">„{entry.quote}“</blockquote> : null}
      </li>)}
    </ul> : null}
    {candidate.proposal_id ? <p className="fd-analysis">Dieser Wert kommt aus Analyse #{candidate.run_number}. {onOpenAnalysis ? <button type="button" className="rg-link" onClick={onOpenAnalysis}>Dort übernehmen</button> : "Übernehmen können Sie ihn in der KI-Analyse."}</p> : null}
  </div>;
}
