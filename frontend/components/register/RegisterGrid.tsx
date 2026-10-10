"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  createSavedView,
  deleteSavedView,
  downloadGridXlsx,
  getGrid,
  getGridColumns,
  listContractListViews,
  listSavedViews,
  saveBlob,
  updateSavedView,
  type GridColumn,
  type GridFilter,
  type GridResponse,
  type GridSpec,
  type ListViewDto,
  type MoneyTotals,
  type SavedViewDto,
  type TreeHospital,
} from "@/lib/domain-api/registerGrid";
import { unarchiveContract } from "@/lib/domain-api/contracts";
import { coverageNote, formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/components/ui/Toast";
import ContractQuickView from "./ContractQuickView";
import FilterEditor from "./FilterEditor";
import { describeFilter } from "./filters";

const PAGE_SIZE = 100;
const LAST_VIEW_KEY = "medflux.register.lastView";

type Spec = GridSpec;

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

// Standardansicht aus der Adresse (?ansicht=archive), z. B. aus dem Menü oder einer alten Seite.
function linkedViewKey(): string | null {
  try { return new URLSearchParams(window.location.search).get("ansicht"); } catch { return null; }
}

function writeViewKey(key: string | null) {
  try {
    const params = new URLSearchParams(window.location.search);
    if (key) params.set("ansicht", key); else params.delete("ansicht");
    const query = params.toString();
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  } catch {
    // Adresse ist nur Komfort.
  }
}

function readLastView(): string | null {
  try { return window.localStorage.getItem(LAST_VIEW_KEY); } catch { return null; }
}

function writeLastView(id: string | null) {
  try {
    if (id) window.localStorage.setItem(LAST_VIEW_KEY, id);
    else window.localStorage.removeItem(LAST_VIEW_KEY);
  } catch { /* nur Komfort */ }
}

function linkedQuery(): string | null {
  try {
    const q = new URLSearchParams(window.location.search).get("q");
    return q && q.trim() ? q.trim() : null;
  } catch {
    return null;
  }
}

const RISK_LABEL: Record<string, string> = { high: "Hoch", medium: "Mittel", low: "Niedrig" };

// Ansichten der frueheren Vertragsliste in Register-Filter uebersetzen.
export function legacyQueryToSpec(query: string): Partial<GridSpec> {
  const params = new URLSearchParams(query);
  const filters: GridFilter[] = [];
  const risks = params.getAll("risk").map((value) => RISK_LABEL[value]).filter(Boolean);
  if (risks.length) filters.push({ column: "risk", op: "in", value: risks });
  if (params.get("requires_review") === "true") filters.push({ column: "review_pending", op: "is", value: true });
  if (params.get("automatic_renewal") === "true") filters.push({ column: "term_model", op: "in", value: ["Automatische Verlängerung"] });
  if (params.get("critical_cancellation") === "true") filters.push({ column: "cancel_by", op: "within_days", value: 90 });
  if (params.get("supplier")) filters.push({ column: "partner", op: "contains", value: params.get("supplier") });
  const q = params.get("q") ?? params.get("contract_number");
  return { filters, q: q || null };
}

function linkedFilters(): GridFilter[] | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("filter");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as GridFilter[]) : null;
  } catch {
    return null;
  }
}

// Summe mit Abdeckung: unbekannt bleibt „—“, Teilsummen sind gekennzeichnet.
function sumText(totals: MoneyTotals | undefined, key: string): string {
  if (!totals) return "—";
  const value = totals.sums[key];
  const coverage = totals.coverage?.[key];
  const others = Object.entries(totals.other_currencies?.[key] ?? {}).map(([code, amount]) => ` + ${formatCurrency(amount, code)}`).join("");
  if (value === null || value === undefined) return others ? others.slice(3) : "— (keine gepflegten Kosten)";
  const note = coverageNote(coverage?.known, coverage?.missing);
  return `${formatCurrency(value, totals.currency ?? "EUR")}${others}${note ? ` (${note})` : ""}`;
}

function formatCell(column: GridColumn | undefined, value: unknown): string {
  if (value == null || value === "") return "–";
  switch (column?.type) {
    case "date": return formatDate(String(value));
    case "money": return formatCurrency(String(value), "EUR");
    case "bool": return value ? "Ja" : "Nein";
    default: return String(value);
  }
}

