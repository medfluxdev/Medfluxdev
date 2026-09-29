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
  const { organizationSlug, role, loading } = useAuth();
  const [allowed, setAllowed] = useState(false);
  const [queue, setQueue] = useState<ContractDeletionQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageLoading, setPageLoading] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setAllowed(false);
    setQueue(null);
    setOffset(0);
    setConfirmId(null);
    setError(null);
    if (!organizationSlug || role !== "admin") return;
    try {
      const capability = await getContractDeletionCapabilities(organizationSlug);
      if (!capability.can_delete) return;
      const result = await getContractDeletionQueue(organizationSlug);
      setQueue(result);
      setAllowed(true);
    } catch {
      setError("Die Löschverwaltung ist nicht verfügbar oder nicht freigegeben.");
    }
  }, [organizationSlug, role]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function changePage(next: number) {
    if (!organizationSlug || pageLoading) return;
    setPageLoading(true);
    setError(null);
    try {
      const result = await getContractDeletionQueue(organizationSlug, next);
      setQueue(result);
      setOffset(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Weitere Einträge konnten nicht geladen werden.");
    } finally {
      setPageLoading(false);
    }
  }

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

  if (!loading && role !== "admin") return <main className="page"><h1>Keine Berechtigung</h1><p>Diese Funktion ist nur für freigegebene Administratoren verfügbar.</p></main>;

  return <main className="page">
    <header><h1>Vertragslöschung verwalten</h1>
      <p>Nur ausdrücklich freigegebene Administratoren. Keine endgültige Datenvernichtung.</p>
    </header>
    {error && <p role="alert">{error}</p>}
    {!allowed && !error && <p>Keine Löschberechtigung oder Daten werden geladen.</p>}
    {allowed && queue && <>
      {queue.items.length === 0 && <p>Keine vorgemerkten oder gelöschten Verträge.</p>}
      {queue.items.length > 0 && <p role="status">Einträge {offset + 1}–{offset + queue.items.length}</p>}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <button type="button" disabled={pageLoading || busy !== null || offset === 0} onClick={() => void changePage(Math.max(0, offset - 100))}>Zurück</button>
        <button type="button" disabled={pageLoading || busy !== null || !queue.has_more || queue.next_offset === null} onClick={() => { if (queue.next_offset !== null) void changePage(queue.next_offset); }}>Weitere anzeigen</button>
      </div>
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
