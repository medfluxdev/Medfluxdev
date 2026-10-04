"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  const [checking, setChecking] = useState(true);
  const [queue, setQueue] = useState<ContractDeletionQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageLoading, setPageLoading] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    const current = ++generation.current;
    setChecking(true);
    setAllowed(false);
    setQueue(null);
    setOffset(0);
    setConfirmId(null);
    setError(null);
    if (loading || !organizationSlug || role !== "admin") {
      setChecking(false);
      return;
    }
    try {
      const capability = await getContractDeletionCapabilities(organizationSlug);
      if (current !== generation.current || !capability.can_delete) return;
      const result = await getContractDeletionQueue(organizationSlug);
      if (current !== generation.current) return;
      setQueue(result);
      setAllowed(true);
    } catch {
      if (current === generation.current) setError("Die Löschverwaltung ist nicht verfügbar oder nicht freigegeben.");
    } finally {
      if (current === generation.current) setChecking(false);
    }
  }, [organizationSlug, role, loading]);

  useEffect(() => {
    void refresh();
    return () => { generation.current += 1; };
  }, [refresh]);

  async function changePage(next: number) {
    if (!organizationSlug || pageLoading) return;
    const current = generation.current;
    setPageLoading(true);
    setError(null);
    try {
      const result = await getContractDeletionQueue(organizationSlug, next);
      if (current !== generation.current) return;
      setQueue(result);
      setOffset(next);
    } catch (err) {
      if (current === generation.current) setError(err instanceof Error ? err.message : "Weitere Einträge konnten nicht geladen werden.");
    } finally {
      setPageLoading(false);
    }
  }

  async function act(id: string, action: "cancel" | "confirm" | "restore") {
    if (!organizationSlug || busy || !allowed || checking || pageLoading) return;
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

  if (loading) return <main className="page"><p role="status">Benutzerberechtigungen werden geladen…</p></main>;

  if (role !== "admin") return <main className="page"><h1>Keine Berechtigung</h1><p>Diese Funktion ist nur für freigegebene Administratoren verfügbar.</p></main>;

  return <main className="page">
    <header><h1>Vertragslöschung verwalten</h1>
      <p>Nur ausdrücklich freigegebene Administratoren. Keine endgültige Datenvernichtung.</p>
    </header>
    {error && <p role="alert">{error}</p>}
    {checking && <p role="status">Berechtigungen werden geprüft…</p>}
    {!checking && !allowed && !error && <p>Die Löschverwaltung ist für diese Organisation nicht freigegeben.</p>}
    {allowed && queue && <>
      {queue.items.length === 0 && <p>Keine vorgemerkten oder gelöschten Verträge.</p>}
      {queue.items.length > 0 && <p role="status">Einträge {offset + 1}–{offset + queue.items.length}</p>}
      <div className="btn-group mb-4">
        <button type="button" disabled={checking || pageLoading || busy !== null || offset === 0} onClick={() => void changePage(Math.max(0, offset - 100))}>Zurück</button>
        <button type="button" disabled={checking || pageLoading || busy !== null || !queue.has_more || queue.next_offset === null} onClick={() => { if (queue.next_offset !== null) void changePage(queue.next_offset); }}>Weitere anzeigen</button>
      </div>
      {queue.items.map((item) => <section className="panel mb-4" key={item.contract_id}>
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
