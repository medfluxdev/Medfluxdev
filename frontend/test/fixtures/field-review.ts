import type {
  FieldCandidateDto, FieldEvidenceDto, FieldFindingDto, FieldReviewDto, FieldReviewFieldDto, FieldStageDto, FieldTier,
} from "@/lib/contract-detail-types";

/** Bausteine für die Tests der Feldprüfung (Form wie das Backend `field_review`). */

export function evidence(overrides: Partial<FieldEvidenceDto> = {}): FieldEvidenceDto {
  return {
    evidence_id: "e1", page: 3, snippet: "Der Vertrag endet am 31.03.2029.", location: "exact", text_verified: true, confidence: 0.93,
    extraction_method: "ai", document_version_id: "doc-1", original_filename: "vertrag.pdf", document_available: true,
    source_state: "verified", source_state_label: "Fundstelle bestätigt", excluded: false, exclusion_reason: null,
    exclusion_reason_label: null, exclusion_note: null, excluded_by: null, primary: true, ...overrides,
  };
}

export function candidate(overrides: Partial<FieldCandidateDto> = {}): FieldCandidateDto {
  return {
    key: "2029-03-31", display: "31.03.2029", value: "31.03.2029", is_current: true,
    sources: [{ source: "document", label: "Aus dem Dokument gelesen" }], evidence_ids: ["e1"], inline_evidence: [], support_count: 1,
    proposal_id: null, run_number: null, detail: null, confidence: 0.93, ...overrides,
  };
}

export function field(overrides: Partial<FieldReviewFieldDto> = {}): FieldReviewFieldDto {
  return {
    fact_key: "dates.end_date", label: "Vertragsende", card: "term", card_label: "Fristen & Aufgaben", tier: "essential", tier_label: "Wesentliche Angaben",
    why: "Das Vertragsende bestimmt Kündigung und Verlängerung.", kind: "extracted", status: "open", status_label: "Zu entscheiden", reason: null,
    decision_needed: true, present: true, current: "31.03.2029", current_origin: "document", document_value: "31.03.2029", stored_value: null,
    register_field: null, candidates: [candidate()], evidence: [evidence()], primary_evidence_id: "e1", source_state: "verified",
    source_state_label: "Fundstelle bestätigt", active_evidence_count: 1, inputs: [], ai_confidence: 0.93, found_by_rule: false, is_critical: true,
    reviewed_at: null, reviewer: null, version: null, fact_state: "unreviewed", history: [], ...overrides,
  };
}

export function stage(tier: FieldTier, overrides: Partial<FieldStageDto> = {}): FieldStageDto {
  return { tier, label: tier, total: 0, open: 0, decided: 0, missing: 0, conflicts: 0, deferred: 0, ...overrides };
}

export function finding(overrides: Partial<FieldFindingDto> = {}): FieldFindingDto {
  return {
    finding_key: "evidence.costs.discounts.0", label: "Rabatte", source_field: "costs.discounts.0", snippet: "3 % Skonto bei Zahlung in 10 Tagen", page: 5,
    evidence_id: "e9", evidence_ids: ["e9"], decision: null, target_fact_key: null, note: null, decided_by: null, contact: false, consequential: true, ...overrides,
  };
}

export function review(fields: FieldReviewFieldDto[], overrides: Partial<FieldReviewDto> = {}): FieldReviewDto {
  const tiers: FieldTier[] = ["essential", "important", "optional"];
  const stages = tiers.map((tier) => {
    const group = fields.filter((item) => item.tier === tier && item.kind === "extracted" && (item.present || item.status === "missing"));
    return stage(tier, {
      total: group.length, open: group.filter((item) => item.decision_needed).length, decided: group.filter((item) => !item.decision_needed).length,
      missing: group.filter((item) => item.status === "missing").length,
      conflicts: group.filter((item) => item.status === "conflict" || item.status === "changed").length,
      deferred: group.filter((item) => item.status === "deferred").length,
    });
  });
  return {
    stages, essential_complete: stages[0].total > 0 && stages[0].open === 0, essential_open: stages[0].open,
    decisions_open: stages.reduce((sum, item) => sum + item.open, 0), fields, findings: [], findings_open: 0, findings_consequential: 0,
    exclusion_reasons: [{ key: "wrong_place", label: "Falsche Stelle im Dokument" }, { key: "other", label: "Sonstiges" }], ...overrides,
  };
}

/** Ein Vertrag mit zwei übereinstimmenden Belegen zum Vertragsende. */
export function twoAgreeing(): FieldReviewFieldDto {
  return field({
    candidates: [candidate({ evidence_ids: ["e1", "e2"], support_count: 2 })],
    evidence: [evidence(), evidence({ evidence_id: "e2", page: 9, snippet: "Laufzeit bis 31.03.2029", location: "page", text_verified: false, source_state: "located", source_state_label: "Seite bekannt, Stelle ungefähr", primary: false })],
    active_evidence_count: 2,
  });
}

/** Das Vertragsende mit zwei konkurrierenden Werten. */
export function conflicting(): FieldReviewFieldDto {
  return field({
    status: "conflict", status_label: "Widerspruch", reason: "Mehrere Werte kommen in Frage – bitte einen wählen.",
    candidates: [
      candidate({ evidence_ids: ["e1"], support_count: 1 }),
      candidate({ key: "2028-03-31", display: "31.03.2028", value: "31.03.2028", is_current: false, sources: [{ source: "conflict", label: "Aus Beginn + Laufzeit" }], evidence_ids: [], support_count: 0, detail: "01.04.2025 + 36 Monate" }),
    ],
  });
}
