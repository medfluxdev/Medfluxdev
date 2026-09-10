"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiPost, apiUpload } from "@/lib/api";
import {
  ImportBatchResponse,
  ImportFileResult,
  ImportStatus,
} from "@/lib/types";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge, { StatusTone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";

const statusLabel: Record<ImportStatus, string> = {
  imported: "Importiert",
  duplicate: "Duplikat",
  rejected: "Fehlgeschlagen",
  failed: "Fehlgeschlagen",
  analysis_failed: "Analyse fehlgeschlagen",
};

const statusTone: Record<ImportStatus, StatusTone> = {
  imported: "success",
  duplicate: "warning",
  rejected: "critical",
  failed: "critical",
  analysis_failed: "warning",
};

export default function ImportPage() {
  const [selected, setSelected] = useState<File[]>([]);
  const [results, setResults] = useState<ImportFileResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    setResults(null);
    setError(null);
    setSelected((prev) => [...prev, ...Array.from(list)]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const handleDropzoneKey = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        inputRef.current?.click();
      }
    },
    []
  );

  const handleUpload = useCallback(async () => {
    if (selected.length === 0 || loading) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await apiUpload<ImportBatchResponse>(
        "/api/documents/import",
        selected,
        "krankenhaus"
      );
      setResults(res.documents);
      setSelected([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Import fehlgeschlagen: ${err.message}`
          : "Import fehlgeschlagen"
      );
    } finally {
      setLoading(false);
    }
  }, [selected, loading]);

  const importedCount = useMemo(
    () => results?.filter((r) => r.status === "imported").length ?? 0,
    [results]
  );

  const canRetry = (r: ImportFileResult): boolean =>
    (r.status === "analysis_failed" || r.analysis_status === "failed") &&
    !!r.document_version_id;

  const retryAnalysis = useCallback(
    async (r: ImportFileResult) => {
      if (!r.document_version_id || retryingId) return;
      setRetryingId(r.document_version_id);
      try {
        const res = await apiPost<{
          status: string;
          analysis_status: string | null;
          message: string | null;
          contract_id: string | null;
        }>(
          `/api/documents/${encodeURIComponent(
            r.document_version_id
          )}/retry?organization_slug=${encodeURIComponent("krankenhaus")}`,
          {}
        );
        setResults((prev) =>
          prev
            ? prev.map((x) =>
                x.document_version_id === r.document_version_id
                  ? {
                      ...x,
                      status:
                        res.status === "imported" || res.analysis_status === "success"
                          ? "imported"
                          : res.status === "analysis_failed" ||
                              res.analysis_status === "failed"
                            ? "analysis_failed"
                            : x.status,
                      analysis_status: res.analysis_status ?? x.analysis_status,
                      message:
                        res.message ??
                        (res.analysis_status === "success"
                          ? "Analyse erneut erfolgreich."
                          : "Analyse erneut fehlgeschlagen."),
                      contract_id: res.contract_id ?? x.contract_id,
                    }
                  : x
              )
            : prev
        );
        toast(
          res.analysis_status === "success" || res.status === "imported"
            ? `Analyse für „${r.original_filename}“ erneut erfolgreich.`
            : `Analyse für „${r.original_filename}“ erneut fehlgeschlagen.`,
          res.analysis_status === "success" || res.status === "imported"
            ? "success"
            : "error"
        );
      } catch {
        toast(
          `Erneute Analyse für „${r.original_filename}“ konnte nicht gestartet werden.`,
          "error"
        );
      } finally {
        setRetryingId(null);
      }
    },
    [retryingId, toast]
  );

  const reviewCount = useMemo(
    () =>
      results?.filter(
        (r) => r.status === "imported" && r.requires_review
      ).length ?? 0,
    [results]
  );

  return (
    <div className="page">
      <PageHeader
        title="Verträge importieren"
        description="PDF- oder DOCX-Dateien lokal hinzufügen – vollständig verarbeitet im lokalen Rechenzentrum des Krankenhauses."
      />

      <div className="import-layout">
        <div>
          <div
            className="dropzone"
            role="button"
            tabIndex={0}
            aria-label="Dateien hinzufügen. Klicken oder Dateien hierher ziehen."
            onClick={() => inputRef.current?.click()}
            onKeyDown={handleDropzoneKey}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            <p className="dz-primary">Dateien hierher ziehen oder klicken</p>
            <p>
              Unterstützt: <strong>PDF</strong> und <strong>DOCX</strong>
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.docx"
              style={{ display: "none" }}
              onChange={(e) => addFiles(e.target.files)}
            />
          </div>

          {selected.length > 0 && !loading && (
            <>
              <ul className="file-list" aria-label="Ausgewählte Dateien">
                {selected.map((file, i) => (
                  <li key={`${file.name}-${i}`} className="file-row">
                    <span className="file-name">{file.name}</span>
                    <span className="file-meta">
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                    <Button size="sm" variant="danger" onClick={() => removeFile(i)}>
                      Entfernen
                    </Button>
                  </li>
                ))}
              </ul>
              <div className="import-actions">
                <Button variant="primary" onClick={handleUpload}>
                  Import starten ({selected.length})
                </Button>
                <Button onClick={() => setSelected([])}>Alle entfernen</Button>
              </div>
            </>
          )}

          {loading && (
            <div role="status" aria-live="polite">
              <p>
                Upload und lokale Verarbeitung laufen … Der Fortschritt wird
                nicht vorgetäuscht; bei großen PDFs kann das dauern.
              </p>
              <p className="muted small">
                Ablauf: Übertragung → Lesen (OCR nur bei gescannten Seiten) →
                Extraktion → Prüfung auf Mehrdeutigkeit → Fristen- und
                Kostenberechnung → fertig oder fehlgeschlagen.
              </p>
              <div className="import-progress" aria-hidden="true">
                <div className="import-progress-bar import-progress-active" />
              </div>
            </div>
          )}

          {error && (
            <InlineAlert tone="critical" role="alert">
              {error}
            </InlineAlert>
          )}

          {results && results.length > 0 && !loading && (
            <section aria-label="Import-Ergebnis" aria-live="polite">
              <h2 className="card-title">Import-Ergebnis</h2>
              <InlineAlert tone="success" role="status">
                {importedCount} von {results.length} Dateien importiert und analysiert.
                {reviewCount > 0 && ` ${reviewCount} erfordern manuelle Prüfung.`}
              </InlineAlert>
              <div className="result-list">
                {results.map((r, i) => (
                  <div key={i} className="result-row">
                    <span className="result-file">{r.original_filename}</span>
                    <StatusBadge tone={statusTone[r.status]} label={statusLabel[r.status]} />
                    {r.analysis_status && r.status === "imported" && (
                      <span className="result-msg">
                        {r.analysis_status === "success" && "Analyse OK"}
                        {r.analysis_status === "partial" && "Teilanalyse – Prüfung empfohlen"}
                        {r.analysis_status === "failed" && "Analyse fehlgeschlagen"}
                      </span>
                    )}
                    {r.message && <span className="result-msg">{r.message}</span>}
                    {canRetry(r) && (
                      <Button
                        size="sm"
                        disabled={retryingId === r.document_version_id}
                        onClick={() => void retryAnalysis(r)}
                      >
                        {retryingId === r.document_version_id
                          ? "Wird erneut verarbeitet…"
                          : "Erneut verarbeiten"}
                      </Button>
                    )}
                    {r.contract_id && (
                      <Link
                        href={`/contracts/${r.contract_id}`}
                        className="result-link"
                      >
                        Vertrag ansehen
                      </Link>
                    )}
                  </div>
                ))}
              </div>
              <div className="import-actions">
                <Link href="/contracts" className="btn btn-primary">
                  Zu den Verträgen
                </Link>
              </div>
            </section>
          )}

          {selected.length === 0 && !loading && !results && !error && (
            <p className="state-empty">
              Noch keine Dateien ausgewählt. Wählen Sie eine oder mehrere
              Wartungs- oder Serviceverträge aus.
            </p>
          )}
        </div>

        <aside className="card card-pad side-note">
          <h2>Hinweise zum Import</h2>
          <ul>
            <li>
              Analysierte Kerninformationen: Laufzeit, Kosten, Kündigungs- und
              Vertragsende-Fristen, Leistungsumfang.
            </li>
            <li>
              Mehrdeutigkeiten werden als „Manuelle Prüfung erforderlich“
              gekennzeichnet – nie per Geratewohl beantwortet.
            </li>
            <li>
              Die Analyse läuft vollständig lokal; es werden keine Vertragsdaten
              an externe Dienste übertragen.
            </li>
            <li>Für Durchsuchbarkeit empfohlen: digitale, textbasierte PDFs.</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}