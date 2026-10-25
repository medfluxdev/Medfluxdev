"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AiOrigin from "@/components/ui/AiOrigin";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import ActionMenu from "@/components/ui/ActionMenu";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  getContractDeviceTypes,
  listDeviceTypes,
  saveContractDeviceTypes,
  type ContractDeviceTypes,
  type DeviceTypeDto,
} from "@/lib/domain-api/deviceTypes";
import { getOrganizationStructure } from "@/lib/domain-api/organizations";
import { getContractDepartmentRoles } from "@/lib/domain-api/ownership";
import { deviceTypeGroups, type ContractDepartmentContext } from "@/lib/device-type-match";
import { departmentFullPath } from "@/lib/organization-tree";

type Draft = { device_type_id: string; quantity: string; note: string };

const svg = (body: JSX.Element) => <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const MONITOR_ICON = svg(<path d="M4 4h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM8 20h8M12 16v4" />);
const PLUS_ICON = svg(<path d="M12 5v14M5 12h14" />);
const PEN_ICON = svg(<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" />);
const INFO_ICON = svg(<path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 11v6M12 7.5v.5" />);
const TRASH_ICON = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>;

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
  /** Name der verantwortlichen Abteilung – Rückfall, falls die Abteilungen des Vertrags nicht ladbar sind. */
  responsibleDepartment?: string | null;
  onSaved?: () => void;
}) {
  const toast = useToast();
  const [catalog, setCatalog] = useState<DeviceTypeDto[]>([]);
  const [data, setData] = useState<ContractDeviceTypes | null>(null);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [adding, setAdding] = useState(false);
  const [newRow, setNewRow] = useState<Draft>({ device_type_id: "", quantity: "", note: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [contextDepartments, setContextDepartments] = useState<ContractDepartmentContext[] | null>(null);

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
        setCatalog(Array.isArray(types?.items) ? types.items : []);
      })
      .catch(() => { if (!cancelled) setError("Gerätearten konnten nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [contractId, orgSlug]);

  // Verantwortliche und nutzende Abteilungen (mit übergeordneten) – gleiche Regel wie in der Organisationszuordnung.
  useEffect(() => {
    if (!canEdit) return;
    let cancelled = false;
    Promise.all([getContractDepartmentRoles(orgSlug, contractId), getOrganizationStructure(orgSlug)])
      .then(([roles, structure]) => {
        if (cancelled) return;
        const all = structure?.departments ?? [];
        const ids = [roles?.responsible_department_id, ...(roles?.beneficiary_department_ids ?? [])].filter(Boolean);
        setContextDepartments(all.filter((item) => ids.includes(item.id)).map((item) => ({ id: item.id, path: departmentFullPath(item, all) })));
      })
      .catch(() => { if (!cancelled) setContextDepartments(null); });
    return () => { cancelled = true; };
  }, [canEdit, contractId, orgSlug]);

  const byId = useMemo(() => new Map(catalog.map((item) => [item.id, item])), [catalog]);
  const rows = data?.items ?? [];
  const chosen = new Set(rows.map((item) => item.device_type_id));
  const groups = deviceTypeGroups(catalog, chosen, contextDepartments ?? (responsibleDepartment ? [{ id: null, path: responsibleDepartment }] : []));
  const openSuggestions = (data?.suggestions ?? []).filter((item) => !chosen.has(item.device_type_id));

  /** Jede Änderung speichert sofort die ganze Zuordnung (Hinzufügen, Bearbeiten, Entfernen). */
  async function persist(next: Draft[], success: string) {
    setBusy(true);
    setError(null);
    try {
      const saved = await saveContractDeviceTypes(orgSlug, contractId, next.map((item) => ({
        device_type_id: item.device_type_id,
        quantity: item.quantity.trim() ? Number(item.quantity) : null,
        note: item.note.trim() || null,
      })));
      setData(saved);
      setEditing(null);
      setAdding(false);
      toast(success, "success");
      onSaved?.();
      return true;
    } catch (caught) {
      setError(caught instanceof ApiError && caught.message ? caught.message : "Gerätearten konnten nicht gespeichert werden.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const current = () => (data ? toDraft(data) : []);
  const nameOf = (id: string) => byId.get(id)?.label ?? rows.find((entry) => entry.device_type_id === id)?.label ?? "Geräteart";
  const add = (id: string) => void persist([...current(), { device_type_id: id, quantity: "", note: "" }], `„${nameOf(id)}“ zugeordnet.`);
  const remove = (id: string) => void persist(current().filter((item) => item.device_type_id !== id), `Zuordnung „${nameOf(id)}“ entfernt.`);
  const EMPTY_ROW: Draft = { device_type_id: "", quantity: "", note: "" };
  const closeAdd = () => { setAdding(false); setNewRow(EMPTY_ROW); };
  const addNew = () => {
    if (!newRow.device_type_id) return;
    void persist([...current(), newRow], `„${nameOf(newRow.device_type_id)}“ zugeordnet.`).then((ok) => { if (ok) setNewRow(EMPTY_ROW); });
  };
  const saveRow = () => editing && void persist(current().map((item) => (item.device_type_id === editing.device_type_id ? editing : item)), `„${nameOf(editing.device_type_id)}“ gespeichert.`);

  if (data === null) return error ? <p role="alert" className="rg-error">{error}</p> : <p role="status">Gerätearten werden geladen…</p>;

  return <CollapsibleSection id="contract-device-types" className="dt-card" title={`Gerätearten (${rows.length})`} icon={MONITOR_ICON} iconClassName="section-tile--device" description="Zuordnung für Filter und Vertragsvergleiche."
    actions={<div className="dt-head-actions">
      {canEdit && groups.length ? <button type="button" className="btn btn-primary" aria-expanded={adding} disabled={busy} onClick={() => (adding ? closeAdd() : setAdding(true))}>{PLUS_ICON}Geräteart hinzufügen</button> : null}
      <Link className="rg-link" href="/stammdaten/geraetearten">Gerätearten verwalten</Link>
    </div>}>
    <div className="rel-main">

      {adding ? <form className="dt-add" aria-label="Geräteart hinzufügen" onSubmit={(event) => { event.preventDefault(); addNew(); }}>
        {/* Alle Angaben auf einmal: Geräteart, Anzahl und Notiz, dann einmal speichern. */}
        <label>Geräteart<select aria-label="Geräteart" value={newRow.device_type_id} autoFocus disabled={busy} required onChange={(event) => setNewRow({ ...newRow, device_type_id: event.target.value })}>
          <option value="">Bitte auswählen …</option>
          {groups.map((group) => <optgroup key={group.label} label={group.label}>{group.items.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup>)}
        </select></label>
        <label>Anzahl<input type="number" inputMode="numeric" min={1} max={100000} value={newRow.quantity} disabled={busy} onChange={(event) => setNewRow({ ...newRow, quantity: event.target.value })} placeholder="unbekannt" /></label>
        <label className="dt-add-note">Notiz<input value={newRow.note} maxLength={255} disabled={busy} onChange={(event) => setNewRow({ ...newRow, note: event.target.value })} placeholder="z. B. Standort, Modell" /></label>
        <span className="dt-add-actions">
          <button type="button" className="btn btn-ghost" onClick={closeAdd}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !newRow.device_type_id}>{busy ? "Wird gespeichert…" : "Hinzufügen"}</button>
        </span>
      </form> : null}

      {canEdit && openSuggestions.length ? <ul className="device-type-suggestions" aria-label="Vorschläge aus dem Dokument">
        {openSuggestions.map((item) => <li key={item.device_type_id}>
          <AiOrigin state="unreviewed" factKey="equipment.identity" subject={item.label} detail={item.reason} /> <strong>{item.label}</strong> <span className="cw-muted">({item.reason})</span>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => add(item.device_type_id)}>Übernehmen</button>
        </li>)}
      </ul> : null}

      {rows.length === 0
        ? <p className="cw-muted">Noch keine Geräteart zugeordnet. Mit Geräteart lässt sich der Vertrag filtern und unter Analysen mit gleichartigen Verträgen vergleichen.</p>
        : <div className="table-scroll"><table className="rg-table dt-table" aria-label="Gerätearten des Vertrags">
          <thead><tr><th scope="col">Geräteart</th><th scope="col">Bereich</th><th scope="col">Anzahl</th><th scope="col">Notiz</th>{canEdit ? <th scope="col" className="dt-actions-col">Aktionen</th> : null}</tr></thead>
          <tbody>{rows.map((item) => {
            const name = nameOf(item.device_type_id);
            const area = byId.get(item.device_type_id)?.area_label ?? item.area_label ?? "–";
            const isEditing = editing?.device_type_id === item.device_type_id;
            return <tr key={item.device_type_id}>
              <th scope="row"><span className="dt-name">{MONITOR_ICON}{name}</span></th>
              <td className="cw-muted">{area}</td>
              <td>{isEditing && editing
                ? <input className="dt-input" type="number" inputMode="numeric" min={1} max={100000} value={editing.quantity} onChange={(event) => setEditing({ ...editing, quantity: event.target.value })} aria-label={`Anzahl ${name}`} placeholder="unbekannt" />
                : item.quantity ? `${item.quantity} ${item.quantity === 1 ? "Gerät" : "Geräte"}` : <span className="cw-muted">Nicht angegeben</span>}</td>
              <td>{isEditing && editing
                ? <input className="dt-input" value={editing.note} maxLength={255} onChange={(event) => setEditing({ ...editing, note: event.target.value })} aria-label={`Notiz ${name}`} placeholder="z. B. Standort, Modell" />
                : item.note ?? <span className="cw-muted">—</span>}</td>
              {canEdit ? <td className="dt-actions">{isEditing
                ? <><button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setEditing(null)}>Abbrechen</button><button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={saveRow}>{busy ? "Wird gespeichert…" : "Speichern"}</button></>
                : <><button type="button" className="rg-link dt-edit" disabled={busy || editing !== null} aria-label={`${name} bearbeiten`} onClick={() => setEditing({ device_type_id: item.device_type_id, quantity: item.quantity ? String(item.quantity) : "", note: item.note ?? "" })}>{PEN_ICON}Bearbeiten</button>
                  <ActionMenu label={`Weitere Aktionen: ${name}`} disabled={busy || editing !== null} items={[{ label: "Zuordnung entfernen", icon: TRASH_ICON, danger: true, onSelect: () => remove(item.device_type_id) }]} /></>}
              </td> : null}
            </tr>;
          })}</tbody>
        </table></div>}
      {rows.length && canEdit ? <p className="rel-info">{INFO_ICON}Anzahl und Notiz können je Zuordnung ergänzt werden. „Zuordnung entfernen“ lässt die Geräteart in den Stammdaten bestehen.</p> : null}
      {error ? <p role="alert" className="rg-error">{error}</p> : null}
    </div>
  </CollapsibleSection>;
}
