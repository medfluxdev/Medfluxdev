"use client";

import { useEffect, useId, useState } from "react";
import Popover from "@/components/ui/Popover";
import { getGridValues, type GridColumn, type GridFilter, type GridSpec, type TreeHospital } from "@/lib/domain-api/registerGrid";
import { areaSelection, inValues, quickLabel, setArea, setInValues } from "./register-state";

export interface ValueOption {
  value: string;
  label: string;
  count?: number;
}

// Mehrfachauswahl als Kästchenliste; ab neun Einträgen mit Suchfeld.
export function ValueChecklist({ legend, options, selected, onChange, loading = false, hideLegend = false }: {
  legend: string;
  options: ValueOption[] | null;
  selected: string[];
  onChange: (values: string[]) => void;
  loading?: boolean;
  hideLegend?: boolean;
}) {
  const [needle, setNeedle] = useState("");
  const searchId = useId();
  // Gewählte Werte, die gerade nicht vorkommen (z. B. aus einem Link), bleiben abwählbar.
  const all: ValueOption[] = [...(options ?? []), ...selected.filter((value) => !(options ?? []).some((item) => item.value === value)).map((value) => ({ value, label: value || "(ohne)" }))];
  const term = needle.trim().toLocaleLowerCase("de");
  const visible = term ? all.filter((item) => item.label.toLocaleLowerCase("de").includes(term)) : all;
  return <fieldset className="reg-checklist">
    <legend className={hideLegend ? "visually-hidden" : undefined}>{legend}</legend>
    {all.length > 8 ? <>
      <label htmlFor={searchId} className="visually-hidden">{legend} durchsuchen</label>
      <input id={searchId} type="search" placeholder="Suchen…" value={needle} onChange={(event) => setNeedle(event.target.value)} />
    </> : null}
    {loading || options === null ? <p role="status" className="cw-muted">Werte werden geladen…</p>
      : all.length === 0 ? <p className="cw-muted">Keine Werte vorhanden.</p>
        : <div className="reg-checklist-items">
          {visible.map((item) => <label key={item.value} className="rg-check">
            <input
              type="checkbox"
              checked={selected.includes(item.value)}
              onChange={(event) => onChange(event.target.checked ? [...selected, item.value] : selected.filter((value) => value !== item.value))}
            />
            {item.label}{item.count ? <span className="cw-muted"> ({item.count})</span> : null}
          </label>)}
          {visible.length === 0 ? <p className="cw-muted">Kein Eintrag passt zur Suche.</p> : null}
        </div>}
    {selected.length ? <button type="button" className="rg-link" onClick={() => onChange([])}>Auswahl aufheben</button> : null}
  </fieldset>;
}

/** Werte einer Spalte vom Server (im sichtbaren Bereich, unter den übrigen Filtern), mit Anzahl. */
export function RemoteChecklist({ organizationSlug, column, legend, spec, onFilters, hideLegend }: {
  organizationSlug: string;
  column: string;
  legend: string;
  spec: GridSpec;
  onFilters: (filters: GridFilter[]) => void;
  hideLegend?: boolean;
}) {
  const [options, setOptions] = useState<ValueOption[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    setOptions(null);
    getGridValues(organizationSlug, column, spec)
      .then((result) => { if (!cancelled) setOptions(result.values); })
      .catch(() => { if (!cancelled) setOptions([]); });
    return () => { cancelled = true; };
    // Nur beim Öffnen und bei Filteränderungen anderer Spalten neu laden.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organizationSlug, column, JSON.stringify({ ...spec, columns: [], sort: null, group_by: [] })]);
  return <ValueChecklist
    legend={legend}
    hideLegend={hideLegend}
    options={options}
    selected={inValues(spec.filters, column)}
    onChange={(values) => onFilters(setInValues(spec.filters, column, values))}
  />;
}

export function StatusFilter({ column, spec, onFilters }: { column: GridColumn | undefined; spec: GridSpec; onFilters: (filters: GridFilter[]) => void }) {
  if (!column) return null;
  const selected = inValues(spec.filters, column.key);
  const labels = selected.map((value) => column.options?.find((item) => item.value === value)?.label ?? value);
  return <Popover label={quickLabel(column.label, labels)} panelLabel={`${column.label} wählen`} active={selected.length > 0}>
    <ValueChecklist
      legend={column.label}
      hideLegend
      options={column.options ?? []}
      selected={selected}
      onChange={(values) => onFilters(setInValues(spec.filters, column.key, values))}
    />
  </Popover>;
}

export function PartnerFilter({ organizationSlug, column, spec, onFilters }: {
  organizationSlug: string;
  column: GridColumn | undefined;
  spec: GridSpec;
  onFilters: (filters: GridFilter[]) => void;
}) {
  if (!column) return null;
  const selected = inValues(spec.filters, column.key);
  return <Popover label={quickLabel(column.label, selected.map((value) => value || "(ohne)"))} panelLabel={`${column.label} wählen`} active={selected.length > 0}>
    <RemoteChecklist organizationSlug={organizationSlug} column={column.key} legend={column.label} hideLegend spec={spec} onFilters={onFilters} />
  </Popover>;
}

function areaText({ hospitals, departments }: { hospitals: string[]; departments: string[] }) {
  const name = (value: string, fallback: string) => value || fallback;
  if (!hospitals.length && !departments.length) return [];
  const hospital = hospitals.map((value) => name(value, "ohne Krankenhaus")).join(", ");
  const department = departments.map((value) => name(value, "ohne Abteilung")).join(", ");
  return [hospital && department ? `${hospital} › ${department}` : hospital || department];
}

/**
 * Krankenhaus und Abteilung mit Anzahl – ersetzt den früheren Baum neben der Liste.
 * Die Auswahl gilt innerhalb des oben gewählten Krankenhaus-Bereichs.
 */
export function AreaFilter({ tree, spec, onFilters }: { tree: TreeHospital[]; spec: GridSpec; onFilters: (filters: GridFilter[]) => void }) {
  const selection = areaSelection(spec.filters);
  const current = (hospital: string, department?: string) =>
    selection.hospitals.length === 1 && selection.hospitals[0] === hospital
    && (department === undefined ? selection.departments.length === 0 : selection.departments.length === 1 && selection.departments[0] === department);
  const none = !selection.hospitals.length && !selection.departments.length;
  return <Popover label={quickLabel("Abteilung", areaText(selection))} panelLabel="Krankenhaus und Abteilung wählen" active={!none}>
    {(close) => {
      const pick = (hospital: string | null, department?: string) => { onFilters(setArea(spec.filters, hospital, department)); close(); };
      return <ul className="reg-area">
        <li><button type="button" className="reg-area-option" aria-pressed={none} onClick={() => pick(null)}>Alle Bereiche</button></li>
        {tree.length === 0 ? <li className="cw-muted">Keine Verträge im Bereich.</li> : null}
        {tree.map((hospital) => {
          const value = hospital.hospital ?? "";
          return <li key={value}>
            <button type="button" className="reg-area-option reg-area-hospital" aria-pressed={current(value)} onClick={() => pick(value)}>
              {hospital.label} <span className="cw-muted">({hospital.count})</span>
            </button>
            <ul>{hospital.departments.map((department) => {
              const departmentValue = department.department ?? "";
              return <li key={departmentValue}>
                <button type="button" className="reg-area-option" aria-pressed={current(value, departmentValue)} onClick={() => pick(value, departmentValue)}>
                  {department.label} <span className="cw-muted">({department.count})</span>
                </button>
              </li>;
            })}</ul>
          </li>;
        })}
      </ul>;
    }}
  </Popover>;
}
