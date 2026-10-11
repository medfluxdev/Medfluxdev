"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import Dialog from "@/components/ui/Dialog";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import Signal from "@/components/ui/Signal";
import {
  confirmContractDeletion,
  cancelContractDeletion,
  getContractDeletionCapabilities,
  getContractDeletionQueue,
  restoreDeletedContract,
  type ContractDeletionQueue,
} from "@/lib/domain-api/contracts";
import { formatDateTime } from "@/lib/format";

type Item = ContractDeletionQueue["items"][number];

function itemName(item: Item): string {
  return [item.register_number, item.short_description ?? item.contract_number].filter(Boolean).join(" · ") || "Vertrag";
}

// Verwaltung → Vertragslöschung: Anträge von Vertragsmanagement/Administration bestätigen oder ablehnen,
// gelöschte Verträge wiederherstellen. Nichts wird endgültig vernichtet.
export default function DeletionQueuePage() {
  const { organizationSlug, role, loading } = useAuth();
  const [allowed, setAllowed] = useState(false);
  const [checking, setChecking] = useState(true);
  const [queue, setQueue] = useState<ContractDeletionQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageLoading, setPageLoading] = useState(false);
  const [confirmItem, setConfirmItem] = useState<Item | null>(null);
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    const current = ++generation.current;
    setChecking(true);
    setAllowed(false);
    setQueue(null);
    setOffset(0);
    setConfirmItem(null);
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
      if (current === generation.current) setError("Die Vertragslöschung ist nicht verfügbar oder nicht freigegeben.");
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
      setConfirmItem(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <div className="page"><p role="status">Benutzerberechtigungen werden geladen…</p></div>;
  if (role !== "admin") {
    return <div className="page"><PageHeader title="Vertragslöschung" /><EmptyState title="Keine Berechtigung">Löschungen bestätigt die Administration.</EmptyState></div>;
  }

  const pending = queue?.items.filter((item) => item.lifecycle_state === "pending_deletion") ?? [];
  const deleted = queue?.items.filter((item) => item.lifecycle_state === "deleted") ?? [];

  return <div className="page">
    <PageHeader title="Vertragslöschung" description="Anträge von Vertragsmanagement und Administration bestätigen oder ablehnen. Gelöschte Verträge verschwinden aus allen Listen, bleiben aber wiederherstellbar – nichts wird endgültig vernichtet." />
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {checking ? <p role="status">Berechtigungen werden geprüft…</p> : null}
    {!checking && !allowed && !error ? <EmptyState title="Vertragslöschung ist ausgeschaltet">Sie lässt sich mit CONTRACTS_ALLOW_DELETE=true einschalten (nur mit Anmeldung).</EmptyState> : null}
    {allowed && queue ? <>
      <section className="card card-pad stack-4" aria-labelledby="deletion-pending-heading">
        <h2 id="deletion-pending-heading">Beantragt ({pending.length})</h2>
        {pending.length === 0 ? <EmptyState variant="calm" title="Keine offenen Anträge" /> : <ul className="deletion-list">{pending.map((item) => <li key={item.contract_id}>
          <div><Signal tone="warning" size="sm">Beantragt</Signal> <Link href={`/contracts/${item.contract_id}`}>{itemName(item)}</Link>{item.by_name ? <span className="cw-muted"> · von {item.by_name}</span> : null}</div>
          <div className="rg-actions">
            <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={() => void act(item.contract_id, "cancel")} aria-label={`Antrag für ${itemName(item)} ablehnen`}>Ablehnen</button>
            <button type="button" className="btn btn-danger btn-sm" disabled={busy !== null} onClick={() => setConfirmItem(item)} aria-label={`Löschung von ${itemName(item)} bestätigen`}>Löschung bestätigen</button>
          </div>
        </li>)}</ul>}
      </section>
      <section className="card card-pad stack-4" aria-labelledby="deletion-done-heading">
        <h2 id="deletion-done-heading">Gelöscht ({deleted.length})</h2>
        {deleted.length === 0 ? <EmptyState variant="calm" title="Keine gelöschten Verträge" /> : <ul className="deletion-list">{deleted.map((item) => <li key={item.contract_id}>
          <div><Signal tone="neutral" size="sm">Gelöscht</Signal> {itemName(item)}<span className="cw-muted">{item.deleted_at ? ` · am ${formatDateTime(item.deleted_at)}` : ""}{item.by_name ? ` von ${item.by_name}` : ""}</span></div>
          <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={() => void act(item.contract_id, "restore")} aria-label={`${itemName(item)} wiederherstellen`}>Wiederherstellen</button>
        </li>)}</ul>}
      </section>
      {offset > 0 || queue.has_more ? <div className="rg-actions">
        <button type="button" className="btn btn-sm" disabled={checking || pageLoading || busy !== null || offset === 0} onClick={() => void changePage(Math.max(0, offset - 100))}>Zurück</button>
        <button type="button" className="btn btn-sm" disabled={checking || pageLoading || busy !== null || !queue.has_more || queue.next_offset === null} onClick={() => { if (queue.next_offset !== null) void changePage(queue.next_offset); }}>Weitere anzeigen</button>
      </div> : null}
    </> : null}
    <Dialog
      open={confirmItem !== null}
      title="Löschung bestätigen?"
      onClose={() => setConfirmItem(null)}
      description={confirmItem ? <>„{itemName(confirmItem)}“ verschwindet aus Vertragsliste, Fristen und Auswertungen. Er bleibt unter „Gelöscht“ wiederherstellbar.</> : null}
      actions={<><button type="button" className="btn" disabled={busy !== null} onClick={() => setConfirmItem(null)}>Abbrechen</button><button type="button" className="btn btn-danger" disabled={busy !== null} onClick={() => { if (confirmItem) void act(confirmItem.contract_id, "confirm"); }}>Ja, löschen</button></>}
    />
  </div>;
}
