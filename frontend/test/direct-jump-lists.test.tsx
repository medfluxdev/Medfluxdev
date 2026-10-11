import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RegisterTable from "@/components/register/RegisterTable";
import { listRowTarget, notEvaluableLink, registerHref, NOT_EVALUABLE_FILTERS } from "@/lib/fix-targets";
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
  it("öffnet Verträge aus einer nach Lücken gefilterten Liste dort, wo die Lücke behoben wird", () => {
    expect(listRowTarget([])).toEqual({ tab: "register" });
    expect(listRowTarget([{ column: "cost_current_year", op: "empty" }])).toEqual({ tab: "finance", section: "entries" });
    expect(listRowTarget([{ column: "responsible", op: "empty" }])).toEqual({ tab: "register", section: "ownership" });
    expect(listRowTarget([{ column: "cancel_by", op: "within_days", value: 90 }, { column: "reminder_recipient", op: "empty" }])).toEqual({ tab: "register", field: "reminder_recipient_account_id" });
    expect(listRowTarget(NOT_EVALUABLE_FILTERS)).toEqual({ tab: "register", section: "term" });
    expect(listRowTarget([{ column: "review_pending", op: "is", value: true }])).toEqual({ tab: "documents", subtab: "review" });
    expect(listRowTarget([{ column: "deletion_from", op: "overdue" }])).toEqual({ tab: "register", section: "protection" });
  });

  it("führt bei genau einem nicht bewertbaren Vertrag direkt in dessen Laufzeitangaben", () => {
    expect(notEvaluableLink([{ contract_id: "c-1" }])).toBe("/contracts/c-1?tab=register&abschnitt=term");
    expect(notEvaluableLink([{ contract_id: "c-1" }, { contract_id: "c-2" }])).toBe(registerHref(NOT_EVALUABLE_FILTERS));
  });

  it("Tabellenzeilen folgen dem Filter; „Unvollständig“ führt zu den Laufzeitangaben", () => {
    const filtered = table([{ column: "cost_current_year", op: "empty" }]);
    expect(within(filtered).getByRole("link", { name: "Wartung MRT" })).toHaveAttribute("href", "/contracts/c-1?tab=finance&abschnitt=entries");
    expect(within(filtered).getByRole("link", { name: "Laufzeitangaben von Wartung MRT ergänzen" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=term");
  });

  it("ohne Lückenfilter bleibt der Link wie bisher bei den Vertragsdaten", () => {
    const plain = table([]);
    expect(within(plain).getByRole("link", { name: "Wartung MRT" })).toHaveAttribute("href", "/contracts/c-1?tab=register");
  });
});
