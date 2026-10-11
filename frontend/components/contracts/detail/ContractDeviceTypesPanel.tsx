"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  getContractDeviceTypes,
  listDeviceTypes,
  saveContractDeviceTypes,
  type ContractDeviceTypes,
  type DeviceTypeDto,
} from "@/lib/domain-api/deviceTypes";

type Draft = { device_type_id: string; quantity: string; note: string };

function toDraft(data: ContractDeviceTypes): Draft[] {
  return data.items.map((item) => ({ device_type_id: item.device_type_id, quantity: item.quantity ? String(item.quantity) : "", note: item.note ?? "" }));
}

/**
 * Gerätearten des Vertrags (z. B. CT × 2) – Grundlage für Filter und Vergleich unter Analysen.
 * Vorschläge aus im Dokument gefundenen Geräten übernimmt nur eine Person.
 */
export default function ContractDeviceTypesPanel({ contractId, orgSlug, canEdit, responsibleDepartment, onSaved }: {
  contractId: string;
  orgSlug: string;
  canEdit: boolean;
  /** Name der verantwortlichen Abteilung: ihre Gerätearten stehen in der Auswahl zuerst. */
  responsibleDepartment?: string | null;
  onSaved?: () => void;
}) {
  const toast = useToast();
  const [catalog, setCatalog] = useState<DeviceTypeDto[]>([]);
  const [data, setData] = useState<ContractDeviceTypes | null>(null);
  const [draft, setDraft] = useState<Draft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getContractDeviceTypes(orgSlug, contractId), listDeviceTypes(orgSlug)])
      .then(([response, types]) => {
        if (cancelled) return;
        // Unerwartete Antwort nie als Absturz der ganzen Vertragsakte: dann leer.
        const current: ContractDeviceTypes = {
          items: Array.isArray(response?.items) ? response.items : [],
          suggestions: Array.isArray(response?.suggestions) ? response.suggestions : [],
        };
        setData(current);
        setDraft(toDraft(current));
        setCatalog(Array.isArray(types?.items) ? types.items : []);
      })
      .catch(() => { if (!cancelled) setError("Gerätearten konnten nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [contractId, orgSlug]);

  const byId = useMemo(() => new Map(catalog.map((item) => [item.id, item])), [catalog]);
  const dirty = data !== null && JSON.stringify(toDraft(data)) !== JSON.stringify(draft);
  const chosen = new Set(draft.map((item) => item.device_type_id));
  const available = catalog.filter((item) => item.is_active && !chosen.has(item.id));
  const own = available.filter((item) => responsibleDepartment && item.department_name === responsibleDepartment);
  const areas = Array.from(new Set(available.map((item) => item.area_label)));

  function update(index: number, patch: Partial<Draft>) {
    setDraft((current) => current.map((item, position) => (position === index ? { ...item, ...patch } : item)));
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const saved = await saveContractDeviceTypes(orgSlug, contractId, draft.map((item) => ({
        device_type_id: item.device_type_id,
        quantity: item.quantity.trim() ? Number(item.quantity) : null,
        note: item.note.trim() || null,
      })));
      setData(saved);
      setDraft(toDraft(saved));
      toast("Gerätearten gespeichert.", "success");
      onSaved?.();
    } catch (caught) {
      setError(caught instanceof ApiError && caught.message ? caught.message : "Gerätearten konnten nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  if (data === null) return error ? <p role="alert" className="rg-error">{error}</p> : <p role="status">Gerätearten werden geladen…</p>;

  return <div className="device-types">
    {draft.length === 0
      ? <p className="cw-muted">Noch keine Geräteart zugeordnet. Mit Geräteart lässt sich der Vertrag filtern und unter Analysen mit gleichartigen Verträgen vergleichen.</p>
      : <ul className="device-type-list" aria-label="Gerätearten des Vertrags">{draft.map((item, index) => {
        const kind = byId.get(item.device_type_id);
        const name = kind?.label ?? data.items.find((entry) => entry.device_type_id === item.device_type_id)?.label ?? "Geräteart";
        return <li key={item.device_type_id}>
          <span className="device-type-name"><strong>{name}</strong>{kind ? <small>{kind.area_label}</small> : null}</span>
          {canEdit ? <>
            <label className="device-type-qty">Anzahl<input type="number" inputMode="numeric" min={1} max={100000} value={item.quantity} onChange={(event) => update(index, { quantity: event.target.value })} aria-label={`Anzahl ${name}`} placeholder="unbekannt" /></label>
            <label className="device-type-note">Notiz<input value={item.note} maxLength={255} onChange={(event) => update(index, { note: event.target.value })} aria-label={`Notiz ${name}`} placeholder="z. B. Standort, Modell" /></label>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft((current) => current.filter((_, position) => position !== index))} aria-label={`${name} entfernen`}>Entfernen</button>
          </> : <span>{item.quantity ? `${item.quantity} Gerät${item.quantity === "1" ? "" : "e"}` : "Anzahl unbekannt"}{item.note ? ` · ${item.note}` : ""}</span>}
        </li>;
      })}</ul>}

    {canEdit && data.suggestions.filter((item) => !chosen.has(item.device_type_id)).length ? <ul className="device-type-suggestions" aria-label="Vorschläge aus dem Dokument">
      {data.suggestions.filter((item) => !chosen.has(item.device_type_id)).map((item) => <li key={item.device_type_id}>
        <Signal tone="ai" size="sm">Vorschlag</Signal> <strong>{item.label}</strong> <span className="cw-muted">({item.reason})</span>
        <button type="button" className="btn btn-sm" onClick={() => setDraft((current) => [...current, { device_type_id: item.device_type_id, quantity: "", note: "" }])}>Übernehmen</button>
      </li>)}
    </ul> : null}

    {canEdit ? <div className="device-type-actions">
      {available.length ? <select aria-label="Geräteart hinzufügen" value="" onChange={(event) => { const id = event.target.value; if (id) setDraft((current) => [...current, { device_type_id: id, quantity: "", note: "" }]); }}>
        <option value="">+ Geräteart hinzufügen …</option>
        {own.length ? <optgroup label={`Abteilung ${responsibleDepartment}`}>{own.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup> : null}
        {areas.map((area) => <optgroup key={area} label={area}>{available.filter((item) => item.area_label === area && !own.includes(item)).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup>)}
      </select> : null}
      <Link className="rg-link" href="/stammdaten/geraetearten">Gerätearten pflegen</Link>
      {dirty ? <span className="device-type-save">
        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => setDraft(toDraft(data))}>Abbrechen</button>
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void save()}>{busy ? "Wird gespeichert…" : "Speichern"}</button>
      </span> : null}
    </div> : null}
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
  </div>;
}
