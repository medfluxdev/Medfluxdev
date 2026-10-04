"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { ApiError } from "@/lib/api";
import {
  createPartner,
  findSimilarPartners,
  listPartnerDuplicates,
  listPartners,
  updatePartner,
  type PartnerDto,
  type PartnerValues,
} from "@/lib/domain-api/catalogs";

const FIELDS: { key: keyof PartnerValues; label: string; required?: boolean }[] = [
  { key: "short_name", label: "Kurzname", required: true },
  { key: "name1", label: "Name", required: true },
  { key: "name2", label: "Namenszusatz" },
  { key: "street", label: "Straße" },
  { key: "postal_code", label: "PLZ" },
  { key: "city", label: "Ort" },
  { key: "country", label: "Land" },
  { key: "phone", label: "Telefon" },
  { key: "email", label: "E-Mail" },
  { key: "website", label: "Internet" },
  { key: "vat_id", label: "USt-IdNr." },
  { key: "note", label: "Notiz" },
];

type FormState = Record<string, string>;

function toForm(partner?: PartnerDto): FormState {
  const form: FormState = {};
  for (const field of FIELDS) form[field.key] = partner ? String(partner[field.key] ?? "") : "";
  return form;
}

function toValues(form: FormState): PartnerValues {
  const values: Record<string, string | null> = {};
  for (const field of FIELDS) values[field.key] = form[field.key].trim() || null;
  return values as PartnerValues;
}

export default function PartnerManager({ organizationSlug }: { organizationSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PartnerDto[]>([]);
  const [total, setTotal] = useState(0);
  const [duplicates, setDuplicates] = useState<PartnerDto[][]>([]);
  const [editing, setEditing] = useState<{ id: string | null; form: FormState } | null>(null);
  const [similar, setSimilar] = useState<PartnerDto[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);

  const load = useCallback(async () => {
    try {
      const [list, dupes] = await Promise.all([
        listPartners(organizationSlug, { q: query.trim() || undefined, includeInactive, limit: 200 }),
        listPartnerDuplicates(organizationSlug),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setDuplicates(dupes.groups);
    } catch {
      setMessage("Vertragspartner konnten nicht geladen werden.");
    }
  }, [includeInactive, organizationSlug, query]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function save(allowSimilar = false) {
    if (!editing) return;
    setBusy(true);
    setMessage(null);
    try {
      if (editing.id) await updatePartner(organizationSlug, editing.id, toValues(editing.form));
      else await createPartner(organizationSlug, toValues(editing.form), allowSimilar);
      setEditing(null);
      setSimilar([]);
      setMessage("Vertragspartner gespeichert.");
      await load();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && !editing.id && !allowSimilar) {
        const name = editing.form.name1 || editing.form.short_name;
        const found = await findSimilarPartners(organizationSlug, name).catch(() => ({ items: [] as PartnerDto[] }));
        setSimilar(found.items);
      }
      setMessage(error instanceof Error ? error.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(partner: PartnerDto) {
    setBusy(true);
    try {
      await updatePartner(organizationSlug, partner.id, { is_active: !partner.is_active } as PartnerValues);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Änderung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="rg-panel">
    <section className="cw-section">
      <div className="rg-toolbar">
        <label className="rg-form-grid form-grid-single">Suchen<input type="search" value={query} placeholder="Kurzname, Name oder Ort" onChange={(event) => setQuery(event.target.value)} /></label>
        <label className="rg-check"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />Deaktivierte anzeigen</label>
        {editable ? <button type="button" className="btn btn-primary" onClick={() => { setEditing({ id: null, form: toForm() }); setSimilar([]); setMessage(null); }}>Vertragspartner anlegen</button> : null}
      </div>
      {message ? <p role="status" className="cw-muted">{message}</p> : null}
    </section>

    {editing ? <form className="cw-section" aria-label={editing.id ? "Vertragspartner bearbeiten" : "Vertragspartner anlegen"} onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <div className="cw-section-head"><div><h2>{editing.id ? "Vertragspartner bearbeiten" : "Neuer Vertragspartner"}</h2></div></div>
      <div className="rg-form-grid">
        {FIELDS.map((field) => <label key={field.key}>{field.label}{field.required ? " *" : ""}<input required={field.required} value={editing.form[field.key]} onChange={(event) => setEditing((current) => current && ({ ...current, form: { ...current.form, [field.key]: event.target.value } }))} /></label>)}
      </div>
      {similar.length > 0 ? <div className="rg-hint">
        <strong>Ähnliche Vertragspartner gefunden:</strong> {similar.map((item) => item.short_name).join(", ")}. Bitte prüfen, ob der Partner bereits existiert.
        <div className="rg-actions"><button type="button" className="btn" disabled={busy} onClick={() => void save(true)}>Trotzdem anlegen</button></div>
      </div> : null}
      <div className="rg-actions mt-3">
        <button type="button" className="btn" onClick={() => { setEditing(null); setSimilar([]); }}>Abbrechen</button>
        <button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button>
      </div>
    </form> : null}

    {duplicates.length > 0 ? <section className="cw-section" aria-labelledby="rg-duplicates-heading">
      <div className="cw-section-head"><div><h2 id="rg-duplicates-heading">Mögliche Dubletten</h2><p>Sehr ähnliche Namen. Doppelte Einträge bitte deaktivieren und Verträge dem verbleibenden Partner zuordnen.</p></div></div>
      <ul>{duplicates.map((group) => <li key={group.map((item) => item.id).join("-")}>{group.map((item) => `${item.short_name} (${item.name1})`).join(" ↔ ")}</li>)}</ul>
    </section> : null}

    <section className="cw-section" aria-labelledby="rg-partners-heading">
      <div className="cw-section-head"><div><h2 id="rg-partners-heading">Vertragspartner</h2><p>{total} Einträge</p></div></div>
      {items.length === 0 ? <p className="cw-muted">Keine Vertragspartner gefunden.</p> : <div className="table-scroll"><table className="rg-table">
        <thead><tr><th scope="col">Kurzname</th><th scope="col">Name</th><th scope="col">Ort</th><th scope="col">Kontakt</th><th scope="col">Verträge</th>{editable ? <th scope="col"><span className="sr-only">Aktionen</span></th> : null}</tr></thead>
        <tbody>{items.map((item) => <tr key={item.id} className={item.is_active ? undefined : "rg-inactive"}>
          <th scope="row">{item.short_name}</th>
          <td>{item.display_name}</td>
          <td>{[item.postal_code, item.city].filter(Boolean).join(" ") || "–"}</td>
          <td>{[item.phone, item.email].filter(Boolean).join(" · ") || "–"}</td>
          <td>{item.contract_count ?? 0}</td>
          {editable ? <td><span className="rg-actions"><button type="button" className="rg-link" onClick={() => { setEditing({ id: item.id, form: toForm(item) }); setSimilar([]); }}>Bearbeiten</button><button type="button" className="rg-link" disabled={busy} onClick={() => void toggleActive(item)}>{item.is_active ? "Deaktivieren" : "Aktivieren"}</button></span></td> : null}
        </tr>)}</tbody>
      </table></div>}
    </section>
  </div>;
}
