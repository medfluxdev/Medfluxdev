import { describe, expect, it } from "vitest";
import { deadlineOrigin } from "@/lib/deadline-origin";

describe("Herkunft eines Termins", () => {
  it("berechnete Termine führen zur Angabe, aus der sie entstehen", () => {
    expect(deadlineOrigin({ contract_id: "c1", source: "system", system_key: "cancel_by" }).href).toBe("/contracts/c1?tab=register&feld=notice_period");
    expect(deadlineOrigin({ contract_id: "c1", source: "system", system_key: "maintenance_due" }).href).toBe("/contracts/c1?tab=register&feld=maintenance_next_date");
    expect(deadlineOrigin({ contract_id: "c1", source: "system", system_key: "payment_due" }).href).toBe("/contracts/c1?tab=finance");
    expect(deadlineOrigin({ contract_id: "c1", source: "system", system_key: "retention_review" }).href).toBe("/contracts/c1?tab=register&abschnitt=retention");
  });

  it("manuelle Termine führen zu Fristen & Aufgaben des Vertrags", () => {
    const origin = deadlineOrigin({ contract_id: "c2", source: "manual", system_key: null });
    expect(origin.href).toBe("/contracts/c2?tab=deadlines");
    expect(origin.label).toBe("Fristen & Aufgaben des Vertrags");
  });
});
