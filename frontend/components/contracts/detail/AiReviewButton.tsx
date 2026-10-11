"use client";

import Link from "next/link";
import Signal from "@/components/ui/Signal";
import { useCallback, useEffect, useMemo, useState } from "react";
import Popover from "@/components/ui/Popover";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { getContractRegister, updateContractRegister, type ContractRegister } from "@/lib/domain-api/register";
import { baseFieldKey, contractHref, REVIEW_TARGET } from "@/lib/fix-targets";

/** Nach jeder Änderung an den Vertragsdaten (Kopf und Reiter „Vertragsdaten“ bleiben gleich). */
export const REGISTER_CHANGED_EVENT = "medflux:register-changed";

export function announceRegisterChange() {
  window.dispatchEvent(new Event(REGISTER_CHANGED_EVENT));
}

type OpenItem = { key: string; label: string; keys: string[] };

/** Noch nicht bestätigte KI-Werte, je Feld einmal (Zeiträume: Anzahl + Einheit = ein Feld). */
export function openAiValues(register: ContractRegister | null): OpenItem[] {
  if (!register) return [];
  const items = new Map<string, OpenItem>();
  // Unvollständige Antwort: lieber nichts zeigen, als die Akte zu stören.
  for (const [key, field] of Object.entries(register.fields ?? {})) {
    if (field?.origin !== "ai") continue;
    const base = baseFieldKey(key);
    const item = items.get(base) ?? { key: base, label: field.label.replace(/ \(Einheit\)$/, ""), keys: [] };
    item.keys.push(key);
    if (base === key) item.label = field.label;
    items.set(base, item);
  }
  return Array.from(items.values());
}

/**
 * KI-Prüfung im Kopf der Vertragsakte (auf jedem Reiter sichtbar): noch nicht bestätigte KI-Werte
 * direkt bestätigen oder zum Feld springen, und der Weg zur Prüfung im Dokument.
 */
export default function AiReviewButton({ contractId, orgSlug, reviewPending, canEdit, version, onCount }: {
  contractId: string;
  orgSlug: string;
  /** Prüfung der Werte am Dokument (Dokumente → Prüfung) noch offen. */
  reviewPending: boolean;
  canEdit: boolean;
  /** Neu laden, wenn sich die Vertragsakte ändert. */
  version?: unknown;
  /** Meldet die Zahl offener KI-Werte (z. B. für das Symbol am Reiter „Vertragsdaten“). */
  onCount?: (count: number) => void;
}) {
  const toast = useToast();
  const [register, setRegister] = useState<ContractRegister | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getContractRegister(orgSlug, contractId).then(setRegister).catch(() => setRegister(null));
  }, [contractId, orgSlug]);
  // Änderungen im Reiter „Vertragsdaten“ laden die Akte neu (`version`) – dann hier ebenfalls.
  useEffect(load, [load, version]);

  const open = useMemo(() => openAiValues(register), [register]);
  useEffect(() => { onCount?.(open.length); }, [onCount, open.length]);
  // KI-Prüfung im Kopf: unbestätigte KI-Werte (Liste zum Bestätigen) oder die offene Prüfung am Dokument.
  if (open.length === 0) {
    if (!reviewPending) return null;
    return <Link className="ai-review-link" href={contractHref(contractId, REVIEW_TARGET)} title="Werte aus dem Dokument mit dem Vertrag vergleichen">
      <Signal tone="ai">KI-Prüfung offen</Signal>
    </Link>;
  }

  async function confirm(keys: string[], success: string) {
    setBusy(true);
    try {
      setRegister(await updateContractRegister(orgSlug, contractId, { changes: {}, confirm: keys }));
      toast(success, "success");
      announceRegisterChange();
    } catch (error) {
      toast(error instanceof ApiError && error.message ? error.message : "Die Bestätigung ist fehlgeschlagen.", "error");
    } finally {
      setBusy(false);
    }
  }

  const label = `KI-Prüfung · ${open.length}`;
  return <Popover
    className="ai-review"
    label={<><span aria-hidden="true">✦ </span>{label}</>}
    panelLabel="KI-Werte prüfen"
    align="start"
    wide
  >
    {(close) => <div className="ai-review-panel">
      {open.length ? <>
        <p className="ai-review-title">{open.length === 1 ? "1 KI-Wert noch nicht bestätigt" : `${open.length} KI-Werte noch nicht bestätigt`}</p>
        <ul className="ai-review-list">
          {open.map((item) => <li key={item.key}>
            <Link href={contractHref(contractId, { tab: "register", field: item.key })} onClick={close}>{item.label}</Link>
            {canEdit ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => confirm(item.keys, `${item.label} bestätigt.`)} aria-label={`${item.label} bestätigen`}>Bestätigen</button> : null}
          </li>)}
        </ul>
      </> : <p className="ai-review-title">Alle KI-Werte in den Vertragsdaten sind bestätigt.</p>}
      <div className="ai-review-actions">
        {canEdit && open.length > 1 ? <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => confirm(open.flatMap((item) => item.keys), `${open.length} KI-Werte bestätigt.`)}>Alle bestätigen</button> : null}
        <Link className="btn btn-sm" href={contractHref(contractId, REVIEW_TARGET)} onClick={close}>{reviewPending ? "Im Dokument prüfen (offen)" : "Im Dokument prüfen"}</Link>
      </div>
      <p className="field-hint">Bestätigen heißt: Sie haben den Wert mit dem Vertrag verglichen. Den Beleg zeigt „Im Dokument prüfen“.</p>
    </div>}
  </Popover>;
}
