"use client";

import { useMemo, useState } from "react";
import type { DetailDocument } from "@/lib/contract-detail-types";

/** Ab so vielen Dokumenten steht links eine Liste statt Reitern. */
export const DOCUMENT_LIST_THRESHOLD = 5;

type FileKind = "pdf" | "word" | "excel" | "other";
const KIND_LABEL: Record<FileKind, string> = { pdf: "PDF", word: "DOCX", excel: "XLSX", other: "Datei" };
const KIND_FILTER: { value: "" | FileKind; label: string }[] = [
  { value: "", label: "Alle Typen" },
  { value: "pdf", label: "PDF" },
  { value: "word", label: "Word" },
  { value: "excel", label: "Excel" },
  { value: "other", label: "Sonstige" },
];

// Rolle der Dokumentzuordnung (Backend `register/documents.ROLE_BY_TYPE`) → Bezeichnung und Gruppe.
const ROLE_LABEL: Record<string, string> = {
  main: "Hauptdokument",
  amendment: "Nachtrag",
  price_adjustment: "Preisvereinbarung",
  sla_attachment: "Leistungsverzeichnis",
  renewal_letter: "Kündigung",
};
const GROUPS: { key: string; label: string; roles: string[] | null }[] = [
  { key: "main", label: "Hauptdokument", roles: ["main"] },
  { key: "amendments", label: "Nachträge", roles: ["amendment", "price_adjustment"] },
  { key: "terminations", label: "Kündigungen", roles: ["renewal_letter"] },
  { key: "attachments", label: "Anlagen", roles: null },
];

export function fileKind(doc: Pick<DetailDocument, "original_filename"> & { mime_type?: string | null }): FileKind {
  const name = (doc.original_filename ?? "").toLowerCase();
  const mime = doc.mime_type ?? "";
  if (mime.includes("pdf") || name.endsWith(".pdf")) return "pdf";
  if (mime.includes("word") || name.endsWith(".docx") || name.endsWith(".doc")) return "word";
  if (mime.includes("sheet") || mime.includes("excel") || name.endsWith(".xlsx") || name.endsWith(".xls")) return "excel";
  return "other";
}

/** Bezeichnung der Rolle; das erste Dokument ohne Rolle gilt als Hauptdokument, wenn es keins gibt. */
export function roleLabel(doc: DetailDocument, mainId: string | null): string {
  if (doc.role === "main" || doc.document_version_id === mainId) return ROLE_LABEL.main;
  return ROLE_LABEL[doc.role ?? ""] ?? "Anlage";
}

export function FileIcon({ doc }: { doc: Pick<DetailDocument, "original_filename"> & { mime_type?: string | null } }) {
  const kind = fileKind(doc);
  return <span className={`cw-doc-type is-${kind}`} aria-hidden="true">{kind === "pdf" ? "PDF" : kind === "word" ? "W" : kind === "excel" ? "X" : "•"}</span>;
}

const CHEVRON = <svg className="doclist-chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6" /></svg>;
const SEARCH = <svg className="doclist-search-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M11 4a7 7 0 1 1 0 14a7 7 0 1 1 0-14zM20 20l-4-4" /></svg>;

/** Viele Dokumente: Suche, Filter nach Dateityp, Sortierung, Gruppen nach Art (einklappbar). */
export default function DocumentList({ documents, selectedId, mainId, onSelect, compact = false }: {
  documents: DetailDocument[];
  selectedId: string | null;
  mainId: string | null;
  onSelect: (doc: DetailDocument) => void;
  /** Wenige Dateien: ohne Suche und Filter, nur die Gruppen. */
  compact?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"" | FileKind>("");
  const [order, setOrder] = useState<"stored" | "az" | "za">("stored");
  const [closed, setClosed] = useState<Set<string>>(new Set());

  const groups = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    const found = documents.filter((doc) => (!needle || (doc.original_filename ?? "").toLocaleLowerCase("de-DE").includes(needle)) && (!kind || fileKind(doc) === kind));
    const sorted = order === "stored" ? found : [...found].sort((a, b) => (a.original_filename ?? "").localeCompare(b.original_filename ?? "", "de") * (order === "az" ? 1 : -1));
    const isMain = (doc: DetailDocument) => doc.role === "main" || doc.document_version_id === mainId;
    return GROUPS.map((group) => ({
      ...group,
      items: sorted.filter((doc) => group.key === "main" ? isMain(doc)
        : !isMain(doc) && (group.roles ? group.roles.includes(doc.role ?? "") : !GROUPS.some((other) => other.roles?.includes(doc.role ?? "")))),
    })).filter((group) => group.items.length > 0);
  }, [documents, query, kind, order, mainId]);

  const toggle = (key: string) => setClosed((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return <nav className="doclist" aria-label="Quelldokumente">
    {compact ? null : <><label className="doclist-search">{SEARCH}<span className="visually-hidden">Dateien durchsuchen</span>
      <input type="search" placeholder="Dateien durchsuchen" value={query} onChange={(event) => setQuery(event.target.value)} />
    </label>
    <div className="doclist-filters">
      <label><span className="visually-hidden">Dateityp</span>
        <select value={kind} onChange={(event) => setKind(event.target.value as "" | FileKind)}>{KIND_FILTER.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
      </label>
      <label><span className="visually-hidden">Sortierung</span>
        <select value={order} onChange={(event) => setOrder(event.target.value as "stored" | "az" | "za")}>
          <option value="stored">Wie abgelegt</option>
          <option value="az">Name A–Z</option>
          <option value="za">Name Z–A</option>
        </select>
      </label>
    </div></>}
    {groups.length === 0 ? <p className="doclist-empty">Keine Datei passt zur Suche.</p> : groups.map((group) => {
      const open = !closed.has(group.key);
      return <section key={group.key} className="doclist-group">
        <button type="button" className="doclist-group-head" aria-expanded={open} onClick={() => toggle(group.key)}>{CHEVRON}{group.label} ({group.items.length})</button>
        {open ? <ul>{group.items.map((doc) => {
          const selected = doc.document_version_id === selectedId;
          return <li key={doc.document_version_id}>
            <button type="button" className={selected ? "is-selected" : undefined} aria-current={selected ? "true" : undefined} onClick={() => onSelect(doc)}>
              <FileIcon doc={doc} />
              <span className="doclist-text"><strong>{doc.original_filename ?? "Dokument"}</strong><small>{KIND_LABEL[fileKind(doc)]} · {roleLabel(doc, mainId)}</small></span>
            </button>
          </li>;
        })}</ul> : null}
      </section>;
    })}
  </nav>;
}
