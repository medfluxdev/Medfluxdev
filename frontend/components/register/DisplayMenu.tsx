"use client";

import Popover from "@/components/ui/Popover";
import type { GridColumn, GridSpec } from "@/lib/domain-api/registerGrid";
import { sameList } from "./register-state";

type Props = {
  columns: GridColumn[];
  spec: GridSpec;
  standard: string[];
  onToggleColumn: (key: string) => void;
  onColumns: (keys: string[]) => void;
  onGroup: (level: 0 | 1, key: string) => void;
};

// Spalten und Gruppierung: ändern nur die Darstellung, nie die Treffermenge.
export default function DisplayMenu({ columns, spec, standard, onToggleColumn, onColumns, onGroup }: Props) {
  const groupable = columns.filter((item) => item.groupable);
  return <Popover label="Darstellung" panelLabel="Darstellung" align="end" wide>
    <div className="reg-display">
      <fieldset className="reg-columns">
        <legend>Spalten ({spec.columns.length})</legend>
        <div className="reg-columns-list">
          {columns.map((item) => <label key={item.key} className="rg-check"><input type="checkbox" checked={spec.columns.includes(item.key)} onChange={() => onToggleColumn(item.key)} />{item.label}</label>)}
        </div>
        <button type="button" className="btn btn-sm" disabled={sameList(spec.columns, standard)} onClick={() => onColumns(standard)}>Standardspalten</button>
      </fieldset>
      <div className="reg-grouping">
        <label>Gruppieren nach<select value={spec.group_by[0] ?? ""} onChange={(event) => onGroup(0, event.target.value)}>
          <option value="">Keine Gruppierung</option>
          {groupable.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select></label>
        {spec.group_by[0] ? <label>danach<select value={spec.group_by[1] ?? ""} onChange={(event) => onGroup(1, event.target.value)}>
          <option value="">–</option>
          {groupable.filter((item) => item.key !== spec.group_by[0]).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select></label> : null}
      </div>
    </div>
  </Popover>;
}
