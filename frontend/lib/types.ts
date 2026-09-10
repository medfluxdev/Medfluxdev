export type ImportStatus =
  | "imported"
  | "rejected"
  | "failed"
  | "duplicate"
  | "analysis_failed";

export interface ImportFileResult {
  document_id?: string | null;
  document_version_id?: string | null;
  original_filename: string;
  status: ImportStatus;
  size: number;
  sha256?: string | null;
  duplicate_of_document_id?: string | null;
  message?: string | null;
  analysis_status?: string | null;
  requires_review?: boolean;
  contract_id?: string | null;
}

export interface ImportBatchResponse {
  total: number;
  successful: number;
  failed: number;
  duplicates: number;
  documents: ImportFileResult[];
}
