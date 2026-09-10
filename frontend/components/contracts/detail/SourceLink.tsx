"use client";

import type { DetailDocument } from "@/lib/contract-detail-types";

interface Props {
  document: DetailDocument;
  active: boolean;
  onSelect: (doc: DetailDocument) => void;
}

// "Quelle anzeigen": PDF -> Viewer im Dokument oeffnen; anderes Format ->
// ehrlicher Hinweis (kein stiller DOCX-Reconvert, keine erfundene Geometrie).
export default function SourceLink({ document, active, onSelect }: Props) {
  if (!document.viewer_supported) {
    return (
      <div className="source-row source-unsupported">
        <span className="source-name">
          {document.original_filename ?? "Quelldokument"}
        </span>
        <span className="source-hint">
          {document.mime_type?.startsWith("application/vnd.openxmlformats")
            ? "DOCX kann derzeit nicht als PDF-Vorschau dargestellt werden."
            : "Quelle kann nicht als PDF-Vorschau dargestellt werden."}
        </span>
      </div>
    );
  }

  return (
    <div className={`source-row${active ? " active" : ""}`}>
      <button
        type="button"
        className="source-link-btn"
        aria-pressed={active}
        aria-current={active ? "true" : undefined}
        onClick={() => onSelect(document)}
      >
        <span className="source-name">
          {document.original_filename ?? "Quelldokument"}
        </span>
        <span className="source-role">
          {(document.role ?? "Quelle") as string}
        </span>
      </button>
    </div>
  );
}
