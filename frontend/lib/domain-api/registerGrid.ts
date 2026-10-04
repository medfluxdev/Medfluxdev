import { apiDelete, apiDownload, apiGet, apiPost, apiPut, scopedApiUrl } from "@/lib/api";

export type ColumnType = "text" | "date" | "money" | "number" | "bool" | "status" | "enum" | "account";
export type FilterOp = "empty" | "not_empty" | "in" | "contains" | "range" | "within_days" | "due_within_days" | "overdue" | "me" | "is";

export interface GridColumn {
  key: string;
  label: string;
  type: ColumnType;
  default: boolean;
  groupable: boolean;
  options?: { value: string; label: string }[];
}

export interface GridFilter {
  column: string;
  op: FilterOp;
  value?: unknown;
}

export interface GridSpec {
  columns: string[];
  filters: GridFilter[];
  sort: { column: string; dir: "asc" | "desc" } | null;
  group_by: string[];
  q: string | null;
  include_deleted: boolean;
}

export interface GridGroup {
  path: (string | number | boolean | null)[];
  labels: string[];
  count: number;
  sums: Record<string, string>;
}

export interface GridResponse {
  as_of: string;
  spec: GridSpec;
  total: number;
  totals: { count: number; sums: Record<string, string> };
  groups: GridGroup[];
  items: { contract_id: string; values: Record<string, string | number | boolean | null>; group: (string | number | boolean | null)[] }[];
}

export interface SavedViewDto {
  id: string;
  name: string;
  config: GridSpec;
  is_global: boolean;
  is_system: boolean;
  is_own: boolean;
  created_by_name: string | null;
}

export interface TreeHospital {
  hospital: string | null;
  label: string;
  count: number;
  departments: { department: string | null; label: string; count: number }[];
}

export interface PortfolioItem {
  label: string;
  value: string | null;
  count: number;
  annual_cost: string;
  cost_current_year: string;
}

export interface PortfolioReport {
  as_of: string;
  totals: { contracts: number; running: number; annual_cost: string; cost_current_year: string; income_current_year: string };
  by_status: { status: string; label: string; count: number }[];
  cost_by: Record<string, PortfolioItem[]>;
  dimensions: { key: string; label: string }[];
  cost_by_year: { year: number; expense: string; income: string; is_projection: boolean }[];
  deadlines_by_month: { month: string; notice: number; other: number }[];
  upcoming: { contract_id: string; register_number: string | null; short_description: string | null; due_date: string; title: string; kind: string }[];
  supplier_concentration: { partner: string; share_percent: string } | null;
  insights: { key: string; label: string; count: number; filter: GridFilter }[];
}

export const EMPTY_SPEC: GridSpec = { columns: [], filters: [], sort: null, group_by: [], q: null, include_deleted: false };

function org(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

function specParam(spec: Partial<GridSpec>) {
  return `spec=${encodeURIComponent(JSON.stringify(spec))}`;
}

export function getGridColumns(organizationSlug: string) {
  return apiGet<{ columns: GridColumn[] }>(`/api/register/columns?${org(organizationSlug)}`);
}

export function getGrid(organizationSlug: string, spec: Partial<GridSpec>, page: { offset: number; limit: number }) {
  return apiGet<GridResponse>(`/api/register/grid?${org(organizationSlug)}&${specParam(spec)}&offset=${page.offset}&limit=${page.limit}`);
}

export function getGridValues(organizationSlug: string, column: string, spec: Partial<GridSpec>) {
  return apiGet<{ column: string; values: { value: string; label: string; count: number }[] }>(
    `/api/register/grid/values?${org(organizationSlug)}&column=${encodeURIComponent(column)}&${specParam(spec)}`,
  );
}

export function getGridTree(organizationSlug: string, spec: Partial<GridSpec>) {
  return apiGet<{ total: number; hospitals: TreeHospital[] }>(`/api/register/grid/tree?${org(organizationSlug)}&${specParam(spec)}`);
}

export function downloadGridXlsx(organizationSlug: string, spec: Partial<GridSpec>, title: string) {
  return apiDownload(`/api/register/grid/export.xlsx?${org(organizationSlug)}&${specParam(spec)}&title=${encodeURIComponent(title)}`, 120000);
}

export function listSavedViews(organizationSlug: string) {
  return apiGet<{ items: SavedViewDto[]; can_manage_global: boolean }>(`/api/register/views?${org(organizationSlug)}`);
}

export function createSavedView(organizationSlug: string, payload: { name: string; config: Partial<GridSpec>; is_global: boolean }) {
  return apiPost<SavedViewDto>(`/api/register/views?${org(organizationSlug)}`, payload);
}

export function updateSavedView(organizationSlug: string, viewId: string, payload: { name: string; config: Partial<GridSpec> }) {
  return apiPut<SavedViewDto>(`/api/register/views/${encodeURIComponent(viewId)}?${org(organizationSlug)}`, payload);
}

export function deleteSavedView(organizationSlug: string, viewId: string) {
  return apiDelete<{ deleted: boolean }>(`/api/register/views/${encodeURIComponent(viewId)}?${org(organizationSlug)}`);
}

export function getPortfolioReport(organizationSlug: string) {
  return apiGet<PortfolioReport>(`/api/register/reports/portfolio?${org(organizationSlug)}`);
}

export function downloadPortfolioXlsx(organizationSlug: string) {
  return apiDownload(`/api/register/reports/portfolio.xlsx?${org(organizationSlug)}`, 120000);
}

export function coverPdfUrl(organizationSlug: string, contractId: string) {
  return scopedApiUrl(`/api/contracts/${encodeURIComponent(contractId)}/cover.pdf?${org(organizationSlug)}`);
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
