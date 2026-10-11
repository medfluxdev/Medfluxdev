import type { GridColumn, GridFilter, GridSpec, SavedViewDto, TreeHospital } from "@/lib/domain-api/registerGrid";
import { formatCurrency, formatDate } from "@/lib/format";

// Zustand der Vertragsliste: eine GridSpec für Suche, Schnellfilter, weitere Filter und Chips.
// Alles hier ist rein (ohne React), damit die Regeln einzeln getestet werden können.

export const PAGE_SIZE = 100;
export const LAST_VIEW_KEY = "medflux.register.lastView";
// Reiter-Ansichten (Zu prüfen, Archiv) gehören zu ihren Reitern und erscheinen nicht in der Auswahl „Ansicht“.
export const TAB_VIEW_KEYS = new Set(["review", "archive"]);
const AREA_COLUMNS = new Set(["hospital", "department"]);
// Schnellfilter „besitzen“ den ersten „ist einer von“-Filter ihrer Spalte; weitere Bedingungen bleiben unberührt.
export const QUICK_COLUMNS = new Set(["business_status", "partner", "device_types"]);

export function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function formatCell(column: GridColumn | undefined, value: unknown): string {
  if (value == null || value === "") return "–";
  switch (column?.type) {
    case "date": return formatDate(String(value));
    case "money": return formatCurrency(String(value), "EUR");
    case "bool": return value ? "Ja" : "Nein";
    default: return String(value);
  }
}

// ---------------------------------------------------------------- Ansichten und Spalten

export function defaultColumnKeys(columns: GridColumn[]): string[] {
  return columns.filter((item) => item.default).map((item) => item.key);
}

/** Spalten, zu denen „Standardspalten“ zurückkehrt: die der gewählten Ansicht, sonst die Vorgabe. */
export function standardColumns(columns: GridColumn[], view: SavedViewDto | null): string[] {
  return view?.config.columns?.length ? view.config.columns : defaultColumnKeys(columns);
}

export function sameList(a: readonly string[], b: readonly string[]) {
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

// ---------------------------------------------------------------- Adresse und Speicher

export interface UrlState {
  viewId: string | null;
  filters: GridFilter[] | null;
  q: string | null;
  sort: GridSpec["sort"] | null;
  groupBy: string[] | null;
  columns: string[] | null;
  includeDeleted: boolean | null;
  page: number;
}

// Zustand der Liste aus der Adresse: Ansicht, Filter, Suche, Sortierung, Gruppierung, Spalten, Seite (U4).
export function readUrlState(): UrlState {
  const empty: UrlState = { viewId: null, filters: null, q: null, sort: null, groupBy: null, columns: null, includeDeleted: null, page: 0 };
  try {
    const params = new URLSearchParams(window.location.search);
    const sortRaw = params.get("sort");
    const [column, dir] = sortRaw ? sortRaw.split(":") : [];
    const page = Number(params.get("seite") ?? "1");
    const q = params.get("q");
    const columns = params.get("spalten");
    return {
      viewId: params.get("sicht"),
      filters: linkedFilters(params),
      q: q && q.trim() ? q.trim() : null,
      sort: column ? { column, dir: dir === "desc" ? "desc" : "asc" } : null,
      groupBy: params.get("gruppe") ? params.get("gruppe")!.split(",").filter(Boolean).slice(0, 2) : null,
      columns: columns ? columns.split(",").filter(Boolean) : null,
      includeDeleted: params.get("geloescht") === "1" ? true : null,
      page: Number.isFinite(page) && page > 1 ? Math.floor(page) - 1 : 0,
    };
  } catch {
    return empty;
  }
}

function linkedFilters(params: URLSearchParams): GridFilter[] | null {
  try {
    const raw = params.get("filter");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as GridFilter[]) : null;
  } catch {
    return null;
  }
}

export function writeUrlState(tab: string | undefined, viewId: string | null, spec: GridSpec, page: number, standard: string[]) {
  try {
    const params = new URLSearchParams();
    if (tab && tab !== "bestand") params.set("ansicht", tab);
    if (viewId) params.set("sicht", viewId);
    if (spec.q) params.set("q", spec.q);
    if (spec.filters.length) params.set("filter", JSON.stringify(spec.filters));
    if (spec.sort) params.set("sort", `${spec.sort.column}:${spec.sort.dir}`);
    if (spec.group_by.length) params.set("gruppe", spec.group_by.join(","));
    if (!sameList(spec.columns, standard)) params.set("spalten", spec.columns.join(","));
    if (spec.include_deleted) params.set("geloescht", "1");
    if (page > 0) params.set("seite", String(page + 1));
    const query = params.toString();
    const next = `${window.location.pathname}${query ? `?${query}` : ""}`;
    if (next !== `${window.location.pathname}${window.location.search}`) window.history.replaceState(window.history.state, "", next);
  } catch {
    // Adresse ist nur Komfort.
  }
}

// Standardansicht aus der Adresse (?ansicht=…), z. B. aus einem alten Link.
export function linkedViewKey(): string | null {
  try {
    const key = new URLSearchParams(window.location.search).get("ansicht");
    return key && !TAB_VIEW_KEYS.has(key) ? key : null;
  } catch { return null; }
}

export function readLastView(): string | null {
  try { return window.localStorage.getItem(LAST_VIEW_KEY); } catch { return null; }
}

