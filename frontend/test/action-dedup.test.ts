import { describe, expect, it } from "vitest";
import { removeWarningsRepresentedByTasks } from "@/lib/action-dedup";

describe("contract action/warning deduplication", () => {
  it("hides a warning already represented by the same task and target date", () => {
    const tasks = [{ title_de: "Manuelle Prüfung erforderlich", target_date: null }];
    const warnings = [
      { warning_type: "manual_review_required", title_de: "Manuelle Prüfung erforderlich", target_date: null },
      { warning_type: "contract_end_approaching", title_de: "Vertragsende nähert sich", target_date: "2027-01-01" },
    ];

    expect(removeWarningsRepresentedByTasks(tasks, warnings)).toEqual([warnings[1]]);
  });

  it("keeps materially different warnings and dates", () => {
    const tasks = [{ title_de: "Vertragsdaten unklar", target_date: null }];
    const warnings = [
      { warning_type: "manual_review_required", title_de: "Vertragsdaten unklar", target_date: "2027-06-01" },
      { warning_type: "contract_expired", title_de: "Vertrag ausgelaufen", target_date: "2027-06-01" },
    ];

    expect(removeWarningsRepresentedByTasks(tasks, warnings)).toEqual(warnings);
  });
});
