import { describe, expect, it } from "vitest";
import { servicesVisible } from "@/lib/contract-services";
import { SCOPE_TARGET, contractHref, normalizeTarget, sectionAnchor } from "@/lib/fix-targets";

const EMPTY = { scope_text: null, availability_percent: null, penalty_terms: null };

describe("Leistungen & SLA: Sichtbarkeit", () => {
  it("sichtbar bei passendem Vertragstyp, sonst nur mit Angaben oder auf Wunsch", () => {
    const base = { service: EMPTY, scopeHasData: false, slaHasData: false, revealed: false };
    expect(servicesVisible({ ...base, sections: { scope: true, sla: true } })).toBe(true);
    expect(servicesVisible({ ...base, sections: { scope: false, sla: false } })).toBe(false);
    expect(servicesVisible({ ...base, sections: null })).toBe(false);
    expect(servicesVisible({ ...base, sections: { scope: false, sla: false }, slaHasData: true })).toBe(true);
    expect(servicesVisible({ ...base, sections: { scope: false, sla: false }, service: { ...EMPTY, penalty_terms: "0,5 % je Tag" } })).toBe(true);
    expect(servicesVisible({ ...base, sections: { scope: false, sla: false }, revealed: true })).toBe(true);
  });
});

describe("Leistungen & SLA: Direkt zur Stelle", () => {
  it("Felder und Abschnitte führen zum Reiter „Leistungen & SLA“", () => {
    expect(normalizeTarget({ tab: "register", field: "sla_availability_percent" })).toEqual({ tab: "services", field: "sla_availability_percent" });
    expect(normalizeTarget({ tab: "overview", section: "leistungsumfang" })).toEqual({ tab: "services", section: "leistungsumfang" });
    expect(contractHref("c-1", SCOPE_TARGET)).toBe("/contracts/c-1?tab=services&abschnitt=leistungsumfang");
    expect(sectionAnchor("sla")).toBe("sla-heading");
  });
});
