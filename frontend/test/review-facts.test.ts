import { describe, expect, it } from "vitest";
import { findReviewFact } from "@/lib/review-facts";
import type { ContractDetailResponse, EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";

const fact = (fact_key: string, label_de: string, extra: Partial<FactReviewStateDto> = {}) => ({
  fact_key, label_de, present: true, state: "unreviewed", state_label_de: "Ungeprüft", original_value: "x", effective_value: "x",
  reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false,
  evidence_count: 0, linked_evidence: [], linked_evidence_refs: [], needs_evidence: false, is_critical: false, ...extra,
}) as FactReviewStateDto;
const evidence = (evidence_id: string, field_ref: string) => ({ evidence_id, field_ref }) as EvidenceRef;

const data = {
  fact_review_states: [
    fact("dates.start_date", "Vertragsbeginn"),
    fact("costs.annual", "Jährliche Gesamtkosten"),
    fact("evidence.costs.scheduled_prices", "Preisstaffel"),
    fact("costs.monthly_net", "Monatlicher Nettopreis", { linked_evidence_refs: ["e-fee"] }),
    fact("sla.response_time", "Reaktionszeit", { present: false }),
  ],
  evidence: [evidence("e-fee", "costs.maintenance_fee.evidence.0")],
} as unknown as Pick<ContractDetailResponse, "fact_review_states" | "evidence">;

describe("Sprung von der KI-Plakette zur Prüf-Angabe", () => {
  it.each([
    [["dates.start_date"], "dates.start_date"],
    [["costs.annual_cost"], "costs.annual"],
    [["costs.scheduled_prices.2"], "evidence.costs.scheduled_prices"],
    [["costs.maintenance_fee"], "costs.monthly_net"],
    [[null as unknown as string, "dates.start_date"].filter(Boolean), "dates.start_date"],
  ])("%j -> %s", (keys, expected) => {
    expect(findReviewFact(data, keys)?.fact_key).toBe(expected);
  });

  it("nur Angaben, die die Prüfung zeigt; ohne Treffer nichts, mit gleicher Bezeichnung die Angabe", () => {
    expect(findReviewFact(data, ["sla.response_time"])).toBeUndefined();
    expect(findReviewFact(data, ["identity.contract_title"])).toBeUndefined();
    expect(findReviewFact(data, [], "Vertragsbeginn")?.fact_key).toBe("dates.start_date");
  });
});
