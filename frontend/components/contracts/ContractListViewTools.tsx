"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { createContractListView, deleteSavedView, listContractListViews, type ListViewDto } from "@/lib/domain-api/registerGrid";

type SavedView = { id: string; name: string; query: string; deletable: boolean };

// Frueher nur im Browser gespeichert; wird einmalig auf den Server uebernommen.
const LEGACY_VIEWS_KEY = "medflux.contracts.savedViews";

function fromDto(item: ListViewDto): SavedView {
  return { id: item.id, name: item.name, query: item.config.query, deletable: item.is_own };
}

function readLegacy(): { name: string; query: string }[] {
  try {
    const stored = localStorage.getItem(LEGACY_VIEWS_KEY);
    const parsed = stored ? (JSON.parse(stored) as unknown) : [];
    return Array.isArray(parsed)
      ? parsed.filter((item): item is { name: string; query: string } => typeof item?.name === "string" && typeof item?.query === "string")
      : [];
  } catch {
    return [];
  }
}

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
  const { organizationSlug } = useAuth();
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [viewName, setViewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationSlug) return;
    let cancelled = false;
    (async () => {
      try {
        const legacy = readLegacy();
        if (legacy.length > 0) {
          try { localStorage.removeItem(LEGACY_VIEWS_KEY); } catch { /* nur Komfort */ }
          try {
            for (const item of legacy) await createContractListView(organizationSlug, item.name, item.query);
          } catch (uploadError) {
            try { localStorage.setItem(LEGACY_VIEWS_KEY, JSON.stringify(legacy)); } catch { /* nur Komfort */ }
            throw uploadError;
          }
        }
        const result = await listContractListViews(organizationSlug);
        if (!cancelled) setSavedViews(result.items.map(fromDto));
      } catch {
        if (!cancelled) setError("Gespeicherte Ansichten konnten nicht geladen werden.");
      }
    })();
    return () => { cancelled = true; };
  }, [organizationSlug]);

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
  }, [searchParams]);

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

  async function saveCurrentView() {
    const name = viewName.trim();
    if (!name || !organizationSlug) return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("page");
    try {
      const created = await createContractListView(organizationSlug, name, params.toString());
      setSavedViews((current) => [...current, fromDto(created)]);
      setViewName("");
      setError(null);
    } catch {
      setError("Die Ansicht konnte nicht gespeichert werden.");
    }
  }

  function applyView(view: SavedView) {
    router.replace(`${pathname}${view.query ? `?${view.query}` : ""}`, { scroll: false });
  }

  async function deleteView(id: string) {
    if (!organizationSlug) return;
    try {
      await deleteSavedView(organizationSlug, id);
      setSavedViews((current) => current.filter((view) => view.id !== id));
    } catch {
      setError("Die Ansicht konnte nicht gelöscht werden.");
    }
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
          <button type="button" className="btn-ghost btn-sm" disabled={!viewName.trim()} onClick={() => void saveCurrentView()}>Ansicht speichern</button>
        </div>
        {savedViews.length > 0 ? (
          <div className="saved-view-list">
            {savedViews.map((view) => (
              <span key={view.id} className="saved-view-item">
                <button type="button" className="saved-view-apply" onClick={() => applyView(view)}>{view.name}</button>
                {view.deletable ? <button type="button" className="saved-view-delete" onClick={() => void deleteView(view.id)} aria-label={`Gespeicherte Ansicht ${view.name} löschen`}>×</button> : null}
              </span>
            ))}
          </div>
        ) : <span className="contract-tool-muted">Noch keine Ansichten gespeichert.</span>}
        {error ? <span role="alert" className="contract-tool-muted">{error}</span> : null}
      </div>
    </div>
  );
}