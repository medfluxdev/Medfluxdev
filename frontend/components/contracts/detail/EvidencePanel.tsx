"use client";

import { useDeferredValue, useEffect, useState, type ReactNode } from "react";
import type { EvidenceRef } from "@/lib/contract-detail-types";
import type { EvidenceRow } from "@/lib/evidence";
import EvidenceTable, { EvidenceFilterInline, NO_FILTER, matchesFilter, type EvidenceFilter } from "./EvidenceTable";

/**
 * Seitenleiste „Nachweise“: Filter und Liste in einem eigenen Baustein, der den Filterstand selbst hält. So rendert eine
 * Eingabe oder Auswahl nur diese Leiste neu – nicht die ganze Vertragsakte samt PDF-Ansicht. Die Auswahlfelder reagieren
 * sofort; die Liste folgt über einen zurückgestellten Wert und springt bei jeder Änderung nach oben.
 */
export default function EvidencePanel({ rows, currentId, onPick, searchOpen, onSearchOpen, onQueryActive, children }: {
  rows: EvidenceRow[];
  currentId: string | null;
  onPick: (ref: EvidenceRef) => void;
  searchOpen: boolean;
  onSearchOpen: (open: boolean) => void;
  /** Meldet nur, ob ein Suchtext besteht (für den Punkt an der Lupe), nicht jeden Tastendruck. */
  onQueryActive: (active: boolean) => void;
  /** Zusätzliche Quellen unter der Liste. */
  children?: ReactNode;
}) {
  const [filter, setFilter] = useState<EvidenceFilter>(NO_FILTER);
  const deferred = useDeferredValue(filter);
  const hasQuery = Boolean(filter.query);
  useEffect(() => onQueryActive(hasQuery), [hasQuery, onQueryActive]);

  function nextOpen() {
    const open = rows.filter((row) => row.status === "open" && matchesFilter(row, filter));
    if (open.length === 0) return;
    const at = open.findIndex((row) => row.ref.evidence_id === currentId);
    const currentNumber = rows.find((row) => row.ref.evidence_id === currentId)?.number ?? 0;
    const target = at >= 0 ? open[(at + 1) % open.length] : open.find((row) => row.number > currentNumber) ?? open[0];
    onPick(target.ref);
  }

  return <>
    <EvidenceFilterInline rows={rows} filter={filter} onFilter={setFilter} searchOpen={searchOpen} onSearchOpen={onSearchOpen} onNextOpen={nextOpen} />
    <div className="dw-panel">
      <EvidenceTable rows={rows} currentId={currentId} caption="Nachweise dieses Vertrags" onPick={onPick} filter={deferred} onFilter={setFilter} />
      {children}
    </div>
  </>;
}