export function writeLastView(id: string | null) {
  try {
    if (id) window.localStorage.setItem(LAST_VIEW_KEY, id);
    else window.localStorage.removeItem(LAST_VIEW_KEY);
  } catch { /* nur Komfort */ }
}

const RISK_LABEL: Record<string, string> = { high: "Hoch", medium: "Mittel", low: "Niedrig" };

// Ansichten der früheren Vertragsliste in Register-Filter übersetzen.
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

// ---------------------------------------------------------------- Filter

export function sameFilter(a: GridFilter, b: GridFilter) {
  return a.column === b.column && a.op === b.op && JSON.stringify(a.value ?? null) === JSON.stringify(b.value ?? null);
}

export function hasFilter(filters: GridFilter[], filter: GridFilter) {
  return filters.some((item) => sameFilter(item, filter));
}

export function toggleFilter(filters: GridFilter[], filter: GridFilter): GridFilter[] {
  return hasFilter(filters, filter) ? filters.filter((item) => !sameFilter(item, filter)) : [...filters, filter];
}

function firstIn(filters: GridFilter[], column: string) {
  return filters.findIndex((item) => item.column === column && item.op === "in");
}

/** Werte des „ist einer von“-Filters einer Spalte (Schnellfilter, Vertragstyp). */
export function inValues(filters: GridFilter[], column: string): string[] {
  const index = firstIn(filters, column);
  const value = index < 0 ? [] : filters[index].value;
  return Array.isArray(value) ? value.map(String) : [];
}

/** Setzt die Werte des „ist einer von“-Filters einer Spalte; leere Auswahl entfernt ihn. */
export function setInValues(filters: GridFilter[], column: string, values: string[]): GridFilter[] {
  const index = firstIn(filters, column);
  if (index < 0) return values.length ? [...filters, { column, op: "in", value: values }] : filters;
  if (!values.length) return filters.filter((_, position) => position !== index);
  return filters.map((item, position) => (position === index ? { ...item, value: values } : item));
}

/** Ein Filter, den ein Schnellfilter (Status, Vertragspartner, Abteilung) darstellt. */
export function isQuickFilter(filters: GridFilter[], index: number): boolean {
  const item = filters[index];
  if (item.op !== "in") return false;
  if (AREA_COLUMNS.has(item.column)) return true;
  return QUICK_COLUMNS.has(item.column) && firstIn(filters, item.column) === index;
}

/** Zahl am Knopf „Weitere Filter“: Bedingungen, die kein Schnellfilter zeigt (keine doppelte Zählung). */
export function advancedCount(filters: GridFilter[]): number {
  return filters.filter((_, index) => !isQuickFilter(filters, index)).length;
}

export interface AreaSelection {
  hospitals: string[];
  departments: string[];
}

export function areaSelection(filters: GridFilter[]): AreaSelection {
  return { hospitals: inValues(filters, "hospital"), departments: inValues(filters, "department") };
}

/**
 * Krankenhaus/Abteilung wählen (wie früher im Baum): null = alle, sonst Krankenhaus und optional Abteilung.
 * Abteilungsnamen sind nicht krankenhausübergreifend eindeutig, deshalb wird das Krankenhaus immer mitgesetzt.
 */
export function setArea(filters: GridFilter[], hospital: string | null, department?: string): GridFilter[] {
  const rest = filters.filter((item) => !(item.op === "in" && AREA_COLUMNS.has(item.column)));
  if (hospital === null) return rest;
  const added: GridFilter[] = [{ column: "hospital", op: "in", value: [hospital] }];
  if (department !== undefined) added.push({ column: "department", op: "in", value: [department] });
  return [...rest, ...added];
}

/**
 * Nach einem Wechsel des Krankenhaus-Bereichs können Krankenhaus-/Abteilungsfilter aus der Adresse
 * oder einer Ansicht ins Leere zeigen. Entfernt Werte, die im aktuellen Bereich nicht vorkommen.
 */
export function cleanAreaFilters(filters: GridFilter[], hospitals: TreeHospital[]): { filters: GridFilter[]; removed: string[] } {
  const allowed: Record<string, Set<string>> = {
    hospital: new Set(hospitals.map((item) => item.hospital ?? "")),
    department: new Set(hospitals.flatMap((item) => item.departments.map((department) => department.department ?? ""))),
  };
  const removed: string[] = [];
  const out: GridFilter[] = [];
  for (const item of filters) {
    if (item.op !== "in" || !AREA_COLUMNS.has(item.column) || !Array.isArray(item.value)) {
      out.push(item);
      continue;
    }
    const values = item.value.map(String);
    const keep = values.filter((value) => allowed[item.column].has(value));
    removed.push(...values.filter((value) => !keep.includes(value)).map((value) => value || "(ohne)"));
    if (keep.length) out.push({ ...item, value: keep });
  }
  return { filters: removed.length ? out : filters, removed };
}

/** Beschriftung eines Schnellfilters: „Status“, „Status: Gültig“, „Status: Gültig +2“. */
export function quickLabel(base: string, labels: string[]): string {
  if (!labels.length) return base;
  return labels.length === 1 ? `${base}: ${labels[0]}` : `${base}: ${labels[0]} +${labels.length - 1}`;
}
