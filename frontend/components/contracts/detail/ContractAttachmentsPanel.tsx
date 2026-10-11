"use client";

import Dialog from "@/components/ui/Dialog";
import StatusBadge from "@/components/ui/StatusBadge";
import Signal from "@/components/ui/Signal";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
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
  const [attachmentType, setAttachmentType] = useState("nachtrag");
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

  return <section className="cw-section" aria-labelledby="attachments-heading">
    <div className="cw-section-head"><div><h2 id="attachments-heading">Dokumente zum Vertrag</h2><p>Hauptdokument, Nachträge, Kündigungen und weitere Anlagen. Analysierte Nachträge erzeugen nur Vorschläge in den Stammdaten.</p></div></div>
    {editable ? <form className="rg-transition" aria-label="Dokument hinzufügen" onSubmit={(event) => { event.preventDefault(); void upload(); }}>
      <div className="rg-form-grid">
        <label>Dateien (PDF/DOCX)<input ref={fileInput} type="file" multiple accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></label>
        <label>Dokumentart<select value={attachmentType} onChange={(event) => setAttachmentType(event.target.value)}>{(types.length ? types : [{ id: "n", code: "nachtrag", label: "Nachtrag" } as LookupDto]).map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
        <label>Bezeichnung (optional)<input value={title} maxLength={255} disabled={files.length > 1} onChange={(event) => setTitle(event.target.value)} /></label>
        <label className="rg-check"><input type="checkbox" checked={analyze} disabled={!ANALYZABLE.has(attachmentType)} onChange={(event) => setAnalyze(event.target.checked)} />Mit lokaler KI analysieren und Änderungen vorschlagen</label>
      </div>
      <div className="rg-actions"><button type="submit" className="btn btn-primary" disabled={busy || files.length === 0}>{busy ? "Wird verarbeitet…" : "Hinzufügen"}</button></div>
    </form> : null}
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {results.length > 0 ? <ul className="rg-explanation" aria-label="Ergebnis des Uploads">{results.map((item) => <li key={`${item.original_filename}-${item.document_version_id}`}><strong>{item.original_filename}</strong>: {item.message ?? item.status}</li>)}</ul> : null}
    {items === null ? <p role="status">Dokumente werden geladen…</p> : items.length === 0 ? <p className="cw-muted">Noch keine Dokumente.</p> : <div className="table-scroll"><table className="rg-table">
      <thead><tr><th scope="col">Bezeichnung</th><th scope="col">Art</th><th scope="col">Hinzugefügt</th><th scope="col">Status</th>{editable ? <th scope="col"><span className="sr-only">Aktionen</span></th> : null}</tr></thead>
      <tbody>{items.map((item) => <tr key={item.link_id} className={item.is_valid ? undefined : "rg-inactive"}>
        <th scope="row">{item.title}{item.title !== item.original_filename ? <span className="contract-business-status">{item.original_filename}</span> : null}</th>
        <td>{editable ? <select aria-label={`Dokumentart von ${item.title}`} value={item.attachment_type ?? ""} disabled={busy} onChange={(event) => void update(item, { attachment_type: event.target.value })}><option value="" disabled>Ohne Art</option>{types.map((type) => <option key={type.id} value={type.code}>{type.label}</option>)}</select> : label(item.attachment_type)}</td>
        <td>{item.added_at ? timestamp.format(new Date(item.added_at)) : "–"}{item.added_by_name ? ` · ${item.added_by_name}` : ""}</td>
        <td>{item.is_main ? <StatusBadge label="Hauptdokument" tone="information" /> : null}{!item.is_valid ? <Signal tone="warning">Ungültig</Signal> : null}</td>
        {editable ? <td><span className="rg-actions">
          {!item.is_main && item.is_valid ? <button type="button" className="rg-link" disabled={busy} onClick={() => void update(item, { is_main: true })}>Als Hauptdokument</button> : null}
          {!item.is_main ? <button type="button" className="rg-link" disabled={busy} onClick={() => void update(item, { is_valid: !item.is_valid })}>{item.is_valid ? "Ungültig setzen" : "Wieder gültig"}</button> : null}
          {item.is_main
            ? <span className="cw-muted" title="Zuerst ein anderes Dokument als Hauptdokument festlegen.">Hauptdokument kann nicht entfernt werden</span>
            : <button type="button" className="rg-link" disabled={busy} onClick={() => { setReason(""); setRemoving(item); }} aria-label={`${item.title} entfernen`}>Entfernen</button>}
        </span></td> : null}
      </tr>)}</tbody>
    </table></div>}
    {removed.length ? <details className="removed-documents">
      <summary>Entfernte Dokumente ({removed.length})</summary>
      <ul>{removed.map((item) => <li key={item.removed_id}>
        <span><strong>{item.title}</strong> · {label(item.attachment_type)} · entfernt {item.removed_at ? timestamp.format(new Date(item.removed_at)) : ""}{item.removed_by_name ? ` von ${item.removed_by_name}` : ""}{item.reason ? ` – „${item.reason}“` : ""}</span>
        {editable ? <button type="button" className="rg-link" disabled={busy} onClick={() => void change(() => restoreContractDocument(orgSlug, contractId, item.removed_id), "Wiederherstellen fehlgeschlagen.")} aria-label={`${item.title} wiederherstellen`}>Wiederherstellen</button> : null}
      </li>)}</ul>
    </details> : null}
    <Dialog open={removing !== null} title="Dokument entfernen?" onClose={() => setRemoving(null)}
      description={removing ? <>„{removing.title}“ wird aus diesem Vertrag entfernt. Die Datei und der Verlauf bleiben erhalten; unter „Entfernte Dokumente“ lässt es sich wiederherstellen.</> : null}
      actions={<><button type="button" className="btn" onClick={() => setRemoving(null)}>Abbrechen</button><button type="button" className="btn btn-danger" disabled={busy} onClick={() => void confirmRemove()}>{busy ? "Wird entfernt…" : "Entfernen"}</button></>}>
      <label className="field">Grund (optional)<input value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} placeholder="z. B. falsch zugeordnet" /></label>
    </Dialog>
  </section>;
}
