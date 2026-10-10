"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { useToast } from "@/components/ui/Toast";
import { linkSupplierToPartner, listUnlinkedSuppliers, type PartnerDto, type UnlinkedSupplier } from "@/lib/domain-api/catalogs";
import { QuickCreatePartner } from "./lazy";
import type { ManagerApi } from "./types";

function count(value: number) {
  return `${value} ${value === 1 ? "Vertrag" : "Verträge"}`;
}

function Row({ item, organizationSlug, onDone }: { item: UnlinkedSupplier; organizationSlug: string; onDone: (message: string) => void }) {
  const [partnerId, setPartnerId] = useState(item.suggestions[0]?.id ?? "");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function link(id: string, label: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await linkSupplierToPartner(organizationSlug, item.supplier, id);
      onDone(`${count(result.linked)} mit „${label}“ verknüpft.`);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Verknüpfen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  const chosen = item.suggestions.find((suggestion) => suggestion.id === partnerId);
  return <li className="md-supplier">
    <div className="md-supplier-head"><strong>„{item.supplier}“</strong><span className="field-hint">{count(item.contracts)} ohne verknüpften Vertragspartner</span></div>
    {item.suggestions.length > 0 ? <label className="md-supplier-choice">Vorschlag
      <select value={partnerId} disabled={busy} onChange={(event) => setPartnerId(event.target.value)}>
        {item.suggestions.map((suggestion) => <option key={suggestion.id} value={suggestion.id}>{suggestion.short_name} – {suggestion.display_name ?? suggestion.name1} ({Math.round((suggestion.score ?? 0) * 100)} % ähnlich)</option>)}
      </select>
    </label> : <span className="field-hint">Kein ähnlicher Vertragspartner gefunden.</span>}
    <span className="btn-group">
      {chosen ? <Button size="sm" variant="primary" loading={busy} onClick={() => void link(chosen.id, chosen.short_name)}>Zuordnen</Button> : null}
      <Button size="sm" disabled={busy} onClick={() => setCreating(true)}>Neu anlegen</Button>
    </span>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {creating ? <QuickCreatePartner
      organizationSlug={organizationSlug}
      open={creating}
      preset={{ short_name: item.supplier.slice(0, 60), name1: item.supplier }}
      onClose={() => setCreating(false)}
      onCreated={({ id, label }) => { setCreating(false); void link(id, label); }}
    /> : null}
  </li>;
}

// „Lieferanten zuordnen“ (U8): Lieferantennamen aus Verträgen ohne Vertragspartner, gruppiert.
// Nur Vorschläge – zugeordnet wird erst auf Klick, nichts wird automatisch zusammengeführt.
export default function SupplierWorklist({ organizationSlug, api }: { organizationSlug: string; api: ManagerApi<PartnerDto> }) {
  const toast = useToast();
  const [items, setItems] = useState<UnlinkedSupplier[] | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    listUnlinkedSuppliers(organizationSlug)
      .then((data) => { setItems(data.items); setFailed(false); })
      .catch(() => { setItems(null); setFailed(true); });
  }, [organizationSlug]);

  useEffect(load, [load]);

  if (!api.canEdit) return null;
  if (failed) return <InlineAlert tone="warning" action={<Button size="sm" onClick={load}>Erneut laden</Button>}>Die Liste „Lieferanten zuordnen“ konnte nicht geladen werden.</InlineAlert>;
  if (!items || items.length === 0) return null;
  const total = items.reduce((sum, item) => sum + item.contracts, 0);
  return <details className="md-duplicates md-suppliers" open>
    <summary>Lieferanten zuordnen – {count(total)} mit {items.length === 1 ? "1 Lieferantennamen" : `${items.length} Lieferantennamen`} ohne Vertragspartner</summary>
    <p className="field-hint">Die KI liest den Lieferanten als Text. Ordnen Sie ihn einmal einem Vertragspartner zu – alle Verträge mit genau diesem Namen werden verknüpft (Herkunft „manuell“, im Verlauf jedes Vertrags sichtbar).</p>
    <ul>{items.map((item) => <Row key={item.supplier} item={item} organizationSlug={organizationSlug} onDone={(message) => { toast(message, "success"); load(); void api.reload(); }} />)}</ul>
  </details>;
}
