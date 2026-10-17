import type { ContractDetailResponse, FactReviewStateDto } from "@/lib/contract-detail-types";

// Quellfeld eines Werts (Register, Finanzen) -> Prüf-Angabe, wenn die Namen abweichen.
const REVIEW_FACT_ALIAS: Record<string, string> = {
  "costs.annual_cost": "costs.annual",
  "costs.annual_recurring": "costs.annual",
  "costs.monthly_cost": "costs.monthly_recurring",
  "costs.price_adjustment_clause": "costs.price_indexation",
  "termination.cancellation_to_contract_end": "termination.cancellation_period",
};

/** Angaben, die die Prüfung zeigt (wie `FactReviewPanel`); nur dorthin kann ein Sprung führen. */
export function visibleReviewFacts(data: Pick<ContractDetailResponse, "fact_review_states">): FactReviewStateDto[] {
  return (data.fact_review_states ?? []).filter((s) => s.present || s.state !== "unreviewed" || s.has_history);
}

/**
 * Prüf-Angabe, aus der ein Wert stammt – in dieser Reihenfolge: gleicher Schlüssel, Schlüssel unter anderem
 * Namen, Nachweis-Angabe („evidence.<Feld>“, auch ohne Zähler wie bei Preisstufen), Angabe mit einem Beleg
 * dieses Felds, gleiche Bezeichnung. Sonst nichts (kein Raten).
 */
export function findReviewFact(
  data: Pick<ContractDetailResponse, "fact_review_states" | "evidence">,
  factKeys: string[],
  subject?: string,
): FactReviewStateDto | undefined {
  const states = visibleReviewFacts(data);
  const keys = factKeys.flatMap((key) => {
    const base = key.split(".evidence", 1)[0];
    const parent = base.replace(/\.\d+$/, "");
    return [base, REVIEW_FACT_ALIAS[base], parent, REVIEW_FACT_ALIAS[parent], `evidence.${base}`, `evidence.${parent}`]
      .filter((item): item is string => Boolean(item));
  });
  for (const key of keys) {
    const fact = states.find((s) => s.fact_key === key);
    if (fact) return fact;
  }
  for (const key of keys) {
    const ids = new Set(data.evidence.filter((ref) => ref.field_ref === key || ref.field_ref?.startsWith(`${key}.`)).map((ref) => ref.evidence_id));
    const fact = ids.size ? states.find((s) => s.linked_evidence_refs?.some((id) => ids.has(id))) : undefined;
    if (fact) return fact;
  }
  return subject ? states.find((s) => s.label_de === subject) : undefined;
}
