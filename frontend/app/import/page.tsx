"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiPost, apiUpload } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { ImportBatchResponse, ImportFileResult, ImportStatus } from "@/lib/types";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge, { StatusTone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";

const statusLabel: Record<ImportStatus, string> = {
  imported: "Importiert",
  duplicate: "Duplikat",
  rejected: "Abgelehnt",
  failed: "Import fehlgeschlagen",
  analysis_failed: "Importiert",
};

const statusTone: Record<ImportStatus, StatusTone> = {
  imported: "success",
  duplicate: "warning",
  rejected: "critical",
  failed: "critical",
  analysis_failed: "success",
};

function supportedFile(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}

function analysisLabel(result: ImportFileResult): string {
  if (result.status === "duplicate") return "Nicht erneut analysiert";
  if (result.status === "rejected" || result.status === "failed") return "Nicht gestartet";
  if (result.status === "analysis_failed" || result.analysis_status === "failed") return "Fehlgeschlagen";
  if (result.analysis_status === "partial") return "Teilanalyse – Prüfung erforderlich";
  if (result.analysis_status === "success") return "Erfolgreich";
  return "Status nicht gemeldet";
}

export default function ImportPage() {
  const { organizationSlug, membership } = useAuth();
  const [selected, setSelected] = useState<File[]>([]);
  const [rejectedSelection, setRejectedSelection] = useState<string[]>([]);
  const [results, setResults] = useState<ImportFileResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const effectiveOrgSlug = organizationSlug ?? membership?.organization_slug ?? "krankenhaus";

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list);
    const accepted = incoming.filter(supportedFile);
    const rejected = incoming.filter((file) => !supportedFile(file)).map((file) => file.name);
    setResults(null);
    setError(null);
    setRejectedSelection(rejected);
    setSelected((prev) => [...prev, ...accepted]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleDropzoneKey = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      inputRef.current?.click();
    }
  }, []);

  const handleUpload = useCallback(async () => {
    if (selected.length === 0 || loading) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await apiUpload<ImportBatchResponse>("/api/documents/import", selected, effectiveOrgSlug);
      setResults(res.documents);
      setSelected([]);
      setRejectedSelection([]);
    } catch (err) {
      setError(err instanceof Error ? `Import fehlgeschlagen: ${err.message}` : "Import fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }, [selected, loading, effectiveOrgSlug]);

  const importAcceptedCount = useMemo(
    () => results?.filter((r) => r.status === "imported" || r.status === "analysis_failed").length ?? 0,
    [results]
  );
  const analysisSuccessCount = useMemo(
    () => results?.filter((r) => r.analysis_status === "success").length ?? 0,
    [results]
  );
  const analysisFailedCount = useMemo(
    () => results?.filter((r) => r.status === "analysis_failed" || r.analysis_status === "failed").length ?? 0,
    [results]
  );
  const duplicateCount = useMemo(
    () => results?.filter((r) => r.status === "duplicate").length ?? 0,
    [results]
  );
  const reviewCount = useMemo(
    () => results?.filter((r) => (r.status === "imported" || r.status === "analysis_failed") && r.requires_review).length ?? 0,
    [results]
  );

  const canRetry = (r: ImportFileResult): boolean =>
    (r.status === "analysis_failed" || r.analysis_status === "failed") && !!r.document_version_id;

  const retryAnalysis = useCallback(async (r: ImportFileResult) => {
    if (!r.document_version_id || retryingId) return;
    setRetryingId(r.document_version_id);
    try {
      const res = await apiPost<{
        status: string;
        analysis_status: string | null;
        message: string | null;
        contract_id: string | null;
      }>(`/api/documents/${encodeURIComponent(r.document_version_id)}/retry?organization_slug=${encodeURIComponent(effectiveOrgSlug)}`, {});
      setResults((prev) => prev ? prev.map((x) => x.document_version_id === r.document_version_id ? {
        ...x,
        status: res.status === "imported" || res.analysis_status === "success" ? "imported" : res.status === "analysis_failed" || res.analysis_status === "failed" ? "analysis_failed" : x.status,
        analysis_status: res.analysis_status ?? x.analysis_status,
        message: res.message ?? (res.analysis_status === "success" ? "Analyse erneut erfolgreich." : "Analyse erneut fehlgeschlagen."),
        contract_id: res.contract_id ?? x.contract_id,
      } : x) : prev);
      toast(
        res.analysis_status === "success" || res.status === "imported"
          ? `Analyse für „${r.original_filename}“ erneut erfolgreich.`
          : `Analyse für „${r.original_filename}“ erneut fehlgeschlagen.`,
        res.analysis_status === "success" || res.status === "imported" ? "success" : "error"
      );
    } catch {
      toast(`Erneute Analyse für „${r.original_filename}“ konnte nicht gestartet werden.`, "error");
    } finally {
      setRetryingId(null);
    }
  }, [effectiveOrgSlug, retryingId, toast]);

  return (
    <div className="page">
      <PageHeader
        title="Verträge importieren"
        description="PDF- oder DOCX-Dateien hinzufügen. Import und Analyse laufen vollständig lokal und werden getrennt ausgewiesen."
      />

      <div className="import-layout">
        <div>
          <div className="import-scope-card" role="note" aria-label="Zielbereich des Imports">
            <strong>Zielbereich</strong>
            <span>{membership?.organization_name ?? effectiveOrgSlug}</span>
            <span>Der aktuell in der Kopfzeile gewählte Krankenhaus-/Abteilungsbereich wird nach erfolgreichem Import dem Vertrag zugeordnet.</span>
          </div>

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
            <p>Unterstützte Dateitypen: <strong>PDF</strong> und <strong>DOCX</strong></p>
            <p className="import-validation-note">Eine feste maximale Dateigröße wird von der aktuellen Import-API nicht als Frontend-Limit bereitgestellt.</p>
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx" style={{ display: "none" }} onChange={(e) => addFiles(e.target.files)} />
          </div>

          {rejectedSelection.length > 0 && (
            <InlineAlert tone="critical" role="alert">
              Nicht unterstützte Dateien wurden nicht hinzugefügt: {rejectedSelection.join(", ")}. Erlaubt sind PDF und DOCX.
            </InlineAlert>
          )}

          {selected.length > 0 && !loading && (
            <>
              <ul className="file-list" aria-label="Ausgewählte Dateien">
                {selected.map((file, i) => (
                  <li key={`${file.name}-${i}`} className="file-row">
                    <span className="file-name">{file.name}</span>
                    <span className="file-meta">{(file.size / 1024).toFixed(1)} KB</span>
                    <div className="import-file-state"><span>Datei ausgewählt</span></div>
                    <Button size="sm" variant="danger" onClick={() => removeFile(i)}>Entfernen</Button>
                  </li>
                ))}
              </ul>
              <div className="import-actions">
                <Button variant="primary" onClick={handleUpload}>Import starten ({selected.length})</Button>
                <Button onClick={() => { setSelected([]); setRejectedSelection([]); }}>Alle entfernen</Button>
              </div>
            </>
          )}

          {loading && (
            <div role="status" aria-live="polite">
              <p><strong>Dateien werden übertragen und serverseitig verarbeitet.</strong></p>
              <p className="muted small">Die aktuelle API meldet keine einzelnen Live-Stufen oder Prozentwerte. Ergebnisse pro Datei erscheinen erst nach Abschluss der Verarbeitung.</p>
              <ul className="import-processing-steps" aria-label="Mögliche Verarbeitungsschritte">
                <li>Übertragung</li><li>Lesen/OCR bei Bedarf</li><li>Extraktion</li><li>Analyse</li><li>Fristen/Kosten</li>
              </ul>
              <div className="import-progress" aria-hidden="true"><div className="import-progress-bar import-progress-active" /></div>
            </div>
          )}

          {error && <InlineAlert tone="critical" role="alert">{error}</InlineAlert>}

          {results && results.length > 0 && !loading && (
            <section aria-label="Import-Ergebnis" aria-live="polite">
              <h2 className="card-title">Import-Ergebnis</h2>
              <div className="import-result-summary">
                <div><strong>{importAcceptedCount}</strong><span>importiert</span></div>
                <div><strong>{analysisSuccessCount}</strong><span>Analyse erfolgreich</span></div>
                <div><strong>{analysisFailedCount}</strong><span>Analyse fehlgeschlagen</span></div>
                <div><strong>{duplicateCount}</strong><span>Duplikate</span></div>
              </div>
              {reviewCount > 0 && <InlineAlert tone="warning" role="status">{reviewCount} {reviewCount === 1 ? "Vertrag erfordert" : "Verträge erfordern"} manuelle Prüfung.</InlineAlert>}
              <div className="result-list">
                {results.map((r, i) => (
                  <div key={`${r.document_version_id ?? r.original_filename}-${i}`} className="result-row">
                    <span className="result-file">{r.original_filename}</span>
                    <div className="result-state-stack">
                      <div className="result-state-line"><span className="result-state-label">Import</span><StatusBadge tone={statusTone[r.status]} label={statusLabel[r.status]} /></div>
                      <div className="result-state-line"><span className="result-state-label">Analyse</span><span className="result-state-value">{analysisLabel(r)}</span></div>
                      {r.requires_review && <div className="result-state-line"><span className="result-state-label">Prüfung</span><span className="result-state-value">Erforderlich</span></div>}
                    </div>
                    {r.message && <span className="result-msg">{r.message}</span>}
                    {canRetry(r) && <Button size="sm" disabled={retryingId === r.document_version_id} onClick={() => void retryAnalysis(r)}>{retryingId === r.document_version_id ? "Wird erneut verarbeitet…" : "Analyse erneut starten"}</Button>}
                    {r.contract_id && <Link href={`/contracts/${r.contract_id}`} className="result-link">Vertrag ansehen</Link>}
                  </div>
                ))}
              </div>
              <div className="import-actions"><Link href="/contracts" className="btn btn-primary">Zu den Verträgen</Link></div>
            </section>
          )}

          {selected.length === 0 && !loading && !results && !error && (
            <p className="state-empty">Noch keine Dateien ausgewählt. Wählen Sie eine oder mehrere Wartungs- oder Serviceverträge aus.</p>
          )}
        </div>

        <aside className="card card-pad side-note">
          <h2>Hinweise zum Import</h2>
          <ul>
            <li>Importiert bedeutet, dass das Dokument angenommen und persistiert wurde; der Analysestatus wird separat angezeigt.</li>
            <li>Mehrdeutigkeiten werden als „Manuelle Prüfung erforderlich“ gekennzeichnet – fehlende Angaben werden nicht erfunden.</li>
            <li>Fehlgeschlagene Analysen können nur dann erneut gestartet werden, wenn eine gespeicherte Dokumentversion vorliegt.</li>
            <li>Die Analyse läuft vollständig lokal; es werden keine Vertragsdaten an externe Dienste übertragen.</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}