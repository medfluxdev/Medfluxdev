"use client";

import Link from "next/link";
import { useState } from "react";
import Popover from "@/components/ui/Popover";
import { useToast } from "@/components/ui/Toast";
import { ApiError, apiPost } from "@/lib/api";
import type { DetailWarning } from "@/lib/contract-detail-types";
import { contractHref, warningTarget } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";

export interface RiskInfo {
  computed: string | null;
  effective: string | null;
  override: { level: string; reason: string | null; by: string | null; at: string | null } | null;
  confirmed: { by: string | null; at: string | null } | null;
}

const LABEL: Record<string, string> = { low: "niedrig", medium: "mittel", high: "hoch", unknown: "unbekannt" };
const SEVERITY: Record<string, string> = { critical: "kritisch", high: "hoch", medium: "mittel", low: "niedrig", info: "Hinweis" };
const RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function label(level: string | null | undefined) {
  return level ? LABEL[level] ?? level : "unbekannt";
}

/**
 * „Risiko hoch“ im Kopf: woher die Einschätzung kommt (aktive Warnungen, je mit Link zur Stelle),
 * bestätigen oder mit Begründung anders festlegen bzw. zurücksetzen.
 */
export default function RiskButton({ contractId, orgSlug, risk, warnings, canEdit, onChanged }: {
  contractId: string;
  orgSlug: string;
  risk: RiskInfo | null | undefined;
  warnings: DetailWarning[];
  canEdit: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<{ level: string; reason: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const effective = risk?.effective ?? null;
  // Wie bisher: nur auffällige oder von Hand festgelegte Einschätzungen erscheinen im Kopf.
  if (!risk || (!risk.override && effective !== "high" && effective !== "medium")) return null;

  const reasons = warnings
    .filter((item) => (RANK[item.severity] ?? 4) <= 2)
    .sort((a, b) => (RANK[a.severity] ?? 4) - (RANK[b.severity] ?? 4));

  async function decide(body: { action: "confirm" | "override" | "reset"; level?: string; reason?: string }, done: string) {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/api/contracts/${encodeURIComponent(contractId)}/risk?organization_slug=${encodeURIComponent(orgSlug)}`, body);
      toast(done, "success");
      setForm(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError && err.message ? err.message : "Das Risiko konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  const suffix = risk.override ? " · festgelegt" : risk.confirmed ? " · bestätigt" : "";
  return <Popover
    className={`risk-button risk-button--${effective ?? "unknown"}`}
    label={<><span aria-hidden="true">⚠ </span>Risiko {label(effective)}{suffix}</>}
    panelLabel="Risiko des Vertrags"
    wide
  >
    {(close) => <div className="risk-panel">
      <p className="risk-title">Berechnet: Risiko {label(risk.computed)}</p>
      <p className="field-hint">Aus dem höchsten Schweregrad der aktiven Warnungen dieses Vertrags.</p>
      {reasons.length ? <ul className="risk-reasons">{reasons.map((item, index) => {
        const target = warningTarget(item.warning_type, item.requires_review);
        return <li key={`${item.warning_type}-${index}`}>
          <span className="cw-muted">{SEVERITY[item.severity] ?? item.severity}</span>
          {target ? <Link href={contractHref(contractId, target)} onClick={close}>{item.title_de}</Link> : <span>{item.title_de}</span>}
        </li>;
      })}</ul> : <p className="cw-muted">Keine aktiven Warnungen.</p>}

      {risk.override ? <p className="risk-decision" role="status">
        Von Hand festgelegt: <strong>{label(risk.override.level)}</strong>
        {risk.override.reason ? <> – „{risk.override.reason}“</> : null}
        {risk.override.by ? <> ({risk.override.by}{risk.override.at ? `, ${formatDate(risk.override.at)}` : ""})</> : null}
      </p> : null}
      {risk.confirmed ? <p className="risk-decision" role="status">Bestätigt von {risk.confirmed.by ?? "–"}{risk.confirmed.at ? ` am ${formatDate(risk.confirmed.at)}` : ""}.</p> : null}

      {canEdit && form ? <form className="risk-form" onSubmit={(event) => { event.preventDefault(); void decide({ action: "override", level: form.level, reason: form.reason }, "Risiko festgelegt."); }}>
        <label className="field"><span className="field-label">Risiko</span>
          <select value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })}>
            <option value="low">Niedrig</option><option value="medium">Mittel</option><option value="high">Hoch</option>
          </select>
        </label>
        <label className="field"><span className="field-label">Begründung</span>
          <textarea rows={2} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} placeholder="Warum wird das Risiko anders eingeschätzt?" />
        </label>
        <div className="reextraction-actions">
          <button type="button" className="btn btn-sm" onClick={() => setForm(null)} disabled={busy}>Abbrechen</button>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy || form.reason.trim().length < 3}>Festlegen</button>
        </div>
      </form> : null}

      {canEdit && !form ? <div className="reextraction-actions">
        {!risk.override && !risk.confirmed ? <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void decide({ action: "confirm" }, "Risiko bestätigt.")}>Bestätigen</button> : null}
        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => setForm({ level: risk.override?.level ?? effective ?? "medium", reason: "" })}>Anders einschätzen …</button>
        {risk.override ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => void decide({ action: "reset" }, "Risiko wird wieder berechnet.")}>Auf berechneten Wert zurücksetzen</button> : null}
      </div> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </div>}
  </Popover>;
}
