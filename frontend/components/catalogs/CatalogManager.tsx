"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  LOOKUP_FIELD_LABEL,
  createContractCategory,
  createContractType,
  createLookup,
  getNumberRange,
  listContractTypes,
  listLookups,
  loadDefaultCatalogs,
  reserveNumbers,
  updateContractCategory,
  updateContractType,
  updateLookup,
  updateNumberRange,
  type ContractCategoryDto,
  type ContractTypeDto,
  type LookupDto,
  type NumberRangeDto,
} from "@/lib/domain-api/catalogs";

type Tab = "types" | "categories" | "lookups" | "numbers";

const TABS: { key: Tab; label: string }[] = [
  { key: "types", label: "Vertragstypen" },
  { key: "categories", label: "Kategorien" },
  { key: "lookups", label: "Auswahllisten" },
  { key: "numbers", label: "Nummernkreis" },
];

function errorText(error: unknown) {
  return error instanceof Error && error.message ? error.message : "Die Änderung konnte nicht gespeichert werden.";
}

export default function CatalogManager({ organizationSlug }: { organizationSlug: string }) {
  const [tab, setTab] = useState<Tab>("types");
  const [types, setTypes] = useState<ContractTypeDto[]>([]);
  const [categories, setCategories] = useState<ContractCategoryDto[]>([]);
  const [lookups, setLookups] = useState<LookupDto[]>([]);
  const [fieldKeys, setFieldKeys] = useState<string[]>([]);
  const [fieldKey, setFieldKey] = useState("storage_location");
  const [range, setRange] = useState<NumberRangeDto | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newConfidential, setNewConfidential] = useState(false);
  const [newTypeIds, setNewTypeIds] = useState<string[]>([]);
  const [rangeForm, setRangeForm] = useState({ prefix: "", padding: "6", next_value: "" });
  const [reserveText, setReserveText] = useState("");

  const load = useCallback(async () => {
    try {
      const [catalog, lookupData, numberRange] = await Promise.all([
        listContractTypes(organizationSlug),
        listLookups(organizationSlug, undefined, true),
        getNumberRange(organizationSlug),
      ]);
      setTypes(catalog.contract_types);
      setCategories(catalog.contract_categories);
      setLookups(lookupData.items);
      setFieldKeys(lookupData.field_keys);
      setRange(numberRange);
      setRangeForm({ prefix: numberRange.prefix, padding: String(numberRange.padding), next_value: String(numberRange.next_value) });
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error) });
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  const typeLabel = useMemo(() => new Map(types.map((item) => [item.id, item.label])), [types]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage({ tone: "ok", text: success });
      setNewLabel("");
      setNewConfidential(false);
      setNewTypeIds([]);
      await load();
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  function addEntry() {
    const label = newLabel.trim();
    if (!label) return;
    if (tab === "types") void run(() => createContractType(organizationSlug, { label, is_confidential: newConfidential }), "Vertragstyp angelegt.");
    if (tab === "categories") void run(() => createContractCategory(organizationSlug, { label, contract_type_ids: newTypeIds }), "Kategorie angelegt.");
    if (tab === "lookups") void run(() => createLookup(organizationSlug, { field_key: fieldKey, label }), "Eintrag angelegt.");
  }

  function toggleCategoryType(category: ContractCategoryDto, typeId: string) {
    const ids = category.contract_type_ids.includes(typeId)
      ? category.contract_type_ids.filter((id) => id !== typeId)
      : [...category.contract_type_ids, typeId];
    void run(() => updateContractCategory(organizationSlug, category.id, { contract_type_ids: ids }), "Zuordnung gespeichert.");
  }

  function saveRange() {
    const payload: { prefix?: string; padding?: number; next_value?: number } = { prefix: rangeForm.prefix, padding: Number(rangeForm.padding) };
    if (range && Number(rangeForm.next_value) !== range.next_value) payload.next_value = Number(rangeForm.next_value);
    void run(() => updateNumberRange(organizationSlug, payload), "Nummernkreis gespeichert.");
  }

  function reserve() {
    const values = reserveText.split(/[\s,;]+/).map((part) => Number(part)).filter((value) => Number.isInteger(value) && value > 0);
    if (values.length === 0) return;
    void run(() => reserveNumbers(organizationSlug, values), "Nummern reserviert.").then(() => setReserveText(""));
  }

  const lookupRows = lookups.filter((item) => item.field_key === fieldKey);

  return <div className="rg-panel">
    <div className="rg-tabs" role="tablist" aria-label="Kataloge">
      {TABS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={tab === item.key} className={tab === item.key ? "active" : ""} onClick={() => { setTab(item.key); setMessage(null); }}>{item.label}</button>)}
      <button type="button" disabled={busy} onClick={() => void run(() => loadDefaultCatalogs(organizationSlug), "Fehlende Standardeinträge ergänzt.")}>Standardkatalog ergänzen</button>
    </div>
    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

    {tab !== "numbers" ? <form className="cw-section" aria-label="Eintrag hinzufügen" onSubmit={(event) => { event.preventDefault(); addEntry(); }}>
      <div className="rg-form-grid">
        {tab === "lookups" ? <label>Auswahlliste<select value={fieldKey} onChange={(event) => setFieldKey(event.target.value)}>{fieldKeys.map((key) => <option key={key} value={key}>{LOOKUP_FIELD_LABEL[key] ?? key}</option>)}</select></label> : null}
        <label>Neue Bezeichnung<input value={newLabel} maxLength={160} onChange={(event) => setNewLabel(event.target.value)} /></label>
        {tab === "types" ? <label className="rg-check"><input type="checkbox" checked={newConfidential} onChange={(event) => setNewConfidential(event.target.checked)} />Vertraulich</label> : null}
        {tab === "categories" ? <label>Vertragstypen<select multiple value={newTypeIds} onChange={(event) => setNewTypeIds(Array.from(event.target.selectedOptions, (option) => option.value))}>{types.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label> : null}
        <button type="submit" className="btn btn-primary" disabled={busy || !newLabel.trim()}>Hinzufügen</button>
      </div>
    </form> : null}

    {tab === "types" ? <section className="cw-section"><table className="rg-table">
      <thead><tr><th scope="col">Bezeichnung</th><th scope="col">Code</th><th scope="col">Vertraulich</th><th scope="col">Aufbewahrung (Jahre nach Ende)</th><th scope="col">Status</th></tr></thead>
      <tbody>{types.map((item) => <tr key={item.id} className={item.is_active ? undefined : "rg-inactive"}>
        <th scope="row">{item.label}</th><td>{item.code}</td>
        <td><input type="checkbox" aria-label={`${item.label} vertraulich`} checked={item.is_confidential} disabled={busy} onChange={(event) => void run(() => updateContractType(organizationSlug, item.id, { is_confidential: event.target.checked }), "Gespeichert.")} /></td>
        <td><input type="number" min={0} max={100} className="rg-narrow" aria-label={`${item.label} Aufbewahrung in Jahren`} defaultValue={item.retention_years ?? ""} key={`${item.id}-${item.retention_years ?? ""}`} disabled={busy} onBlur={(event) => {
          const next = event.target.value === "" ? null : Number(event.target.value);
          if (next !== item.retention_years) void run(() => updateContractType(organizationSlug, item.id, { retention_years: next }), "Aufbewahrung gespeichert.");
        }} /></td>
        <td><button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => updateContractType(organizationSlug, item.id, { is_active: !item.is_active }), "Gespeichert.")}>{item.is_active ? "Deaktivieren" : "Aktivieren"}</button></td>
      </tr>)}</tbody>
    </table></section> : null}

    {tab === "categories" ? <section className="cw-section"><table className="rg-table">
      <thead><tr><th scope="col">Kategorie</th><th scope="col">Zugeordnete Vertragstypen</th><th scope="col">Status</th></tr></thead>
      <tbody>{categories.map((item) => <tr key={item.id} className={item.is_active ? undefined : "rg-inactive"}>
        <th scope="row">{item.label}</th>
        <td><details><summary>{item.contract_type_ids.map((id) => typeLabel.get(id)).filter(Boolean).join(", ") || "Keine"}</summary>
          <div className="rg-period">{types.filter((type) => type.is_active).map((type) => <label key={type.id} className="rg-check"><input type="checkbox" checked={item.contract_type_ids.includes(type.id)} disabled={busy} onChange={() => toggleCategoryType(item, type.id)} />{type.label}</label>)}</div>
        </details></td>
        <td><button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => updateContractCategory(organizationSlug, item.id, { is_active: !item.is_active }), "Gespeichert.")}>{item.is_active ? "Deaktivieren" : "Aktivieren"}</button></td>
      </tr>)}</tbody>
    </table></section> : null}

    {tab === "lookups" ? <section className="cw-section"><table className="rg-table">
      <thead><tr><th scope="col">{LOOKUP_FIELD_LABEL[fieldKey] ?? fieldKey}</th><th scope="col">Beschreibung</th><th scope="col">Status</th></tr></thead>
      <tbody>{lookupRows.map((item) => <tr key={item.id} className={item.is_active ? undefined : "rg-inactive"}>
        <th scope="row">{item.label}</th><td>{item.description ?? "–"}</td>
        <td><button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => updateLookup(organizationSlug, item.id, { is_active: !item.is_active }), "Gespeichert.")}>{item.is_active ? "Deaktivieren" : "Aktivieren"}</button></td>
      </tr>)}</tbody>
    </table></section> : null}

    {tab === "numbers" && range ? <section className="cw-section" aria-labelledby="rg-numbers-heading">
      <div className="cw-section-head"><div><h2 id="rg-numbers-heading">Vertragsnummern</h2><p>Nächste Nummer: <strong>{range.next_formatted}</strong> · {range.used_count} vergeben · {range.reserved.length} reserviert</p></div></div>
      <form className="rg-form-grid" onSubmit={(event) => { event.preventDefault(); saveRange(); }}>
        <label>Präfix<input maxLength={16} value={rangeForm.prefix} onChange={(event) => setRangeForm((form) => ({ ...form, prefix: event.target.value }))} /></label>
        <label>Stellen<input type="number" min={1} max={12} value={rangeForm.padding} onChange={(event) => setRangeForm((form) => ({ ...form, padding: event.target.value }))} /></label>
        <label>Nächste Nummer<input type="number" min={1} value={rangeForm.next_value} onChange={(event) => setRangeForm((form) => ({ ...form, next_value: event.target.value }))} /></label>
        <button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button>
      </form>
      <form className="rg-form-grid mt-4" onSubmit={(event) => { event.preventDefault(); reserve(); }}>
        <label className="span-2">Nummern reservieren (z. B. „1, 21, 100“)<input value={reserveText} onChange={(event) => setReserveText(event.target.value)} /></label>
        <button type="submit" className="btn" disabled={busy || !reserveText.trim()}>Reservieren</button>
      </form>
      {range.reserved.length > 0 ? <p className="cw-muted">Reserviert: {range.reserved.map((item) => item.formatted).join(", ")}</p> : null}
    </section> : null}
  </div>;
}
