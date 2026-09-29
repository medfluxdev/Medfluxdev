"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  confirmContractDeletion,
  cancelContractDeletion,
  getContractDeletionCapabilities,
  getContractDeletionQueue,
  restoreDeletedContract,
  type ContractDeletionQueue,
} from "@/lib/domain-api/contracts";

export default function DeletionQueuePage() {
  const { organizationSlug } = useAuth();
  const [allowed, setAllowed] = useState(false);
  const [queue, setQueue] = useState<ContractDeletionQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setAllowed(false);
    setQueue(null);
    if (!organizationSlug) return;
    try {
      const capability = await getContractDeletionCapabilities(organizationSlug);
      if (!capability.can_delete) return;
      const result = await getContractDeletionQueue(organizationSlug);
      setQueue(result);
      setAllowed(true);
    } catch {
      setError("Die Löschverwaltung ist nicht verfügbar oder nicht freigegeben.");
    }
  }, [organizationSlug]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function act(id: string, action: "cancel" | "confirm" | "restore") {
    if (!organizationSlug || busy) return;
    setBusy(id);
    setError(null);
    try {
      if (action === "cancel") await cancelContractDeletion(id, organizationSlug);
      if (action === "confirm") await confirmContractDeletion(id, organizationSlug);
      if (action === "restore") await restoreDeletedContract(id, organizationSlug);
      setConfirmId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(null);
    }
  }

  return <main className="page">
    <header><h1>Vertragslöschung verwalten</h1>
      <p>Nur ausdrücklich freigegebene Administratoren. Keine endgültige Datenvernichtung.</p>
    </header>
    {error && <p role="alert">{error}</p>}
    {!allowed && !error && <p>Keine Löschberechtigung oder Daten werden geladen.</p>}
    {allowed && queue && <>
      {queue.items.length === 0 && <p>Keine vorgemerkten oder gelöschten Verträge.</p>}
      {queue.has_more && <p role="status">Weitere Einträge vorhanden. Bitte die Liste eingrenzen lassen.</p>}
      {queue.items.map((item) => <section className="panel" key={item.contract_id} style={{ padding: "1rem", marginBottom: "1rem" }}>
        <h2>{item.contract_number || item.contract_id}</h2>
        <p>Status: {item.lifecycle_state === "pending_deletion" ? "Zur Löschung vorgemerkt" : "Gelöscht (wiederherstellbar)"}</p>
        {item.lifecycle_state === "pending_deletion" ? <>
          <button type="button" disabled={busy !== null} onClick={() => void act(item.contract_id, "cancel")}>Löschung abbrechen</button>{" "}
          <button type="button" disabled={busy !== null} onClick={() => setConfirmId(item.contract_id)}>Löschung bestätigen</button>
          {confirmId === item.contract_id && <div role="dialog" aria-modal="true" aria-label="Löschung bestätigen">
            <p>Der Vertrag wird aus aktiven Ansichten entfernt, bleibt aber wiederherstellbar.</p>
            <button type="button" disabled={busy !== null} onClick={() => setConfirmId(null)}>Zurück</button>{" "}
            <button type="button" disabled={busy !== null} onClick={() => void act(item.contract_id, "confirm")}>Ja, Löschung bestätigen</button>
          </div>}
        </> : <button type="button" disabled={busy !== null} onClick={() => void act(item.contract_id, "restore")}>Vertrag wiederherstellen</button>}
      </section>)}
    </>}
  </main>;
}
