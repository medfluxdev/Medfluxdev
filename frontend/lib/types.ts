export type ImportStatus =
  | "imported"
  | "rejected"
  | "failed"
  | "duplicate";

export interface ImportFileResult {
  document_id?: string | null;
  original_filename: string;
  status: ImportStatus;
  size: number;
  sha256?: string | null;
  duplicate_of_document_id?: string | null;
  message?: string | null;
}

export interface ImportBatchResponse {
  total: number;
  successful: number;
  failed: number;
  duplicates: number;
  documents: ImportFileResult[];
}
