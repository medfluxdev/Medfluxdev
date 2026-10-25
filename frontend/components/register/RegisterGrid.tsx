"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  createSavedView,
  deleteSavedView,
  downloadGridXlsx,
  getGrid,
  getGridColumns,
  getGridTree,
  listContractListViews,
  listSavedViews,
  saveBlob,
  updateSavedView,
  type GridColumn,
  type GridFilter,
  type GridResponse,
  type GridSpec,
  type ListViewDto,
  type SavedViewDto,
} from "@/lib/domain-api/registerGrid";
import { unarchiveContract } from "@/lib/domain-api/contracts";
import CoverageValue from "@/components/ui/CoverageValue";
import Drawer from "@/components/ui/Drawer";
import Popover from "@/components/ui/Popover";
import { useToast } from "@/components/ui/Toast";
import { usePermissions } from "@/lib/use-permissions";
import ContractQuickView from "./ContractQuickView";
import DisplayMenu from "./DisplayMenu";
import MoreFilters from "./MoreFilters";
import { AreaFilter, PartnerFilter, StatusFilter } from "./QuickFilters";
import RegisterTable from "./RegisterTable";
import { describeFilter } from "./filters";
import {
  PAGE_SIZE,
  TAB_VIEW_KEYS,
  advancedCount,
  cleanAreaFilters,
  defaultColumnKeys,
  errorText,
  legacyQueryToSpec,
  linkedViewKey,
  readLastView,
  readUrlState,
  standardColumns,
  writeLastView,
  writeUrlState,
  type UrlState,
} from "./register-state";

export { legacyQueryToSpec } from "./register-state";

type Spec = GridSpec;

