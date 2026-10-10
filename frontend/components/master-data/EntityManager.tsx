"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import DataTable, { type Column } from "@/components/ui/DataTable";
import Drawer from "@/components/ui/Drawer";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import Skeleton from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { downloadCsv, toCsv } from "@/lib/csv";
import { getMasterDataUsage } from "@/lib/domain-api/masterData";
import { registerLink, type MasterDataSection } from "@/lib/master-data";
import { usePermissions } from "@/lib/use-permissions";
import EntityEditor from "./EntityEditor";
import type { EntityDefinition, FormValues, ManagerApi } from "./types";

interface Props<T, C> {
  definition: EntityDefinition<T, C>;
  section: MasterDataSection;
  organizationSlug: string;
  /** Zusaetzlicher Bereich ueber der Tabelle (z. B. Dubletten). */
  beforeTable?: (api: ManagerApi<T>, rows: T[], context: C) => ReactNode;
  /** Zweite Darstellung neben der Tabelle (z. B. Strukturbaum). */
  alternateView?: { label: string; render: (rows: T[], context: C, api: ManagerApi<T>) => ReactNode };
}

// Import erst laden, wenn er geoeffnet wird.
const CsvImport = dynamic(() => import("./CsvImport"), { ssr: false, loading: () => <Skeleton lines={3} label="Import wird geladen…" /> });

type DrawerState<T> =
  | { mode: "closed" }
  | { mode: "create"; preset?: FormValues }
  | { mode: "edit"; row: T }
  | { mode: "import" };

function readParams(): URLSearchParams {
  try { return new URLSearchParams(window.location.search); } catch { return new URLSearchParams(); }
}