export default function RegisterGrid({ organizationSlug, initialViewKey }: { organizationSlug: string; /** Standardansicht dieser Seite (z. B. "review" unter /review). */ initialViewKey?: string }) {
  const { role, account } = useAuth();
  const canExport = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [columns, setColumns] = useState<GridColumn[]>([]);
  const [views, setViews] = useState<SavedViewDto[]>([]);
  const [canManageGlobal, setCanManageGlobal] = useState(false);
  const [viewId, setViewId] = useState<string | null>(null);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<GridResponse | null>(null);
  const [tree, setTree] = useState<TreeHospital[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "ok"; text: string } | null>(null);
  const [addingFilter, setAddingFilter] = useState(false);
  const [search, setSearch] = useState("");
  const [saveForm, setSaveForm] = useState<{ name: string; is_global: boolean } | null>(null);
  const [legacyViews, setLegacyViews] = useState<ListViewDto[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [busyRow, setBusyRow] = useState<string | null>(null);
  // Auf dem Telefon eingeklappt, damit die Verträge sofort sichtbar sind.
  const [treeOpen, setTreeOpen] = useState(true);
  useEffect(() => {
    try { if (window.matchMedia("(max-width: 900px)").matches) setTreeOpen(false); } catch { /* ohne matchMedia bleibt er offen */ }
  }, []);
  // Seiten mit fester Ansicht (Archiv, Prüfungen) überschreiben die zuletzt genutzte Ansicht der Vertragsliste nicht.
  const presetPage = useRef(Boolean(initialViewKey));
  const toast = useToast();

  const columnByKey = useMemo(() => new Map(columns.map((item) => [item.key, item])), [columns]);
  const view = views.find((item) => item.id === viewId) ?? null;

  const applyView = useCallback((next: SavedViewDto | null, defaults: GridColumn[]) => {
    const base: Spec = { columns: defaults.filter((item) => item.default).map((item) => item.key), filters: [], sort: null, group_by: [], q: null, include_deleted: false, archived: false };
    const config = next ? { ...base, ...next.config } : base;
    setViewId(next?.id ?? null);
    setSpec(config);
    setSearch(config.q ?? "");
    setOffset(0);
    if (presetPage.current) return;
    writeLastView(next?.id ?? null);
    writeViewKey(next?.system_key ?? null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    listContractListViews(organizationSlug)
      .then((result) => { if (!cancelled) setLegacyViews(result.items); })
      .catch(() => undefined);
    Promise.all([getGridColumns(organizationSlug), listSavedViews(organizationSlug)])
      .then(([columnResult, viewResult]) => {
        if (cancelled) return;
        setColumns(columnResult.columns);
        setViews(viewResult.items);
        setCanManageGlobal(viewResult.can_manage_global);
        const linked = linkedFilters();
        const linkedQ = linkedQuery();
        if (linked || linkedQ) {
          applyView(null, columnResult.columns);
          setSpec((current) => current && ({ ...current, filters: linked ?? [], q: linkedQ }));
          setSearch(linkedQ ?? "");
          return;
        }
        const key = linkedViewKey() ?? initialViewKey ?? null;
        const keyed = key ? viewResult.items.find((item) => item.system_key === key) : undefined;
        if (keyed) {
          applyView(keyed, columnResult.columns);
          return;
        }
        const remembered = readLastView();
        applyView(viewResult.items.find((item) => item.id === remembered) ?? null, columnResult.columns);
      })
      .catch((error) => { if (!cancelled) setMessage({ tone: "error", text: errorText(error, "Das Vertragsregister konnte nicht geladen werden.") }); });
    return () => { cancelled = true; };
  }, [applyView, initialViewKey, organizationSlug]);

  useEffect(() => {
    if (!spec) return;
    let cancelled = false;
    setLoading(true);
    getGrid(organizationSlug, spec, { offset, limit: PAGE_SIZE, includeTree: true })
      .then((grid) => {
        if (cancelled) return;
        setData(grid);
        setTree(grid.tree ?? []);
      })
      .catch((error) => { if (!cancelled) setMessage({ tone: "error", text: errorText(error, "Die Liste konnte nicht geladen werden.") }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [offset, organizationSlug, spec]);

  useEffect(() => {
    if (!spec) return;
    const handle = window.setTimeout(() => {
      const q = search.trim() || null;
      if (q !== spec.q) { setSpec({ ...spec, q }); setOffset(0); }
    }, 300);
    return () => window.clearTimeout(handle);
  }, [search, spec]);

  function update(patch: Partial<Spec>) {
    if (!spec) return;
    setSpec({ ...spec, ...patch });
    setOffset(0);
  }

  function toggleColumn(key: string) {
    if (!spec) return;
    update({ columns: spec.columns.includes(key) ? spec.columns.filter((item) => item !== key) : [...spec.columns, key] });
  }

  function sortBy(key: string) {
    if (!spec) return;
    const dir = spec.sort?.column === key && spec.sort.dir === "asc" ? "desc" : "asc";
    update({ sort: { column: key, dir } });
  }

  function setGroup(level: 0 | 1, key: string) {
    if (!spec) return;
    const next = [...spec.group_by];
    if (key) next[level] = key; else next.splice(level, next.length);
    update({ group_by: next.filter(Boolean).filter((item, index, all) => all.indexOf(item) === index) });
  }

  function pickTree(hospital: string | null, department?: string | null) {
    if (!spec) return;
    const rest = spec.filters.filter((item) => item.column !== "hospital" && item.column !== "department");
    const added: GridFilter[] = [{ column: "hospital", op: "in", value: [hospital ?? ""] }];
    if (department !== undefined) added.push({ column: "department", op: "in", value: [department ?? ""] });
    update({ filters: [...rest, ...added] });
  }

  async function exportXlsx() {
    if (!spec) return;
    try {
      const { blob, filename } = await downloadGridXlsx(organizationSlug, spec, view?.name ?? "Vertragsregister");
      saveBlob(blob, filename ?? "vertragsregister.xlsx");
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Export fehlgeschlagen.") });
    }
  }

  async function saveView(asNew: boolean) {
    if (!spec) return;
    try {
      if (!asNew && view) {
        const saved = await updateSavedView(organizationSlug, view.id, { name: view.name, config: spec });
        setViews((current) => current.map((item) => (item.id === saved.id ? saved : item)));
        setMessage({ tone: "ok", text: `Ansicht „${saved.name}“ gespeichert.` });
        return;
      }
      if (!saveForm?.name.trim()) return;
      const saved = await createSavedView(organizationSlug, { name: saveForm.name.trim(), config: spec, is_global: saveForm.is_global });
      setViews((current) => [...current, saved]);
      setViewId(saved.id);
      writeLastView(saved.id);
      setSaveForm(null);
      setMessage({ tone: "ok", text: `Ansicht „${saved.name}“ angelegt.` });
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Ansicht konnte nicht gespeichert werden.") });
    }
  }

  async function removeView() {
    if (!view) return;
    try {
      await deleteSavedView(organizationSlug, view.id);
      setViews((current) => current.filter((item) => item.id !== view.id));
      applyView(null, columns);
      setMessage({ tone: "ok", text: "Ansicht gelöscht." });
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Ansicht konnte nicht gelöscht werden.") });
    }
  }

  if (!spec) {
    return message ? <p role="alert" className="rg-error">{message.text}</p> : <p role="status">Vertragsregister wird geladen…</p>;
  }

  const shown = [...spec.group_by.filter((key) => !spec.columns.includes(key)), ...spec.columns].map((key) => columnByKey.get(key)).filter((item): item is GridColumn => Boolean(item));
  const groupable = columns.filter((item) => item.groupable);
  const editableView = view && (view.is_own || (view.is_global && canManageGlobal));
  const groupIndex = new Map((data?.groups ?? []).map((item) => [JSON.stringify(item.path), item]));
  const total = data?.total ?? 0;

  let previous: (string | number | boolean | null)[] | null = null;
  const archiveMode = Boolean(spec.archived);
  const reviewMode = spec.filters.some((item) => item.column === "review_pending" && item.op === "is" && item.value === true);
  const actionColumn = (archiveMode && canExport) || reviewMode;

  async function restore(contractId: string) {
    if (!spec) return;
    setBusyRow(contractId);
    try {
      await unarchiveContract(contractId, organizationSlug);
      toast("Vertrag wieder ins aktive Portfolio verschoben.", "success");
      setSpec({ ...spec });
    } catch (error) {
      toast(errorText(error, "Wiederherstellung fehlgeschlagen."), "error");
    } finally {
      setBusyRow(null);
    }
  }

  return <div className="reg-layout">
    <nav className="cw-section reg-tree" aria-label="Verträge nach Gesellschaft und Abteilung">
      <details open={treeOpen} onToggle={(event) => setTreeOpen((event.target as HTMLDetailsElement).open)}>
      <summary><h2>Gesellschaft → Abteilung</h2></summary>
      <ul>
        <li><button type="button" className="rg-link" onClick={() => update({ filters: spec.filters.filter((item) => item.column !== "hospital" && item.column !== "department") })}>Alle</button></li>
        {tree.map((hospital) => <li key={hospital.label}>
          <button type="button" className="rg-link" onClick={() => pickTree(hospital.hospital)}>{hospital.label} <span className="cw-muted">({hospital.count})</span></button>
          <ul>{hospital.departments.map((department) => <li key={department.label}><button type="button" className="rg-link" onClick={() => pickTree(hospital.hospital, department.department)}>{department.label} <span className="cw-muted">({department.count})</span></button></li>)}</ul>
        </li>)}
      </ul>
      </details>
    </nav>

    <div className="reg-main">
      <div className="cw-section reg-toolbar">
        <label>Ansicht<select value={viewId ?? ""} onChange={(event) => {
          const legacy = legacyViews.find((item) => `legacy:${item.id}` === event.target.value);
          if (legacy) {
            applyView(null, columns);
            const mapped = legacyQueryToSpec(legacy.config.query);
            setSpec((current) => current && ({ ...current, ...mapped }));
            setSearch(mapped.q ?? "");
            return;
          }
          applyView(views.find((item) => item.id === event.target.value) ?? null, columns);
        }}>
          <option value="">Alle Verträge</option>
          <optgroup label="Standard und global">{views.filter((item) => item.is_global).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup>
          <optgroup label="Meine Ansichten">{views.filter((item) => !item.is_global).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup>
          {legacyViews.length > 0 ? <optgroup label="Aus der früheren Vertragsliste">{legacyViews.map((item) => <option key={item.id} value={`legacy:${item.id}`}>{item.name}</option>)}</optgroup> : null}
        </select></label>
        <label>Suche<input type="search" value={search} placeholder="Nummer, Beschreibung, Partner" onChange={(event) => setSearch(event.target.value)} /></label>
        <div className="rg-actions">
          {editableView ? <button type="button" className="btn" onClick={() => void saveView(false)}>Ansicht speichern</button> : null}
          <button type="button" className="btn" onClick={() => setSaveForm({ name: "", is_global: false })}>Speichern unter…</button>
          {editableView && !view?.is_system ? <button type="button" className="btn" onClick={() => void removeView()}>Ansicht löschen</button> : null}
          {canExport ? <button type="button" className="btn" onClick={() => void exportXlsx()}>Excel exportieren</button> : null}
        </div>
      </div>

      {saveForm ? <form className="cw-section rg-transition" aria-label="Ansicht speichern" onSubmit={(event) => { event.preventDefault(); void saveView(true); }}>
        <label>Name der Ansicht<input required maxLength={120} value={saveForm.name} onChange={(event) => setSaveForm((form) => form && ({ ...form, name: event.target.value }))} /></label>
        {canManageGlobal ? <label className="rg-check"><input type="checkbox" checked={saveForm.is_global} onChange={(event) => setSaveForm((form) => form && ({ ...form, is_global: event.target.checked }))} />Für alle Benutzer der Organisation (global)</label> : null}
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setSaveForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary">Speichern</button></div>
      </form> : null}

      <div className="cw-section reg-controls">
        <details className="reg-columns">
          <summary>Spalten ({spec.columns.length})</summary>
          <fieldset><legend className="visually-hidden">Sichtbare Spalten</legend>
            {columns.map((item) => <label key={item.key} className="rg-check"><input type="checkbox" checked={spec.columns.includes(item.key)} onChange={() => toggleColumn(item.key)} />{item.label}</label>)}
          </fieldset>
        </details>
        <label>Gruppieren nach<select value={spec.group_by[0] ?? ""} onChange={(event) => setGroup(0, event.target.value)}>
          <option value="">Keine Gruppierung</option>
          {groupable.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select></label>
        {spec.group_by[0] ? <label>danach<select value={spec.group_by[1] ?? ""} onChange={(event) => setGroup(1, event.target.value)}>
          <option value="">–</option>
          {groupable.filter((item) => item.key !== spec.group_by[0]).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select></label> : null}
        <label className="rg-check"><input type="checkbox" checked={spec.include_deleted} onChange={(event) => update({ include_deleted: event.target.checked })} />Gelöschte einbeziehen</label>
        <button type="button" className="btn" onClick={() => setAddingFilter(true)}>Filter hinzufügen</button>
      </div>

      {spec.filters.length > 0 ? <ul className="reg-chips" aria-label="Aktive Filter">
        {spec.filters.map((item, index) => <li key={`${item.column}-${index}`}>
          {describeFilter(item, columnByKey.get(item.column))}
          <button type="button" aria-label={`Filter entfernen: ${describeFilter(item, columnByKey.get(item.column))}`} onClick={() => update({ filters: spec.filters.filter((_, position) => position !== index) })}>×</button>
        </li>)}
        <li><button type="button" className="rg-link" onClick={() => update({ filters: [] })}>Alle Filter entfernen</button></li>
      </ul> : null}

      {addingFilter ? <FilterEditor organizationSlug={organizationSlug} columns={columns} spec={spec} onCancel={() => setAddingFilter(false)} onApply={(filter) => { update({ filters: [...spec.filters, filter] }); setAddingFilter(false); }} /> : null}

      {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

      <section className="cw-section reg-table-wrap" aria-labelledby="reg-heading" aria-busy={loading}>
        <div className="cw-section-head"><div>
          <h2 id="reg-heading">{view?.name ?? "Alle Verträge"}</h2>
          {archiveMode ? <p>Archivierte Verträge sind aus Vertragsliste und Fristen ausgeblendet; „Wiederherstellen“ holt sie zurück. Es wird nichts gelöscht.</p> : null}
          <p>{total === 0 ? "Keine Verträge für diese Auswahl." : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} von ${total} · Jährliche Kosten gesamt ${sumText(data?.totals, "annual_cost")} · Kosten lfd. Jahr ${sumText(data?.totals, "cost_current_year")}`}</p>
        </div></div>
        {data && data.items.length > 0 ? <div className="reg-scroll"><table className="rg-table reg-table">
          <thead><tr>{shown.map((column) => {
            const sorted = spec.sort?.column === column.key ? (spec.sort.dir === "asc" ? "ascending" : "descending") : "none";
            return <th key={column.key} scope="col" aria-sort={sorted}><button type="button" className="reg-sort" onClick={() => sortBy(column.key)}>{column.label}{sorted === "ascending" ? " ▲" : sorted === "descending" ? " ▼" : ""}</button></th>;
          })}{actionColumn ? <th scope="col">Aktion</th> : null}</tr></thead>
          <tbody>{data.items.map((row) => {
            const headers = spec.group_by.map((_, depth) => {
              const path = row.group.slice(0, depth + 1);
              const changed = !previous || JSON.stringify(previous.slice(0, depth + 1)) !== JSON.stringify(path);
              if (!changed) return null;
              const group = groupIndex.get(JSON.stringify(path));
              return <tr key={`g-${depth}-${JSON.stringify(path)}`} className={`reg-group reg-group-${depth}`}>
                <th scope="colgroup" colSpan={shown.length + (actionColumn ? 1 : 0)}>
                  {columnByKey.get(spec.group_by[depth])?.label}: {group?.labels[depth] ?? "(ohne)"} <span className="cw-muted">· {group?.count ?? 0} Verträge · {sumText(group, "annual_cost")} jährlich</span>
                </th>
              </tr>;
            });
            previous = row.group;
            return <Fragment key={row.contract_id}>
              {headers}
              <tr>{shown.map((column, index) => {
                const value = row.values[column.key];
                const text = formatCell(column, value);
                if (index === 0 || column.key === "register_number") {
                  return <td key={column.key}><Link href={`/contracts/${row.contract_id}?tab=register`}>{text}</Link></td>;
                }
                if (column.key === "short_description") {
                  return <td key={column.key}><button type="button" className="btn-link reg-preview" onClick={() => setPreview(row.contract_id)} aria-label={`${text} in der Schnellansicht öffnen`}>{text}</button></td>;
                }
                return <td key={column.key} className={column.type === "money" || column.type === "number" ? "num" : undefined}>{text}</td>;
              })}{archiveMode && canExport
                ? <td><button type="button" className="btn btn-sm" disabled={busyRow === row.contract_id} onClick={() => void restore(row.contract_id)} aria-label={`Vertrag ${row.values.register_number ?? ""} wiederherstellen`}>Wiederherstellen</button></td>
                : reviewMode ? <td><Link className="btn btn-sm btn-primary" href={`/contracts/${row.contract_id}?tab=documents&subtab=review`} aria-label={`Vertrag ${row.values.register_number ?? ""} prüfen`}>Prüfen</Link></td> : null}</tr>
            </Fragment>;
          })}</tbody>
        </table></div> : null}
        {total > PAGE_SIZE ? <div className="rg-actions">
          <button type="button" className="btn" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Zurück</button>
          <button type="button" className="btn" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>Weiter</button>
        </div> : null}
      </section>
      <ContractQuickView organizationSlug={organizationSlug} contractId={preview} onClose={() => setPreview(null)} />
    </div>
  </div>;
}
