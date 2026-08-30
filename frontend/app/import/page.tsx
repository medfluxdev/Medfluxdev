"use client";

import { useCallback, useRef, useState } from "react";
import { apiUpload } from "@/lib/api";
import { ImportBatchResponse, ImportFileResult, ImportStatus } from "@/lib/types";

const statusLabel: Record<ImportStatus, string> = {
  imported: "Importiert",
  duplicate: "Duplikat",
  rejected: "Fehlgeschlagen",
  failed: "Fehlgeschlagen",
};

export default function ImportPage() {
  const [selected, setSelected] = useState<File[]>([]);
  const [results, setResults] = useState<ImportFileResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

  const handleUpload = useCallback(async () => {
    if (selected.length === 0) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await apiUpload<ImportBatchResponse>(
        "/api/documents/import",
        selected
      );
      setResults(res.documents);
    } catch (err) {
      setError(
        err instanceof Error
          ? "Import fehlgeschlagen: " + err.message
          : "Import fehlgeschlagen"
      );
    } finally {
      setLoading(false);
    }
  }, [selected]);

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 720 }}>
      <h1>Verträge importieren</h1>
      <p>PDF- oder DOCX-Dateien lokal hinzufügen</p>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        style={{
          border: "2px dashed #888",
          padding: "2rem",
          textAlign: "center",
          cursor: "pointer",
          borderRadius: 8,
          background: "#fafafa",
        }}
      >
        Dateien hierher ziehen oder klicken zum Auswählen
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx"
          style={{ display: "none" }}
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {selected.length > 0 && (
        <>
          <h3>Ausgewählte Dateien</h3>
          <ul>
            {selected.map((file, i) => (
              <li key={`${file.name}-${i}`} style={{ marginBottom: 4 }}>
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
                <button onClick={() => removeFile(i)} style={{ marginLeft: 8 }}>
                  Entfernen
                </button>
              </li>
            ))}
          </ul>

          <button
            onClick={handleUpload}
            disabled={loading}
            style={{ padding: "0.6rem 1.2rem", marginTop: 8 }}
          >
            {loading ? "Import läuft…" : "Import starten"}
          </button>
        </>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}

      {results && results.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Import-Ergebnis</h3>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {results.map((r, i) => (
              <li
                key={i}
                style={{
                  padding: "0.5rem",
                  marginBottom: 4,
                  border: "1px solid #ddd",
                  borderRadius: 4,
                }}
              >
                <strong>{r.original_filename}</strong>
                <span
                  style={{
                    marginLeft: "0.75rem",
                    color:
                      r.status === "imported"
                        ? "green"
                        : r.status === "duplicate"
                        ? "orange"
                        : "red",
                  }}
                >
                  {statusLabel[r.status]}
                </span>
                {r.sha256 && (
                  <div style={{ color: "#666", fontSize: "0.85rem" }}>
                    SHA-256: {r.sha256}
                  </div>
                )}
                {r.message && (
                  <div style={{ color: "#444", fontSize: "0.85rem" }}>
                    {r.message}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
