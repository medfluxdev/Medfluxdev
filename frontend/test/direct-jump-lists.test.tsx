import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RegisterTable from "@/components/register/RegisterTable";
import { notEvaluableLink, registerHref, NOT_EVALUABLE_FILTERS } from "@/lib/fix-targets";
import type { GridColumn, GridResponse, GridSpec } from "@/lib/domain-api/registerGrid";

const COLUMNS: GridColumn[] = [
  { key: "register_number", label: "Nr.", type: "text", default: true, groupable: false },
  { key: "short_description", label: "Kurzbeschreibung", type: "text", default: true, groupable: false },
  { key: "term_status", label: "Laufzeitangaben", type: "enum", default: false, groupable: true },
];

function table(filters: GridSpec["filters"]) {
  const spec: GridSpec = { columns: COLUMNS.map((item) => item.key), filters, sort: null, group_by: [], q: null, include_deleted: false };
  const data: GridResponse = {
    as_of: "2026-10-11", spec, total: 1, groups: [], totals: { count: 1, sums: {} },
    items: [{ contract_id: "c-1", values: { register_number: "000004", short_description: "Wartung MRT", term_status: "Unvollständig" }, group: [] }],
  };
  render(<RegisterTable data={data} spec={spec} shown={COLUMNS} columnByKey={new Map(COLUMNS.map((item) => [item.key, item]))}
    archiveMode={false} reviewMode={false} canRestore={false} busyRow={null} onSort={() => undefined} onRestore={() => undefined} onPreview={() => undefined} />);
  return screen.getByRole("table");
}

describe("Direkt zur Stelle: Listen", () => {
  it("führt bei genau einem nicht bewertbaren Vertrag direkt in dessen Laufzeitangaben", () => {
    expect(notEvaluableLink([{ contract_id: "c-1" }])).toBe("/contracts/c-1?tab=register&abschnitt=term");
    expect(notEvaluableLink([{ contract_id: "c-1" }, { contract_id: "c-2" }])).toBe(registerHref(NOT_EVALUABLE_FILTERS));
  });

  it("Vertragsname öffnet die Übersicht – auch in gefilterten Listen; „Unvollständig“ führt zu den Laufzeitangaben", () => {
    const filtered = table([{ column: "cost_current_year", op: "empty" }]);
    // Der Vertragsname öffnet immer die Übersicht; die Aktion in der Zeile führt zur Stelle.
    expect(within(filtered).getByRole("link", { name: "Wartung MRT" })).toHaveAttribute("href", "/contracts/c-1");
    expect(within(filtered).getByRole("link", { name: "Laufzeitangaben von Wartung MRT ergänzen" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=term");
  });

  it("ohne Filter öffnet der Vertrag ebenfalls die Übersicht", () => {
    const plain = table([]);
    expect(within(plain).getByRole("link", { name: "Wartung MRT" })).toHaveAttribute("href", "/contracts/c-1");
  });
});