export default function RegisterGrid({ organizationSlug, initialViewKey, tab }: {
  organizationSlug: string;
  /** Standardansicht dieses Reiters (z. B. "review" für „Zu prüfen“). */
  initialViewKey?: string;
  /** Reiter der Vertragsliste; bestimmt ?ansicht= in der Adresse. */
  tab?: string;
}) {
  const { role, account } = useAuth();
  const permissions = usePermissions();
  const canExport = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const canSeeDeleted = permissions.can("contract.view_deleted");
  const [columns, setColumns] = useState<GridColumn[]>([]);
  const [views, setViews] = useState<SavedViewDto[]>([]);
  const [canManageGlobal, setCanManageGlobal] = useState(false);
  const [viewId, setViewId] = useState<string | null>(null);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<GridResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "ok"; text: string } | null>(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [saveForm, setSaveForm] = useState<{ name: string; is_global: boolean } | null>(null);
  const [legacyViews, setLegacyViews] = useState<ListViewDto[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [busyRow, setBusyRow] = useState<string | null>(null);
  // Seiten mit fester Ansicht (Archiv, Prüfungen) überschreiben die zuletzt genutzte Ansicht der Vertragsliste nicht.
  const presetPage = useRef(Boolean(initialViewKey));
  const areaChecked = useRef(false);
  const mounted = useRef(true);
  const toast = useToast();

  const columnByKey = useMemo(() => new Map(columns.map((item) => [item.key, item])), [columns]);
  const view = views.find((item) => item.id === viewId) ?? null;
  const standard = useMemo(() => standardColumns(columns, view), [columns, view]);

  const applyView = useCallback((next: SavedViewDto | null, defaults: GridColumn[]) => {
    const base: Spec = { columns: defaultColumnKeys(defaults), filters: [], sort: null, group_by: [], q: null, include_deleted: false, archived: false };
    const config = next ? { ...base, ...next.config } : base;
    setViewId(next?.id ?? null);
    setSpec(config);
    setSearch(config.q ?? "");
    setOffset(0);
    if (presetPage.current) return;
    writeLastView(next?.id ?? null);
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
        const url = readUrlState();
        const known = new Set(columnResult.columns.map((item) => item.key));
        const overlay = (state: UrlState) => {
          const linkedColumns = state.columns?.filter((key) => known.has(key)) ?? [];
          setSpec((current) => current && ({
            ...current,
            ...(state.filters ? { filters: state.filters } : {}),
            ...(state.q !== null ? { q: state.q } : {}),
            ...(state.sort ? { sort: state.sort } : {}),
            ...(state.groupBy ? { group_by: state.groupBy } : {}),
            ...(linkedColumns.length ? { columns: linkedColumns } : {}),
            ...(state.includeDeleted ? { include_deleted: true } : {}),
          }));
          if (state.q !== null) setSearch(state.q);
          setOffset(state.page * PAGE_SIZE);
        };
        // Reiter mit fester Ansicht (Zu prüfen, Archiv): Ansicht des Reiters plus Zustand aus der Adresse.
        const presetKey = initialViewKey ?? linkedViewKey();
        const preset = presetKey ? viewResult.items.find((item) => item.system_key === presetKey) : undefined;
        if (preset) {
          applyView(preset, columnResult.columns);
          overlay(url);
          return;
        }
        // Bestand: gespeicherte Ansicht aus der Adresse, sonst bei verlinkten Filtern „Alle Verträge“,
        // sonst die zuletzt genutzte Ansicht – aber nie eine Reiter-Ansicht (die gehört zu ihrem Reiter).
        const named = url.viewId ? viewResult.items.find((item) => item.id === url.viewId && !TAB_VIEW_KEYS.has(item.system_key ?? "")) : undefined;
        if (named || url.filters || url.q) {
          applyView(named ?? null, columnResult.columns);
          overlay(url);
          return;
        }
        const remembered = readLastView();
        const last = viewResult.items.find((item) => item.id === remembered && !TAB_VIEW_KEYS.has(item.system_key ?? ""));
        applyView(last ?? null, columnResult.columns);
        overlay(url);
      })
      .catch((error) => { if (!cancelled) setMessage({ tone: "error", text: errorText(error, "Das Vertragsregister konnte nicht geladen werden.") }); });
    return () => { cancelled = true; };
  }, [applyView, initialViewKey, organizationSlug]);

  // Krankenhaus-/Abteilungsfilter aus Adresse oder Ansicht gegen den aktuellen Bereich prüfen
  // (nach einem Wechsel oben im Kopf können sie ins Leere zeigen). Ohne Antwort bleibt alles stehen.
  useEffect(() => {
    if (!spec || areaChecked.current) return;
    areaChecked.current = true;
    if (!spec.filters.some((item) => item.op === "in" && (item.column === "hospital" || item.column === "department"))) return;
    // Bewusst ohne Abbruch bei späteren Änderungen: die Prüfung läuft einmal und bereinigt den dann aktuellen Stand.
    getGridTree(organizationSlug, { archived: spec.archived ?? false })
      .then((result) => {
        if (!mounted.current) return;
        let removed: string[] = [];
        setSpec((current) => {
          if (!current) return current;
          const cleaned = cleanAreaFilters(current.filters, result.hospitals);
          removed = cleaned.removed;
          return cleaned.removed.length ? { ...current, filters: cleaned.filters } : current;
        });
        if (!removed.length) removed = cleanAreaFilters(spec.filters, result.hospitals).removed;
        if (removed.length) {
          setOffset(0);
          setMessage({ tone: "ok", text: `Nicht im gewählten Krankenhaus-Bereich und deshalb aus den Filtern entfernt: ${removed.join(", ")}.` });
        }
      })
      .catch(() => undefined);
  }, [organizationSlug, spec]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (!spec) return;
    let cancelled = false;
    setLoading(true);
    getGrid(organizationSlug, spec, { offset, limit: PAGE_SIZE, includeTree: true })
      .then((grid) => {
        if (cancelled) return;
        setData(grid);
        // Seite hinter dem Ende (z. B. nach einem Bereichswechsel): zurück auf die erste Seite.
        if (offset > 0 && grid.total > 0 && offset >= grid.total) setOffset(0);
      })
      .catch((error) => { if (!cancelled) setMessage({ tone: "error", text: errorText(error, "Die Liste konnte nicht geladen werden.") }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [offset, organizationSlug, spec]);

  useEffect(() => {
    if (!spec || !columns.length) return;
    writeUrlState(tab, presetPage.current ? null : viewId, spec, Math.floor(offset / PAGE_SIZE), standard);
  }, [columns.length, offset, spec, standard, tab, viewId]);

  useEffect(() => {
    if (!spec) return;
    const handle = window.setTimeout(() => {
      const q = search.trim() || null;
      if (q !== spec.q) { setSpec({ ...spec, q }); setOffset(0); }
    }, 300);
    return () => window.clearTimeout(handle);
  }, [search, spec]);

  // Jede Änderung an Treffermenge oder Darstellung beginnt wieder auf Seite 1.
  function update(patch: Partial<Spec>) {
    if (!spec) return;
    setSpec({ ...spec, ...patch });
    setOffset(0);
  }

  function setFilters(filters: GridFilter[]) {
    update({ filters });
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
  const editableView = view && (view.is_own || (view.is_global && canManageGlobal));
  const total = data?.total ?? 0;
  const archiveMode = Boolean(spec.archived);
  const reviewMode = spec.filters.some((item) => item.column === "review_pending" && item.op === "is" && item.value === true);
  const baseFilters = view?.config.filters ?? [];
  const narrowed = Boolean(spec.q) || spec.filters.length > baseFilters.length
    || spec.filters.some((item) => !baseFilters.some((base) => JSON.stringify(base) === JSON.stringify(item)));
  const emptyText = archiveMode ? "Das Archiv ist leer." : reviewMode ? "Keine Verträge mit offener KI-Prüfung." : "Noch keine Verträge in diesem Bereich.";
  const extra = advancedCount(spec.filters);
  const heading = presetPage.current ? (view?.name ?? "Verträge") : view?.name ?? "Alle Verträge";
  const coverage = (key: string) => data?.totals.coverage?.[key];

  // „Alle zurücksetzen“: Suche und zusätzliche Filter weg, Ansicht, Reiter, Bereich und Darstellung bleiben.
  function resetNarrowing() {
    if (!spec) return;
    setSearch("");
    setSpec({ ...spec, q: null, filters: view?.config.filters ?? [] });
    setOffset(0);
  }

  async function restore(contractId: string) {
    if (!spec) return;
    setBusyRow(contractId);
    try {
      await unarchiveContract(contractId, organizationSlug);
      toast("Vertrag wieder ins aktive Portfolio verschoben.", "success");
      setSpec({ ...spec });
      window.dispatchEvent(new Event("medflux:register-changed"));
    } catch (error) {
      toast(errorText(error, "Wiederherstellung fehlgeschlagen."), "error");
    } finally {
      setBusyRow(null);
    }
  }

  function pickView(value: string) {
    const legacy = legacyViews.find((item) => `legacy:${item.id}` === value);
    if (legacy) {
      applyView(null, columns);
      const mapped = legacyQueryToSpec(legacy.config.query);
      setSpec((current) => current && ({ ...current, ...mapped }));
      setSearch(mapped.q ?? "");
      return;
    }
    applyView(views.find((item) => item.id === value) ?? null, columns);
  }

  return <div className="reg-page">
    <div className="reg-bar">
      <label className="reg-search">
        <span className="visually-hidden">Suche</span>
        <input type="search" value={search} placeholder="Suchen: Nr., Beschreibung, Partner, interne Nr., Typ" onChange={(event) => setSearch(event.target.value)} />
      </label>
      {presetPage.current ? null : <div className="reg-view">
        <label>Ansicht<select value={viewId ?? ""} onChange={(event) => pickView(event.target.value)}>
          <option value="">Alle Verträge</option>
          <optgroup label="Standard und global">{views.filter((item) => item.is_global && !TAB_VIEW_KEYS.has(item.system_key ?? "")).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup>
          <optgroup label="Meine Ansichten">{views.filter((item) => !item.is_global).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup>
          {legacyViews.length > 0 ? <optgroup label="Aus der früheren Vertragsliste">{legacyViews.map((item) => <option key={item.id} value={`legacy:${item.id}`}>{item.name}</option>)}</optgroup> : null}
        </select></label>
        <Popover label="Ansicht verwalten" panelLabel="Ansicht verwalten">
          {(close) => <div className="reg-menu">
            {editableView ? <button type="button" className="btn btn-sm" onClick={() => { close(); void saveView(false); }}>Ansicht speichern</button> : null}
            <button type="button" className="btn btn-sm" onClick={() => { close(); setSaveForm({ name: "", is_global: false }); }}>Speichern unter…</button>
            {editableView && !view?.is_system ? <button type="button" className="btn btn-sm" onClick={() => { close(); void removeView(); }}>Ansicht löschen</button> : null}
          </div>}
        </Popover>
      </div>}
    </div>

    {/* Schnellfilter links, Filter-/Darstellungs-/Export-Aktionen rechts – eine Zeile auf breiten Bildschirmen. */}
    <div className="reg-row">
      <div className="reg-quick" role="group" aria-label="Schnellfilter">
        <StatusFilter column={columnByKey.get("business_status")} spec={spec} onFilters={setFilters} />
        <PartnerFilter organizationSlug={organizationSlug} column={columnByKey.get("partner")} spec={spec} onFilters={setFilters} labels={data?.filter_labels} />
        <AreaFilter tree={data?.tree ?? []} spec={spec} onFilters={setFilters} />
        <PartnerFilter organizationSlug={organizationSlug} column={columnByKey.get("device_types") ? { ...columnByKey.get("device_types")!, label: "Geräteart" } : undefined} spec={spec} onFilters={setFilters} />
      </div>
      <div className="reg-bar-actions">
        <button type="button" className={`btn${extra ? " popover-trigger--active" : ""}`} aria-haspopup="dialog" onClick={() => setMoreOpen(true)}>
          Weitere Filter{extra ? ` (${extra})` : ""}
        </button>
        <DisplayMenu
          columns={columns}
          spec={spec}
          standard={standard}
          onToggleColumn={toggleColumn}
          onColumns={(keys) => update({ columns: keys })}
          onGroup={setGroup}
        />
        {canExport ? <button type="button" className="btn" onClick={() => void exportXlsx()}>Excel exportieren</button> : null}
      </div>
    </div>

    {spec.filters.length > 0 || narrowed ? <ul className="reg-chips" aria-label="Aktive Filter">
      {spec.filters.map((item, index) => {
        const text = describeFilter(item, columnByKey.get(item.column));
        return <li key={`${item.column}-${index}`}>
          {text}
          <button type="button" aria-label={`Filter entfernen: ${text}`} onClick={() => setFilters(spec.filters.filter((_, position) => position !== index))}>×</button>
        </li>;
      })}
      {narrowed ? <li className="reg-chips-reset"><button type="button" className="rg-link" onClick={resetNarrowing}>Alle zurücksetzen</button></li> : null}
    </ul> : null}

    {saveForm ? <form className="cw-section rg-transition" aria-label="Ansicht speichern" onSubmit={(event) => { event.preventDefault(); void saveView(true); }}>
      <label>Name der Ansicht<input required maxLength={120} value={saveForm.name} onChange={(event) => setSaveForm((form) => form && ({ ...form, name: event.target.value }))} /></label>
      {canManageGlobal ? <label className="rg-check"><input type="checkbox" checked={saveForm.is_global} onChange={(event) => setSaveForm((form) => form && ({ ...form, is_global: event.target.checked }))} />Für alle Benutzer der Organisation (global)</label> : null}
      <div className="rg-actions"><button type="button" className="btn" onClick={() => setSaveForm(null)}>Abbrechen</button><button type="submit" className="btn btn-primary">Speichern</button></div>
    </form> : null}

    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

    <section className="cw-section reg-table-wrap" aria-labelledby="reg-heading" aria-busy={loading}>
      <h2 id="reg-heading" className="visually-hidden">{heading}</h2>
      {archiveMode ? <p className="cw-muted">Archivierte Verträge sind aus Vertragsliste und Fristen ausgeblendet; „Wiederherstellen“ holt sie zurück. Es wird nichts gelöscht.</p> : null}
      {data ? total === 0
        ? <p className="reg-summary">{narrowed ? "Keine Treffer für diese Filter." : emptyText}</p>
        : <p className="reg-summary">
          <strong>{total === 1 ? "1 Vertrag" : `${total.toLocaleString("de-DE")} Verträge`}</strong>
          <span>Jährliche Kosten (netto) <CoverageValue showNote={false} value={data.totals.sums.annual_cost} currency={data.totals.currency} known={coverage("annual_cost")?.known} missing={coverage("annual_cost")?.missing} otherCurrencies={data.totals.other_currencies?.annual_cost} /></span>
          <span>Kosten lfd. Jahr (netto) <CoverageValue showNote={false} value={data.totals.sums.cost_current_year} currency={data.totals.currency} known={coverage("cost_current_year")?.known} missing={coverage("cost_current_year")?.missing} otherCurrencies={data.totals.other_currencies?.cost_current_year} /></span>
          {(coverage("annual_cost")?.missing ?? 0) > 0 && !spec.filters.some((item) => item.column === "cost_current_year" && item.op === "empty")
            ? <button type="button" className="rg-link" onClick={() => setFilters([...spec.filters, { column: "cost_current_year", op: "empty" }])}>Verträge ohne Kosten anzeigen</button>
            : null}
        </p> : null}
      {data && total === 0 && narrowed && !loading ? <p className="reg-filtered-empty">Die Filter oder die Suche blenden alle Verträge aus. <button type="button" className="rg-link" onClick={resetNarrowing}>Filter und Suche zurücksetzen</button></p> : null}
      {data && data.items.length > 0 ? <RegisterTable
        data={data}
        spec={spec}
        shown={shown}
        columnByKey={columnByKey}
        archiveMode={archiveMode}
        reviewMode={reviewMode}
        canRestore={canExport}
        busyRow={busyRow}
        onSort={sortBy}
        onRestore={(id) => void restore(id)}
        onPreview={setPreview}
      /> : null}
      {total > PAGE_SIZE ? <nav className="reg-pager" aria-label="Seiten">
        <span>{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} von {total}</span>
        <button type="button" className="btn btn-sm" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Zurück</button>
        <button type="button" className="btn btn-sm" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>Weiter</button>
      </nav> : null}
    </section>

    <Drawer open={moreOpen} title="Weitere Filter" onClose={() => setMoreOpen(false)}>
      <MoreFilters
        organizationSlug={organizationSlug}
        columns={columns}
        spec={spec}
        canSeeDeleted={canSeeDeleted}
        onFilters={setFilters}
        onIncludeDeleted={(value) => update({ include_deleted: value })}
        onDone={() => setMoreOpen(false)}
      />
    </Drawer>
    <ContractQuickView organizationSlug={organizationSlug} contractId={preview} onClose={() => setPreview(null)} />
  </div>;
}
