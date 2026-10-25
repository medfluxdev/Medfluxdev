"use client";

import Dialog from "@/components/ui/Dialog";
import StatusBadge from "@/components/ui/StatusBadge";
import Signal from "@/components/ui/Signal";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { FileIcon } from "./DocumentList";
import { contentUrl } from "@/lib/api";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import {
  listContractDocuments,
  removeContractDocument,
  restoreContractDocument,
  updateContractDocument,
  uploadContractDocuments,
  type ContractDocumentDto,
  type ContractDocumentsDto,
  type RemovedDocumentDto,
  type UploadResultDto,
} from "@/lib/domain-api/contractDocuments";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" });
const ANALYZABLE = new Set(["vertrag", "nachtrag", "addendum", "vertragsanpassung", "verguetungsvereinbarung", "leistungskatalog", "avv", "kuendigung", "kuendigungsbestaetigung", "aufhebung"]);

export default function ContractAttachmentsPanel({ contractId, orgSlug, onAnalyzed }: { contractId: string; orgSlug: string; onAnalyzed?: () => void }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [items, setItems] = useState<ContractDocumentDto[] | null>(null);
  const [removed, setRemoved] = useState<RemovedDocumentDto[]>([]);
  const [removing, setRemoving] = useState<ContractDocumentDto | null>(null);
  const [reason, setReason] = useState("");
  const [types, setTypes] = useState<LookupDto[]>([]);
  // „AVV hochladen“ (Zugriff & Datenschutz) kommt mit ?dokumentart=avv: Art vorwählen, Dateiauswahl fokussieren.
  const presetType = useSearchParams()?.get("dokumentart") ?? null;
  const [attachmentType, setAttachmentType] = useState(presetType || "nachtrag");
  const [title, setTitle] = useState("");
  const [analyze, setAnalyze] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<UploadResultDto["results"]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await listContractDocuments(orgSlug, contractId);
      setItems(data.items);
      setRemoved(data.removed ?? []);
    } catch (caught) {
      setItems([]);
      setError(caught instanceof Error ? caught.message : "Dokumente konnten nicht geladen werden.");
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (presetType && editable) { setAttachmentType(presetType); fileInput.current?.focus(); }
  }, [presetType, editable]);
  useEffect(() => {
    listLookups(orgSlug, "attachment_type").then((data) => setTypes(data.items)).catch(() => setTypes([]));
  }, [orgSlug]);

  const label = (code: string | null) => types.find((item) => item.code === code)?.label ?? code ?? "Ohne Art";

  async function upload() {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    setResults([]);
    try {
      const response = await uploadContractDocuments(orgSlug, contractId, { files, attachmentType, title: files.length === 1 ? title : undefined, analyze });
      setItems(response.items);
      setResults(response.results);
      setFiles([]);
      setTitle("");
      if (fileInput.current) fileInput.current.value = "";
      if (response.results.some((item) => item.requires_review)) onAnalyzed?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function update(item: ContractDocumentDto, values: Parameters<typeof updateContractDocument>[3]) {
    setBusy(true);
    setError(null);
    try {
      setItems((await updateContractDocument(orgSlug, contractId, item.link_id, values)).items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Änderung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function change(run: () => Promise<ContractDocumentsDto>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      const data = await run();
      setItems(data.items);
      setRemoved(data.removed ?? []);
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : fallback);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!removing) return;
    const ok = await change(() => removeContractDocument(orgSlug, contractId, removing.link_id, reason.trim()), "Dokument konnte nicht entfernt werden.");
    if (ok) { setRemoving(null); setReason(""); }
  }

  const [dragging, setDragging] = useState(false);

  return <section className="cw-section att" aria-labelledby="attachments-heading">
    <header className="att-head">
      <h2 id="attachments-heading">Dokumente zum Vertrag</h2>
      <p>Verträge, Nachträge und weitere Anlagen verwalten. Analysierte Nachträge erzeugen nur Vorschläge in den Stammdaten.</p>
    </header>
    {editable ? <form className="att-add" aria-label="Dokument hinzufügen" onSubmit={(event) => { event.preventDefault(); void upload(); }}>
      <h3>Dokument hinzufügen</h3>
      <div
        className={`att-drop${dragging ? " is-dragging" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const dropped = Array.from(event.dataTransfer.files).filter((file) => /\.(pdf|docx)$/i.test(file.name));
          if (dropped.length) setFiles(dropped);
        }}
      >
        <svg className="att-drop-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M12 17v-6 M9.5 13.5 12 11l2.5 2.5" /></svg>
        <p className="att-drop-text"><strong>PDF oder DOCX</strong> hier ablegen</p>
        <input ref={fileInput} className="sr-only" type="file" multiple aria-label="Dateien (PDF/DOCX)" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
        <button type="button" className="btn" onClick={() => fileInput.current?.click()}>Dateien auswählen</button>
        <p className="att-drop-hint">{files.length ? files.map((file) => file.name).join(", ") : "Mehrere Dateien möglich."}</p>
      </div>
      <div className="att-fields">
        <label>Dokumentart<select value={attachmentType} onChange={(event) => setAttachmentType(event.target.value)}>{(types.length ? types : [{ id: "n", code: "nachtrag", label: "Nachtrag" } as LookupDto]).map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
        <label>Bezeichnung (optional)<input value={title} maxLength={255} disabled={files.length > 1} placeholder="Bezeichnung eingeben" onChange={(event) => setTitle(event.target.value)} /></label>
      </div>
      <div className="att-submit">
        <label className="att-check"><input type="checkbox" checked={analyze} disabled={!ANALYZABLE.has(attachmentType)} onChange={(event) => setAnalyze(event.target.checked)} /><span><strong>Mit lokaler KI analysieren</strong><small>Änderungen werden als Vorschläge gespeichert.</small></span></label>
        <button type="submit" className="btn btn-primary" disabled={busy || files.length === 0}>{busy ? "Wird verarbeitet…" : "Hinzufügen"}</button>
      </div>
      <p className="att-note">Vertragsdaten bleiben bis zur Bestätigung unverändert.</p>
    </form> : null}
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {results.length > 0 ? <ul className="rg-explanation" aria-label="Ergebnis des Uploads">{results.map((item) => <li key={`${item.original_filename}-${item.document_version_id}`}><strong>{item.original_filename}</strong>: {item.message ?? item.status}</li>)}</ul> : null}
    <div className="att-list">
      <h3>Vorhandene Dokumente{items ? <span className="att-count">{items.length}</span> : null}</h3>
      {items === null ? <p role="status">Dokumente werden geladen…</p> : items.length === 0 ? <p className="cw-muted">Noch keine Dokumente.</p> : <div className="table-scroll"><table className="rg-table att-table">
        <thead><tr><th scope="col">Dokument</th><th scope="col">Art</th><th scope="col">Hinzugefügt</th><th scope="col">Aktionen</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.link_id} className={item.is_valid ? undefined : "rg-inactive"}>
          <th scope="row"><span className="att-file">
            <FileIcon doc={item} />
            <span className="att-file-main">{item.title}{item.title !== item.original_filename ? <span className="contract-business-status">{item.original_filename}</span> : null}
              <span className="att-file-badges">{item.is_main ? <StatusBadge label="Hauptdokument" tone="information" /> : null}{!item.is_valid ? <Signal tone="warning">Ungültig</Signal> : null}</span></span>
          </span></th>
          <td>{editable ? <select aria-label={`Dokumentart von ${item.title}`} value={item.attachment_type ?? ""} disabled={busy} onChange={(event) => void update(item, { attachment_type: event.target.value })}><option value="" disabled>Ohne Art</option>{types.map((type) => <option key={type.id} value={type.code}>{type.label}</option>)}</select> : label(item.attachment_type)}</td>
          <td>{item.added_at ? timestamp.format(new Date(item.added_at)) : "–"}{item.added_by_name ? ` · ${item.added_by_name}` : ""}</td>
          <td><span className="rg-actions">
            <a className="btn" href={contentUrl(contractId, item.document_version_id, orgSlug)} target="_blank" rel="noreferrer" aria-label={`${item.title} öffnen`}>Öffnen</a>
            {editable && !item.is_main && item.is_valid ? <button type="button" className="rg-link" disabled={busy} onClick={() => void update(item, { is_main: true })}>Als Hauptdokument</button> : null}
            {editable && !item.is_main ? <button type="button" className="rg-link" disabled={busy} onClick={() => void update(item, { is_valid: !item.is_valid })}>{item.is_valid ? "Ungültig setzen" : "Wieder gültig"}</button> : null}
            {editable ? (item.is_main
              ? <span className="att-locked cw-muted" title="Zuerst ein anderes Dokument als Hauptdokument festlegen."><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 11V8a5 5 0 0 1 10 0v3 M6 11h12v9H6z" /></svg>Geschützt<span className="sr-only">: Hauptdokument kann nicht entfernt werden</span></span>
              : <button type="button" className="rg-link" disabled={busy} onClick={() => { setReason(""); setRemoving(item); }} aria-label={`${item.title} entfernen`}>Entfernen</button>) : null}
          </span></td>
        </tr>)}</tbody>
      </table></div>}
    </div>
    {removed.length ? <details className="att-removed">
      <summary>Entfernte Dokumente ({removed.length})</summary>
      <ul className="removed-documents-list">{removed.map((item) => <li key={item.removed_id}>
        <span className="att-file"><FileIcon doc={item} />
          <span className="att-file-main"><strong>{item.title}</strong><span className="cw-muted">{label(item.attachment_type)} · entfernt {item.removed_at ? timestamp.format(new Date(item.removed_at)) : ""}{item.removed_by_name ? ` von ${item.removed_by_name}` : ""}{item.reason ? ` – „${item.reason}“` : ""}</span></span></span>
        {editable ? <button type="button" className="btn" disabled={busy} onClick={() => void change(() => restoreContractDocument(orgSlug, contractId, item.removed_id), "Wiederherstellen fehlgeschlagen.")} aria-label={`${item.title} wiederherstellen`}>Wiederherstellen</button> : null}
      </li>)}</ul>
    </details> : null}
    <Dialog open={removing !== null} title="Dokument entfernen?" onClose={() => setRemoving(null)}
      description={removing ? <>„{removing.title}“ wird aus diesem Vertrag entfernt. Die Datei und der Verlauf bleiben erhalten; unter „Entfernte Dokumente“ lässt es sich wiederherstellen.</> : null}
      actions={<><button type="button" className="btn" onClick={() => setRemoving(null)}>Abbrechen</button><button type="button" className="btn btn-danger" disabled={busy} onClick={() => void confirmRemove()}>{busy ? "Wird entfernt…" : "Entfernen"}</button></>}>
      <label className="field">Grund (optional)<input value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} placeholder="z. B. falsch zugeordnet" /></label>
    </Dialog>
  </section>;
}
