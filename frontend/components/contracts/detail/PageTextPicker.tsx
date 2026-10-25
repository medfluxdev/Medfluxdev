"use client";

import { useEffect, useRef, useState } from "react";
import { getDocumentPageText } from "@/lib/domain-api/register";

/**
 * Seitentext, wie MedFlux ihn gelesen hat: eine Stelle markieren und als Wert übernehmen.
 * Start ist die Seite des Belegs; man kann auf jede gelesene Seite (und bei mehreren Dokumenten in ein anderes Dokument) wechseln,
 * denn die passende Stelle steht nicht immer dort, wo die KI gesucht hat.
 */
export default function PageTextPicker({ contractId, orgSlug, documentVersionId, page, onPick, documents }: {
  contractId: string; orgSlug: string; documentVersionId: string; page: number; onPick: (text: string) => void;
  documents?: { id: string; label: string }[];
}) {
  const [docId, setDocId] = useState(documentVersionId);
  const [current, setCurrent] = useState(page);
  const [text, setText] = useState<string | null | undefined>(undefined);
  const [pages, setPages] = useState<number[]>([]);
  const [selection, setSelection] = useState("");
  const boxRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { setDocId(documentVersionId); setCurrent(page); }, [documentVersionId, page]);
  useEffect(() => {
    let alive = true;
    setText(undefined);
    setSelection("");
    getDocumentPageText(orgSlug, contractId, docId, current)
      .then((result) => { if (alive) { setText(result.text); setPages(result.pages ?? []); } })
      .catch(() => { if (alive) setText(null); });
    return () => { alive = false; };
  }, [contractId, orgSlug, docId, current]);
  function take() {
    const selected = window.getSelection();
    if (selected && !selected.isCollapsed && selected.anchorNode && boxRef.current?.contains(selected.anchorNode)) setSelection(selected.toString().trim());
  }
  const list = pages.length ? pages : [current];
  const at = list.indexOf(current);
  const previous = at > 0 ? list[at - 1] : null;
  const next = at >= 0 && at < list.length - 1 ? list[at + 1] : null;
  const nav = <div className="erm-picker-nav">
    {documents && documents.length > 1
      ? <select className="erm-picker-doc" aria-label="Dokument" value={docId} onChange={(event) => { setDocId(event.target.value); setCurrent(1); }}>
        {documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.label}</option>)}
      </select> : null}
    <button type="button" className="btn btn-sm" disabled={previous == null} onClick={() => previous != null && setCurrent(previous)} aria-label="Vorherige Seite">‹</button>
    <select className="erm-picker-page" aria-label="Seite" value={current} onChange={(event) => setCurrent(Number(event.target.value))}>
      {list.map((item) => <option key={item} value={item}>Seite {item}{item === page && docId === documentVersionId ? " (Beleg)" : ""}</option>)}
    </select>
    <button type="button" className="btn btn-sm" disabled={next == null} onClick={() => next != null && setCurrent(next)} aria-label="Nächste Seite">›</button>
  </div>;
  if (text === undefined) return <div className="erm-picker">{nav}<p className="erm-muted" role="status">Seitentext wird geladen …</p></div>;
  if (text === null) return <div className="erm-picker">{nav}<p className="erm-muted">Für diese Seite liegt kein gelesener Text vor.</p></div>;
  const shown = (selection.length > 30 ? `${selection.slice(0, 30)}…` : selection).replace(/\s+/g, " ");
  return <div className="erm-picker">
    {nav}
    <div ref={boxRef} className="erm-picker-text" tabIndex={0} role="document" aria-label={`Text der Seite ${current}`} onMouseUp={take} onKeyUp={take}>{text}</div>
    <button type="button" className="btn btn-sm" disabled={!selection} onClick={() => onPick(selection)}>{selection ? `„${shown}“ übernehmen` : "Text markieren"}</button>
  </div>;
}
