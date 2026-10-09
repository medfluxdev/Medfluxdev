"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { usePermissions } from "@/lib/use-permissions";

// Ein Einstieg für neue Verträge: Dokument importieren oder ohne Dokument anlegen.
export default function AddContractMenu() {
  const { can } = usePermissions();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); button.current?.focus(); }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onPointer); document.removeEventListener("keydown", onKey); };
  }, [open]);

  if (!can("contract.create")) return null;
  return <div className="add-contract" ref={root}>
    <button ref={button} type="button" className="btn btn-primary" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen((value) => !value)}>
      Vertrag hinzufügen <span aria-hidden="true">▾</span>
    </button>
    {open ? <ul id={menuId} className="add-contract-menu">
      <li><Link href="/import" onClick={() => setOpen(false)}><strong>Dokument importieren</strong><span>PDF oder DOCX – die lokale KI liest die Angaben aus</span></Link></li>
      <li><Link href="/contracts/new" onClick={() => setOpen(false)}><strong>Ohne Dokument anlegen</strong><span>Angaben von Hand erfassen, Dokument später ergänzen</span></Link></li>
    </ul> : null}
  </div>;
}
