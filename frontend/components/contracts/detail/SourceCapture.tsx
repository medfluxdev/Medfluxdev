"use client";

import { useEffect, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  captureFromDocument,
  getDocumentPageText,
  previewDocumentCapture,
  type DocumentPageText,
} from "@/lib/domain-api/register";

interface Props {
  contractId: string;
  orgSlug: string;
  documentVersionId: string;
  page: number;
  /** Vorausgewähltes Feld (z. B. aus „Stelle im Dokument markieren“). */
  initialField?: string | null;
  onSaved: () => void;
  onClose: () => void;
}

function message(error: unknown, fallback: string) {
  return error instanceof ApiError && error.message ? error.message : fallback;
}

/**
 * „Angabe aus dem Text übernehmen“: Text der aktuellen Seite (so wie MedFlux sie gelesen hat),
 * Stelle markieren, Feld wählen, Vorschau prüfen, übernehmen. Der Wert wird im Backend per Code
 * gelesen und nur gespeichert, wenn die Stelle wörtlich auf der Seite steht.
 */
export default function SourceCapture({ contractId, orgSlug, documentVersionId, page, initialField, onSaved, onClose }: Props) {
  const toast = useToast();
  const textRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<DocumentPageText | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [quote, setQuote] = useState("");
  const [field, setField] = useState(initialField ?? "");
  const [preview, setPreview] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    setData(null);
    setLoadError(false);
    setQuote("");
    getDocumentPageText(orgSlug, contractId, documentVersionId, page)
      .then((result) => { if (alive) setData(result); })
      .catch(() => { if (alive) setLoadError(true); });
    return () => { alive = false; };
  }, [contractId, documentVersionId, orgSlug, page]);

  // Vorschau: wie der Wert gespeichert würde (oder warum nicht) – nichts wird gespeichert.
  useEffect(() => {
    setPreview(null);
    const trimmed = quote.trim();
    if (!trimmed || !field) return;
    let alive = true;
    const timer = window.setTimeout(() => {
      previewDocumentCapture(orgSlug, contractId, { field_key: field, document_version_id: documentVersionId, page, quote: trimmed })
        .then((result) => { if (alive) setPreview({ ok: true, text: result.preview }); })
        .catch((err) => { if (alive) setPreview({ ok: false, text: message(err, "Die Stelle konnte nicht gelesen werden.") }); });
    }, 300);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [contractId, documentVersionId, field, orgSlug, page, quote]);

  function takeSelection() {
    const selection = window.getSelection();
    const container = textRef.current;
    if (!selection || !container || selection.isCollapsed) return;
    const anchor = selection.anchorNode;
    if (anchor && container.contains(anchor)) setQuote(selection.toString().trim());
  }

  async function save() {
    setBusy(true);
    try {
      await captureFromDocument(orgSlug, contractId, { field_key: field, document_version_id: documentVersionId, page, quote: quote.trim() });
      const label = data?.fields.find((item) => item.key === field)?.label ?? "Angabe";
      toast(`${label} aus Seite ${page} übernommen${preview?.ok ? `: ${preview.text}` : ""}.`, "success");
      setQuote("");
      onSaved();
    } catch (err) {
      setPreview({ ok: false, text: message(err, "Die Angabe konnte nicht übernommen werden.") });
    } finally {
      setBusy(false);
    }
  }

  return <section className="cw-section source-capture" aria-labelledby="source-capture-heading">
    <div className="cw-section-head">
      <div>
        <h2 id="source-capture-heading">Angabe aus dem Text übernehmen</h2>
        <p>Markieren Sie die Stelle im Text von Seite {page}. Der Wert wird daraus gelesen und mit dieser Fundstelle gespeichert.</p>
      </div>
      <Button size="sm" onClick={onClose}>Schließen</Button>
    </div>
    {loadError ? <InlineAlert tone="critical" role="alert">Der Text dieser Seite konnte nicht geladen werden.</InlineAlert> : null}
    {!data && !loadError ? <p className="cw-muted" role="status">Text wird geladen…</p> : null}
    {data && data.text === null ? <p className="cw-muted">Für Seite {page} liegt kein gelesener Text vor. Mit „Erneut erfassen …“ und „Dokument neu lesen“ lässt sich das Dokument neu lesen.</p> : null}
    {data?.text ? <>
      <div
        ref={textRef}
        className="source-capture-text"
        role="region"
        aria-label={`Text der Seite ${page}, so wie MedFlux ihn gelesen hat`}
        tabIndex={0}
        onMouseUp={takeSelection}
        onKeyUp={takeSelection}
      >{data.text}</div>
      <div className="source-capture-form">
        <label className="field">
          <span className="field-label">Markierte Stelle (wörtlich)</span>
          <textarea rows={2} value={quote} onChange={(event) => setQuote(event.target.value)} placeholder="Text oben markieren oder hier einfügen" />
        </label>
        <label className="field">
          <span className="field-label">Übernehmen als</span>
          <select value={field} onChange={(event) => setField(event.target.value)}>
            <option value="">Feld wählen …</option>
            {data.fields.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
        {preview ? <InlineAlert tone={preview.ok ? "info" : "warning"} role="status">{preview.ok ? `Wird gespeichert als: ${preview.text}` : preview.text}</InlineAlert> : null}
        <div className="reextraction-actions">
          <Button variant="primary" onClick={save} loading={busy} loadingLabel="Wird übernommen…" disabled={!preview?.ok}>Übernehmen</Button>
        </div>
      </div>
    </> : null}
  </section>;
}
