"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { listContracts } from "@/lib/domain-api/contracts";
import { uploadContractDocuments, type UploadResultDto } from "@/lib/domain-api/contractDocuments";
import type { ContractListItem } from "@/lib/contract-types";

const ANALYZABLE = new Set(["vertrag", "nachtrag", "addendum", "vertragsanpassung", "verguetungsvereinbarung", "leistungskatalog", "avv", "kuendigung", "kuendigungsbestaetigung", "aufhebung"]);

export default function AttachToExistingContract({ organizationSlug }: { organizationSlug: string }) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<ContractListItem[]>([]);
  const [contractId, setContractId] = useState("");
  const [types, setTypes] = useState<LookupDto[]>([]);
  const [attachmentType, setAttachmentType] = useState("nachtrag");
  const [analyze, setAnalyze] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResultDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listLookups(organizationSlug, "attachment_type").then((data) => setTypes(data.items)).catch(() => setTypes([]));
  }, [organizationSlug]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      listContracts(organizationSlug, { q: query.trim(), page_size: 25 })
        .then((data) => setOptions(data.items))
        .catch(() => setOptions([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [organizationSlug, query]);

  async function submit() {
    if (!contractId || files.length === 0) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await uploadContractDocuments(organizationSlug, contractId, { files, attachmentType, analyze: analyze && ANALYZABLE.has(attachmentType) }));
      setFiles([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return <form className="import-assignment-card" aria-label="Zu bestehendem Vertrag hinzufügen" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <p>Nachträge, Kündigungen oder weitere Anlagen einem vorhandenen Vertrag zuordnen. Die KI-Analyse ändert keine Werte, sondern erzeugt Vorschläge in den Stammdaten.</p>
    <label>Vertrag suchen<input type="search" value={query} placeholder="Nummer, Titel oder Lieferant" onChange={(event) => setQuery(event.target.value)} /></label>
    <label>Vertrag
      <select value={contractId} required onChange={(event) => setContractId(event.target.value)}>
        <option value="">Bitte auswählen</option>
        {options.map((item) => <option key={item.contract_id} value={item.contract_id}>{item.register_number ?? item.contract_number ?? "–"} · {item.contract_title ?? item.supplier ?? "Vertrag"}</option>)}
      </select>
    </label>
    <label>Dokumentart
      <select value={attachmentType} onChange={(event) => setAttachmentType(event.target.value)}>
        {(types.length ? types : [{ id: "n", code: "nachtrag", label: "Nachtrag" } as LookupDto]).map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}
      </select>
    </label>
    <label>Dateien (PDF/DOCX)<input type="file" multiple accept=".pdf,.docx" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} /></label>
    <label className="rg-check"><input type="checkbox" checked={analyze && ANALYZABLE.has(attachmentType)} disabled={!ANALYZABLE.has(attachmentType)} onChange={(event) => setAnalyze(event.target.checked)} />Mit lokaler KI analysieren und Änderungen vorschlagen</label>
    <div className="import-actions"><button type="submit" className="btn btn-primary" disabled={busy || !contractId || files.length === 0}>{busy ? "Wird verarbeitet…" : `Hinzufügen (${files.length})`}</button></div>
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {result ? <div role="status">
      <ul className="rg-explanation">{result.results.map((item) => <li key={`${item.original_filename}-${item.document_version_id}`}><strong>{item.original_filename}</strong>: {item.message ?? item.status}</li>)}</ul>
      <Link href={`/contracts/${contractId}?tab=${result.results.some((item) => item.requires_review) ? "register" : "documents"}`} className="btn">Vertrag öffnen</Link>
    </div> : null}
  </form>;
}
