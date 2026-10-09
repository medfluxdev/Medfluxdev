import { apiGet, apiPost } from "@/lib/api";
import type { PartnerDto } from "@/lib/domain-api/catalogs";

export type MasterDataKind = "partner" | "hospital" | "department" | "cost_center" | "contract_type" | "contract_category" | "lookup" | "rule";
export type MasterDataImportKind = "partner" | "department" | "cost_center" | "lookup";

export interface MasterDataCount {
  total: number;
  active: number;
  inactive: number;
  last_change: string | null;
}

export interface MasterDataSummary {
  kinds: Record<MasterDataKind, MasterDataCount>;
  lookup_lists: { field_key: string; active: number; inactive: number }[];
  hints: { partner_duplicate_groups: number; partners_without_contracts: number | null };
}

export interface MasterDataUsage {
  kind: MasterDataKind;
  counts: Record<string, number>;
  tracked_lookup_fields: string[] | null;
}

export interface MasterDataImportRow {
  line: number;
  label: string;
  errors: string[];
  warnings: string[];
}

export interface MasterDataImportResult {
  valid: boolean;
  created: number;
  errors: string[];
  rows: MasterDataImportRow[];
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getMasterDataSummary(organizationSlug: string) {
  return apiGet<MasterDataSummary>(`/api/master-data/summary?${orgQuery(organizationSlug)}`);
}

export function getMasterDataUsage(organizationSlug: string, kind: MasterDataKind) {
  return apiGet<MasterDataUsage>(`/api/master-data/usage?${orgQuery(organizationSlug)}&kind=${encodeURIComponent(kind)}`);
}

export function importMasterData(
  organizationSlug: string,
  kind: MasterDataImportKind,
  rows: Record<string, string | null>[],
  dryRun: boolean,
  fieldKey?: string,
) {
  return apiPost<MasterDataImportResult>(
    `/api/master-data/import/${encodeURIComponent(kind)}?${orgQuery(organizationSlug)}`,
    { rows, dry_run: dryRun, field_key: fieldKey ?? null },
    60000,
  );
}

export function mergePartners(organizationSlug: string, targetId: string, sourceIds: string[]) {
  return apiPost<PartnerDto & { merged: { id: string; short_name: string; contracts: number }[] }>(
    `/api/catalogs/partners/${encodeURIComponent(targetId)}/merge?${orgQuery(organizationSlug)}`,
    { source_ids: sourceIds },
  );
}
