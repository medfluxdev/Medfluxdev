"use client";

import { useEffect, useState } from "react";
import { formatDateTime } from "@/lib/format";
import { listHistory, type HistoryEntry } from "@/lib/domain-api/history";

// Aenderungen an genau einem Stammdaten-Eintrag (Aktivitaetsprotokoll).
export default function EntityHistory({ organizationSlug, objectType, objectId }: { organizationSlug: string; objectType: string; objectId: string }) {
  const [items, setItems] = useState<HistoryEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setItems(null);
    setFailed(false);
    listHistory(organizationSlug, { object_type: objectType, object_id: objectId }, { limit: 50, offset: 0 })
      .then((page) => { if (active) setItems(page.items); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [organizationSlug, objectType, objectId]);

  if (failed) return <p className="field-hint" role="status">Der Verlauf konnte nicht geladen werden.</p>;
  if (items === null) return <p className="state-loading" role="status">Verlauf wird geladen…</p>;
  if (items.length === 0) return <p className="field-hint">Noch keine Änderungen protokolliert.</p>;
  return <ol className="md-history">
    {items.map((item) => <li key={item.id}>
      <strong>{item.label}</strong>
      <span>{item.at ? formatDateTime(item.at) : "–"} · {item.actor ?? "System"}</span>
    </li>)}
  </ol>;
}
