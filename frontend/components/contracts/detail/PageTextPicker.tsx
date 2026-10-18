"use client";

import { useEffect, useRef, useState } from "react";
import { getDocumentPageText } from "@/lib/domain-api/register";

/** Seitentext, wie MedFlux ihn gelesen hat: eine Stelle markieren und als Wert übernehmen. */
export default function PageTextPicker({ contractId, orgSlug, documentVersionId, page, onPick }: {
  contractId: string; orgSlug: string; documentVersionId: string; page: number; onPick: (text: string) => void;
}) {
  const [text, setText] = useState<string | null | undefined>(undefined);
  const [selection, setSelection] = useState("");
  const boxRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let alive = true;
    getDocumentPageText(orgSlug, contractId, documentVersionId, page)
      .then((result) => { if (alive) setText(result.text); })
      .catch(() => { if (alive) setText(null); });
    return () => { alive = false; };
  }, [contractId, orgSlug, documentVersionId, page]);
  function take() {
    const current = window.getSelection();
    if (current && !current.isCollapsed && current.anchorNode && boxRef.current?.contains(current.anchorNode)) setSelection(current.toString().trim());
  }
  if (text === undefined) return <p className="erm-muted" role="status">Seitentext wird geladen …</p>;
  if (text === null) return <p className="erm-muted">Für diese Seite liegt kein gelesener Text vor.</p>;
  return <div className="erm-picker">
    <div ref={boxRef} className="erm-picker-text" tabIndex={0} role="document" aria-label={`Text der Seite ${page}`} onMouseUp={take} onKeyUp={take}>{text}</div>
    <button type="button" className="btn btn-sm" disabled={!selection} onClick={() => onPick(selection)}>{selection ? `„${selection.length > 40 ? `${selection.slice(0, 40)}…` : selection}“ übernehmen` : "Text markieren"}</button>
  </div>;
}
