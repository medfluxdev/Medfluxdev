"use client";

import { useState } from "react";
import type { GridColumn, GridFilter, GridSpec } from "@/lib/domain-api/registerGrid";
import FilterEditor from "./FilterEditor";
import { RemoteChecklist } from "./QuickFilters";
import { hasFilter, toggleFilter } from "./register-state";

// Häufige Bedingungen mit einem Klick. Alle bestehen aus vorhandenen Filtern des Servers;
// „ohne Ende“ fehlt bewusst: unbefristete Verträge haben kein Ende und sind nicht unvollständig.
const PRESETS: { label: string; filter: GridFilter }[] = [
  { label: "Ich bin verantwortlich", filter: { column: "responsible", op: "me" } },
  { label: "Kündbar in den nächsten 30 Tagen", filter: { column: "cancel_by", op: "within_days", value: 30 } },
  { label: "Kosten unbekannt", filter: { column: "annual_cost", op: "empty" } },
];
const MISSING: { label: string; column: string }[] = [
  { label: "Ohne Krankenhaus", column: "hospital" },
  { label: "Ohne Abteilung", column: "department" },
  { label: "Ohne Vertragspartner", column: "partner" },
  { label: "Ohne verantwortliche Person", column: "responsible" },
];

type Props = {
  organizationSlug: string;
  columns: GridColumn[];
  spec: GridSpec;
  canSeeDeleted: boolean;
  onFilters: (filters: GridFilter[]) => void;
  onIncludeDeleted: (value: boolean) => void;
  onDone: () => void;
};

function rangeOf(filters: GridFilter[], column: string) {
  const found = filters.find((item) => item.column === column && item.op === "range");
  const value = (found?.value ?? {}) as { from?: string | null; to?: string | null };
  return { from: value.from ?? "", to: value.to ?? "" };
}

export default function MoreFilters({ organizationSlug, columns, spec, canSeeDeleted, onFilters, onIncludeDeleted, onDone }: Props) {
  const known = new Set(columns.map((item) => item.key));
  const [adding, setAdding] = useState(false);
  const [cost, setCost] = useState(() => rangeOf(spec.filters, "annual_cost"));
  const costApplied = rangeOf(spec.filters, "annual_cost");
  const presets = PRESETS.filter((item) => known.has(item.filter.column));
  const missing = MISSING.filter((item) => known.has(item.column));

  function applyCost(next: { from: string; to: string } | null) {
    const rest = spec.filters.filter((item) => !(item.column === "annual_cost" && item.op === "range"));
    onFilters(next && (next.from.trim() || next.to.trim())
      ? [...rest, { column: "annual_cost", op: "range", value: { from: next.from.trim() || null, to: next.to.trim() || null } }]
      : rest);
    if (!next) setCost({ from: "", to: "" });
  }

  function toggle(label: string, filter: GridFilter) {
    return <button key={label} type="button" className="btn btn-sm reg-preset" aria-pressed={hasFilter(spec.filters, filter)} onClick={() => onFilters(toggleFilter(spec.filters, filter))}>
      {label}
    </button>;
  }

  return <div className="reg-more">
    {presets.length ? <section className="reg-more-section" aria-labelledby="reg-more-quick">
      <h3 id="reg-more-quick">Schnellauswahl</h3>
      <div className="reg-presets">{presets.map((item) => toggle(item.label, item.filter))}</div>
    </section> : null}

    {missing.length ? <section className="reg-more-section" aria-labelledby="reg-more-missing">
      <h3 id="reg-more-missing">Fehlende Angaben</h3>
      <div className="reg-presets">{missing.map((item) => toggle(item.label, { column: item.column, op: "empty" }))}</div>
    </section> : null}

    {known.has("contract_type") ? <section className="reg-more-section">
      <RemoteChecklist organizationSlug={organizationSlug} column="contract_type" legend="Vertragstyp" spec={spec} onFilters={onFilters} />
    </section> : null}

    {known.has("annual_cost") ? <section className="reg-more-section" aria-labelledby="reg-more-cost">
      <h3 id="reg-more-cost">Jährliche Kosten (netto)</h3>
      <form className="reg-range" onSubmit={(event) => { event.preventDefault(); applyCost(cost); }}>
        <label>Von (€)<input inputMode="decimal" value={cost.from} onChange={(event) => setCost((current) => ({ ...current, from: event.target.value }))} /></label>
        <label>Bis (€)<input inputMode="decimal" value={cost.to} onChange={(event) => setCost((current) => ({ ...current, to: event.target.value }))} /></label>
        <button type="submit" className="btn btn-sm">Übernehmen</button>
        {costApplied.from || costApplied.to ? <button type="button" className="btn btn-sm" onClick={() => applyCost(null)}>Kostenbereich entfernen</button> : null}
      </form>
      <p className="field-hint">Verträge ohne gepflegte Kosten fallen bei einem Bereich heraus; sie zeigt „Kosten unbekannt“.</p>
    </section> : null}

    <section className="reg-more-section" aria-labelledby="reg-more-other">
      <h3 id="reg-more-other">Weitere Bedingung</h3>
      {adding
        ? <FilterEditor organizationSlug={organizationSlug} columns={columns} spec={spec} onCancel={() => setAdding(false)} onApply={(filter) => { onFilters([...spec.filters, filter]); setAdding(false); }} />
        : <button type="button" className="btn btn-sm" onClick={() => setAdding(true)}>Bedingung hinzufügen</button>}
    </section>

    {canSeeDeleted ? <section className="reg-more-section" aria-labelledby="reg-more-advanced">
      <h3 id="reg-more-advanced">Erweitert</h3>
      <label className="rg-check"><input type="checkbox" checked={spec.include_deleted} onChange={(event) => onIncludeDeleted(event.target.checked)} />Stornierte einbeziehen</label>
    </section> : null}

    <div className="rg-actions"><button type="button" className="btn btn-primary" onClick={onDone}>Fertig</button></div>
  </div>;
}