function writeParams(update: Record<string, string | null>) {
  try {
    const params = new URLSearchParams(window.location.search);
    for (const [key, value] of Object.entries(update)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    const query = params.toString();
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  } catch {
    // Adresse ist nur Komfort (teilbare Filter); ohne sie funktioniert die Seite weiter.
  }
}

// Einheitliche Pflege fuer jede Stammdaten-Art: suchen, filtern, anlegen,
// bearbeiten in der Seitenleiste, deaktivieren, importieren, exportieren.
export default function EntityManager<T, C>({ definition, section, organizationSlug, beforeTable, alternateView }: Props<T, C>) {
  const toast = useToast();
  const { can } = usePermissions();
  const canEdit = can(section.permission);
  const canExport = can("export");
  const canSeeHistory = can("audit.view");

  const initial = useRef(readParams());
  const [rows, setRows] = useState<T[] | null>(null);
  const [context, setContext] = useState<C | null>(null);
  const [usage, setUsage] = useState<Record<string, number> | null | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState(initial.current.get("q") ?? "");
  const [showInactive, setShowInactive] = useState(initial.current.get("inaktiv") === "1");
  const [filters, setFilters] = useState<Record<string, string>>(() => Object.fromEntries(
    (definition.filters ?? []).map((filter) => [filter.key, initial.current.get(filter.key) ?? ""]),
  ));
  const [view, setView] = useState<"table" | "alternate">(alternateView && initial.current.get("ansicht") === "struktur" ? "alternate" : "table");
  const [drawer, setDrawer] = useState<DrawerState<T>>({ mode: "closed" });
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const pendingOpenId = useRef<string | null>(initial.current.get("id"));

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const result = await definition.load(organizationSlug);
      setRows(result.rows);
      setContext(() => result.context);
    } catch (error) {
      setLoadError(error instanceof Error && error.message ? error.message : `${definition.plural} konnten nicht geladen werden.`);
      return;
    }
    try {
      const result = await getMasterDataUsage(organizationSlug, definition.kind);
      const tracked = definition.kind !== "lookup" || (section.fieldKey !== undefined && (result.tracked_lookup_fields ?? []).includes(section.fieldKey));
      setUsage(tracked ? result.counts : null);
    } catch {
      setUsage(null);
    }
  }, [definition, organizationSlug, section.fieldKey]);

  useEffect(() => { void load(); }, [load]);

  // Tiefer Link auf einen Eintrag (?id=…) oeffnet ihn nach dem Laden.
  useEffect(() => {
    if (!rows || !pendingOpenId.current) return;
    const row = rows.find((item) => definition.id(item) === pendingOpenId.current);
    pendingOpenId.current = null;
    if (row) setDrawer({ mode: "edit", row });
  }, [definition, rows]);

  // ?neu=1 oeffnet das Anlegen, sobald die Rechte feststehen.
  const pendingCreate = useRef(initial.current.get("neu") === "1");
  useEffect(() => {
    if (!pendingCreate.current || !canEdit || context === null) return;
    pendingCreate.current = false;
    setDrawer({ mode: "create" });
  }, [canEdit, context]);

  useEffect(() => {
    writeParams({
      neu: null,
      q: query.trim() || null,
      inaktiv: showInactive ? "1" : null,
      ansicht: view === "alternate" ? "struktur" : null,
      id: drawer.mode === "edit" ? definition.id(drawer.row) : null,
      ...filters,
    });
  }, [definition, drawer, filters, query, showInactive, view]);

  const api: ManagerApi<T> = useMemo(() => ({
    reload: load,
    openEdit: (row: T) => { setConfirmClose(false); setDrawer({ mode: "edit", row }); },
    openCreate: (preset?: FormValues) => { setConfirmClose(false); setDrawer({ mode: "create", preset }); },
    canEdit,
  }), [canEdit, load]);

  const visible = useMemo(() => {
    if (!rows || context === null) return [];
    const needle = query.trim().toLocaleLowerCase("de");
    return rows.filter((row) => {
      if (!showInactive && !definition.active(row)) return false;
      for (const filter of definition.filters ?? []) {
        const value = filters[filter.key];
        if (value && !filter.match(row, value)) return false;
      }
      return !needle || definition.searchText(row, context).toLocaleLowerCase("de").includes(needle);
    });
  }, [context, definition, filters, query, rows, showInactive]);

  const inactiveCount = rows ? rows.filter((row) => !definition.active(row)).length : 0;

  // Aktive Filter als entfernbare Chips über der Tabelle (was gerade eingrenzt, auf einen Blick).
  const chips: { key: string; label: string; clear: () => void }[] = [];
  if (query.trim()) chips.push({ key: "q", label: `Suche: „${query.trim()}“`, clear: () => setQuery("") });
  if (context !== null) {
    for (const filter of definition.filters ?? []) {
      const value = filters[filter.key];
      if (!value) continue;
      const option = filter.options(context).find((item) => item.value === value);
      chips.push({ key: filter.key, label: `${filter.label}: ${option?.label ?? value}`, clear: () => setFilters((current) => ({ ...current, [filter.key]: "" })) });
    }
  }
  if (showInactive) chips.push({ key: "inaktiv", label: "Mit deaktivierten", clear: () => setShowInactive(false) });
  function clearAll() {
    setQuery("");
    setShowInactive(false);
    setFilters((current) => Object.fromEntries(Object.keys(current).map((key) => [key, ""])));
  }

  function usageOf(row: T): number | null | undefined {
    if (usage === undefined || usage === null) return usage;
    return usage[definition.id(row)] ?? 0;
  }

  function linkFor(row: T): string | null {
    if (context === null) return null;
    const target = definition.registerFilter?.(row, context);
    return target ? registerLink(target.column, target.value, target.op) : null;
  }

  const columns: Column<T>[] = context === null ? [] : [
    ...definition.columns(context),
    {
      key: "usage",
      label: definition.usageLabel ?? "Verträge",
      numeric: true,
      sortValue: usage ? (row: T) => usageOf(row) ?? 0 : undefined,
      render: (row: T) => {
        const count = usageOf(row);
        if (count === undefined) return "…";
        if (count === null) return <span title="Wird für diese Liste nicht erfasst">–</span>;
        const href = linkFor(row);
        return count > 0 && href ? <Link href={href} aria-label={`${count} Verträge mit ${definition.label(row)} anzeigen`}>{count}</Link> : count;
      },
    },
    {
      key: "status",
      label: "Status",
      sortValue: (row: T) => (definition.active(row) ? 0 : 1),
      render: (row: T) => definition.active(row) ? <Badge>Aktiv</Badge> : <Badge>Deaktiviert</Badge>,
    },
    {
      key: "actions",
      label: "Aktionen",
      render: (row: T) => <Button size="sm" onClick={() => api.openEdit(row)} aria-label={`${definition.label(row)} ${canEdit ? "bearbeiten" : "ansehen"}`}>
        {canEdit ? "Bearbeiten" : "Ansehen"}
      </Button>,
    },
  ];

  function requestClose() {
    if (dirty && drawer.mode !== "import") {
      setConfirmClose(true);
      return;
    }
    closeDrawer();
  }

  function closeDrawer() {
    setDirty(false);
    setConfirmClose(false);
    setDrawer({ mode: "closed" });
  }

  async function saved(result: { id: string; created: boolean; label: string }) {
    closeDrawer();
    toast(result.created ? `${definition.singular} „${result.label}“ angelegt.` : `${definition.singular} „${result.label}“ gespeichert.`, "success");
    await load();
  }

  function exportCsv() {
    if (!definition.exportRow || !definition.exportHeader || context === null) return;
    downloadCsv(
      `${section.slug.replace("/", "-")}.csv`,
      toCsv(definition.exportHeader, visible.map((row) => definition.exportRow!(row, context))),
    );
  }

  const drawerTitle = drawer.mode === "create" ? `${definition.singular} anlegen`
    : drawer.mode === "edit" ? definition.label(drawer.row)
      : drawer.mode === "import" ? `${definition.plural} importieren` : "";

  return <div className="md-manager">
    {!canEdit ? <InlineAlert tone="info" role="status">
      Sie können {definition.plural} ansehen. Ändern dürfen: {section.editors}.
    </InlineAlert> : null}
    {definition.intro ? <p className="md-intro">{definition.intro}</p> : null}

    <div className="md-toolbar" role="search">
      <label className="md-search">
        <span className="visually-hidden">{definition.plural} durchsuchen</span>
        <input type="search" value={query} placeholder={`${definition.plural} durchsuchen`} onChange={(event) => setQuery(event.target.value)} />
      </label>
      {context !== null ? (definition.filters ?? []).map((filter) => <label key={filter.key} className="md-filter">
        <span className="visually-hidden">{filter.label}</span>
        <select value={filters[filter.key] ?? ""} onChange={(event) => setFilters((current) => ({ ...current, [filter.key]: event.target.value }))}>
          <option value="">{filter.allLabel}</option>
          {filter.options(context).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>) : null}
      <label className="md-check">
        <input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />
        <span>Deaktivierte anzeigen{inactiveCount ? ` (${inactiveCount})` : ""}</span>
      </label>
      <span className="md-toolbar-actions">
        {alternateView ? <span className="md-segmented" role="group" aria-label="Darstellung">
          <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>Liste</button>
          <button type="button" aria-pressed={view === "alternate"} onClick={() => setView("alternate")}>{alternateView.label}</button>
        </span> : null}
        {canExport && definition.exportRow ? <Button size="sm" onClick={exportCsv} disabled={!rows}>Exportieren</Button> : null}
        {canEdit && definition.importKind ? <Button size="sm" onClick={() => setDrawer({ mode: "import" })}>Importieren</Button> : null}
        {canEdit ? <Button variant="primary" onClick={() => api.openCreate()}>{definition.singular} anlegen</Button> : null}
      </span>
    </div>

    {loadError ? <InlineAlert tone="critical" role="alert" action={<Button size="sm" onClick={() => void load()}>Erneut laden</Button>}>{loadError}</InlineAlert> : null}
    {!rows && !loadError ? <Skeleton lines={6} label={`${definition.plural} werden geladen…`} /> : null}

    {rows && context !== null ? <>
      {beforeTable?.(api, rows, context)}
      <div className="md-results">
        <p className="md-count" role="status">{visible.length} von {rows.length} {definition.plural}</p>
        {chips.length > 0 ? <ul className="md-chips" aria-label="Aktive Filter">
          {chips.map((chip) => <li key={chip.key} className="chip">
            {chip.label}
            <button type="button" aria-label={`Filter entfernen: ${chip.label}`} onClick={chip.clear}>×</button>
          </li>)}
          {chips.length > 1 ? <li><button type="button" className="btn-link" onClick={clearAll}>Alle zurücksetzen</button></li> : null}
        </ul> : null}
      </div>
      {view === "alternate" && alternateView ? alternateView.render(visible, context, api) : <DataTable
        caption={definition.plural}
        columns={columns}
        rows={visible}
        rowKey={definition.id}
        empty={rows.length === 0
          ? <EmptyState
            title={`Noch keine ${definition.plural}`}
            action={canEdit ? <Button variant="primary" onClick={() => api.openCreate()}>{definition.singular} anlegen</Button> : undefined}
          >
            {canEdit ? "Legen Sie den ersten Eintrag an oder importieren Sie eine Liste." : "Es wurden noch keine Einträge angelegt."}
          </EmptyState>
          : <EmptyState>Keine Treffer. Suchbegriff oder Filter ändern{inactiveCount && !showInactive ? " oder deaktivierte Einträge einblenden" : ""}.</EmptyState>}
      />}
    </> : null}

    <Drawer open={drawer.mode !== "closed"} title={drawerTitle} onClose={requestClose} wide={drawer.mode === "import"}>
      {confirmClose ? <InlineAlert
        tone="warning"
        role="alert"
        action={<span className="btn-group">
          <Button size="sm" variant="danger" onClick={closeDrawer}>Verwerfen</Button>
          <Button size="sm" onClick={() => setConfirmClose(false)}>Weiter bearbeiten</Button>
        </span>}
      >
        Ungespeicherte Änderungen verwerfen?
      </InlineAlert> : null}
      {drawer.mode === "import" && definition.importKind && definition.importColumns ? <CsvImport
        organizationSlug={organizationSlug}
        kind={definition.importKind}
        columns={definition.importColumns}
        plural={definition.plural}
        fileName={section.slug.replace("/", "-")}
        fieldKey={section.fieldKey}
        onImported={(count) => { toast(`${count} ${definition.plural} importiert.`, "success"); void load(); }}
      /> : null}
      {(drawer.mode === "create" || drawer.mode === "edit") && context !== null ? <EntityEditor
        definition={definition}
        context={context}
        organizationSlug={organizationSlug}
        row={drawer.mode === "edit" ? drawer.row : null}
        preset={drawer.mode === "create" ? drawer.preset : undefined}
        canEdit={canEdit}
        editorsHint={section.editors}
        canSeeHistory={canSeeHistory}
        usageCount={drawer.mode === "edit" ? usageOf(drawer.row) : undefined}
        registerHref={drawer.mode === "edit" ? linkFor(drawer.row) : null}
        onSaved={(result) => void saved(result)}
        onCancel={requestClose}
        onDirtyChange={setDirty}
      /> : null}
    </Drawer>
  </div>;
}
