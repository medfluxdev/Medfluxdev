import { apiGet } from "@/lib/api";

export interface ProcessingJob {
  id: string;
  document_version_id: string;
  status: "running" | "succeeded" | "failed" | "partial" | string;
  provider: string | null;
  provider_version: string | null;
  schema_version: string | null;
  ocr_engine: string | null;
  ocr_engine_version: string | null;
  do_ocr: boolean;
  do_table_structure: boolean;
  geometry_provider: string | null;
  processing_duration: number | null;
  message: string | null;
  error: string | null;
  created_at: string | null;
  contract_id?: string | null;
  original_filename?: string | null;
  page_count: number | null;
  doc_type: string | null;
  processed_at: string | null;
  success_count: number | null;
  failure_count: number | null;
  /** UAT Round 2: deutsche, sichere Status-/Ergebnis-Labels (nie rohe KI-Fehler). */
  status_label_de?: string | null;
  result_label_de?: string | null;
}

export interface ProcessingJobsResponse {
  items: ProcessingJob[];
  total: number;
}

export function listProcessingJobs(organizationSlug: string, options: { status?: string[]; limit?: number } = {}) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  for (const status of options.status ?? []) params.append("status", status);
  if (options.limit) params.set("limit", String(options.limit));
  return apiGet<ProcessingJobsResponse>(`/api/processing-jobs?${params.toString()}`);
}

export function getProcessingJob(organizationSlug: string, jobId: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  return apiGet<ProcessingJob>(`/api/processing-jobs/${encodeURIComponent(jobId)}?${params.toString()}`);
}
