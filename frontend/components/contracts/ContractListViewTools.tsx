"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type SavedView = { id: string; name: string; query: string };

const SAVED_VIEWS_KEY = "medflux.contracts.savedViews";

const LABELS: Record<string, string> = {
  q: "Suche",
  status: "Status",
  risk: "Risiko",
  warning_type: "Warnung",
  requires_action: "Handlungsbedarf",
  requires_review: "Manuelle Prüfung",
  critical_cancellation: "Kritische Kündigungsfrist",
  automatic_renewal: "Automatische Verlängerung",
  supplier: "Lieferant",
  contract_number: "Vertragsnummer",
  currency: "Währung",
  annual_cost_min: "Kosten ab",
  annual_cost_max: "Kosten bis",
  start_date_from: "Beginn ab",
  start_date_to: "Beginn bis",
  end_date_from: "Ende ab",
  end_date_to: "Ende bis",
  cancellation_from: "Kündigung ab",
  cancellation_to: "Kündigung bis",
};

const NON_FILTER_KEYS = new Set(["sort", "direction", "page", "page_size"]);

function displayValue(key: string, value: string) {
  if (value === "true") return "Ja";
  if (value === "false") return "Nein";
  return value;
}

export default function ContractListViewTools() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [viewName, setViewName] = useState("");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(SAVED_VIEWS_KEY);
      if (stored) setSavedViews(JSON.parse(stored) as SavedView[]);
    } catch {
      setSavedViews([]);
    }
  }, []);

  const filterEntries = useMemo(() => {
    const entries: Array<{ key: string; value: string; index: number; label: string }> = [];
    const counts = new Map<string, number>();
    for (const [key, value] of searchParams.entries()) {
      if (NON_FILTER_KEYS.has(key)) continue;
      const index = counts.get(key) ?? 0;
      counts.set(key, index + 1);
      entries.push({ key, value, index, label: LABELS[key] ?? key });
    }
    return entries;
  }, [query, searchParams]);

  function navigate(params: URLSearchParams) {
    params.delete("page");
    const next = params.toString();
    router.replace(`${pathname}${next ? `?${next}` : ""}`, { scroll: false });
  }

  function removeFilter(key: string, value: string, index: number) {
    const params = new URLSearchParams(searchParams.toString());
    const values = params.getAll(key);
    const nextValues = values.filter((candidate, candidateIndex) => !(candidate === value && candidateIndex === index));
    params.delete(key);
    nextValues.forEach((candidate) => params.append(key, candidate));
    navigate(params);
  }

  function clearFilters() {
    const params = new URLSearchParams(searchParams.toString());
    [...params.keys()].forEach((key) => {
      if (!NON_FILTER_KEYS.has(key)) params.delete(key);
    });
    navigate(params);
  }

  function persist(next: SavedView[]) {
    setSavedViews(next);
    localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(next));
  }

  function saveCurrentView() {
    const name = viewName.trim();
    if (!name) return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("page");
    const next: SavedView = {
      id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`,
      name,
      query: params.toString(),
    };
    persist([...savedViews, next]);
    setViewName("");
  }

  function applyView(view: SavedView) {
    router.replace(`${pathname}${view.query ? `?${view.query}` : ""}`, { scroll: false });
  }

  function deleteView(id: string) {
    persist(savedViews.filter((view) => view.id !== id));
  }

  return (
    <div className="contract-view-tools">
      <div className="active-filter-area" aria-label="Aktive Filter">
        <span className="contract-tool-label">Aktive Filter</span>
        {filterEntries.length === 0 ? (
          <span className="contract-tool-muted">Keine Filter aktiv</span>
        ) : (
          <>
            <div className="active-filter-chips">
              {filterEntries.map((entry) => (
                <button
                  key={`${entry.key}-${entry.index}-${entry.value}`}
                  type="button"
                  className="active-filter-chip"
                  onClick={() => removeFilter(entry.key, entry.value, entry.index)}
                  aria-label={`${entry.label} ${displayValue(entry.key, entry.value)} entfernen`}
                  title="Filter entfernen"
                >
                  <span>{entry.label}: {displayValue(entry.key, entry.value)}</span>
                  <span aria-hidden="true">×</span>
                </button>
              ))}
            </div>
            <button type="button" className="btn-ghost btn-sm" onClick={clearFilters}>Filter löschen</button>
          </>
        )}
      </div>

      <div className="saved-view-area" aria-label="Gespeicherte Ansichten">
        <span className="contract-tool-label">Ansichten</span>
        <div className="saved-view-create">
          <label className="sr-text" htmlFor="saved-view-name">Name der Ansicht</label>
          <input id="saved-view-name" value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="z. B. Kritische Verträge" />
          <button type="button" className="btn-ghost btn-sm" disabled={!viewName.trim()} onClick={saveCurrentView}>Ansicht speichern</button>
        </div>
        {savedViews.length > 0 ? (
          <div className="saved-view-list">
            {savedViews.map((view) => (
              <span key={view.id} className="saved-view-item">
                <button type="button" className="saved-view-apply" onClick={() => applyView(view)}>{view.name}</button>
                <button type="button" className="saved-view-delete" onClick={() => deleteView(view.id)} aria-label={`Gespeicherte Ansicht ${view.name} löschen`}>×</button>
              </span>
            ))}
          </div>
        ) : <span className="contract-tool-muted">Noch keine lokalen Ansichten gespeichert.</span>}
      </div>
    </div>
  );
}