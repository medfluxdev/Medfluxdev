import { describe, expect, it } from "vitest";
import type { EvidenceRef } from "@/lib/contract-detail-types";
import { evidence as fieldEvidence, field, finding, review as fieldReview } from "./fixtures/field-review";
import {
  fieldEvidenceStatus, orderEvidence, precisionOf, sameText, valueText, wordDiff,
} from "@/lib/evidence";

function ref(overrides: Partial<EvidenceRef>): EvidenceRef {
  return {
    evidence_id: "e-1", field_ref: "costs.annual_cost", document_version_id: "dv-1", original_filename: "wartung.pdf", page: 2,
    paragraph_index: null, table_index: null, source_type: "paragraph", snippet: "Jährliche Vergütung 12.000 EUR.", confidence: 0.9,
    requires_review: false, bbox: { x0: 100, y0: 200, x1: 160, y1: 212 }, precision: "coarse", geometry_normalized: false,
    bbox_space: "pdf_points", supports_exact_navigation: true, ...overrides,
  };
}
function fact(overrides: Partial<FactReviewStateDto>): FactReviewStateDto {
  return {
    fact_key: "dates.start_date", label_de: "Vertragsbeginn", present: true, state: "unreviewed", state_label_de: "", original_value: null,
    effective_value: null, reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false,
    evidence_count: 1, linked_evidence: [], linked_evidence_refs: ["e-1"], needs_evidence: false, is_critical: false, ...overrides,
  };
}

describe("Lage der Nachweise", () => {
  it("nimmt die belegte Lage aus dem Backend; „Genau“ nur mit Textbeleg", () => {
    expect(precisionOf(ref({ location: "approx" }))).toBe("approx");
    expect(precisionOf(ref({ location: "exact" }))).toBe("exact");
    expect(precisionOf(ref({ location: "page", bbox: null }))).toBe("page");
  });

  it("ohne Backend-Angabe: seitenfüllende Box ungefähr, schmale genau, ohne Box nur Seite, ohne Seite ohne Seite", () => {
    expect(precisionOf(ref({ bbox: { x0: 89.66, y0: 69.16, x1: 543.86, y1: 725.15 } }))).toBe("approx");
    expect(precisionOf(ref({}))).toBe("exact");
    expect(precisionOf(ref({ bbox: null, supports_exact_navigation: false }))).toBe("page");
    expect(precisionOf(ref({ page: null, bbox: null }))).toBe("none");
  });
});

describe("Prüfstand eines Nachweises = Stand seines Felds", () => {
  const entry = (evidence_id: string, excluded = false) => ({ ...fieldEvidence({ evidence_id }), excluded });
  const review = fieldReview([
    field({ fact_key: "a", status: "decided", decision_needed: false, evidence: [entry("e-ok"), entry("e-out", true)] }),
    field({ fact_key: "b", status: "conflict", evidence: [entry("e-conflict")] }),
    field({ fact_key: "c", status: "deferred", evidence: [entry("e-later")] }),
    field({ fact_key: "d", status: "open", evidence: [entry("e-open")] }),
    field({ fact_key: "e", status: "derived", kind: "calculated", decision_needed: false, evidence: [entry("e-calc")] }),
  ], { findings: [finding({ evidence_ids: ["e-extra"] })] });

  it("ein Feld, eine Entscheidung: alle Belege eines entschiedenen Felds gelten als entschieden", () => {
    expect(fieldEvidenceStatus("e-ok", review)).toBe("confirmed");
    expect(fieldEvidenceStatus("e-calc", review)).toBe("confirmed");
    expect(fieldEvidenceStatus("e-conflict", review)).toBe("deviation");
    expect(fieldEvidenceStatus("e-later", review)).toBe("skipped");
    expect(fieldEvidenceStatus("e-open", review)).toBe("open");
  });

  it("ausgeschlossene Belege sind kenntlich, Weitere Informationen zählen nicht als offen", () => {
    expect(fieldEvidenceStatus("e-out", review)).toBe("excluded");
    expect(fieldEvidenceStatus("e-extra", review)).toBe("extra");
  });

  it("ohne Feldprüfung oder ohne Zuordnung bleibt ein Nachweis offen", () => {
    expect(fieldEvidenceStatus("e-ok", null)).toBe("open");
    expect(fieldEvidenceStatus("unbekannt", review)).toBe("open");
  });
});

describe("Abgleich Dokument ↔ MedFlux", () => {
  it("formatiert wie die Vertragsdaten", () => {
    expect(valueText("dates.end_date", "2029-03-31")).toBe("31.03.2029");
    expect(valueText("costs.annual", "8000.0")).toMatch(/^8\.000,00\s€$/);
    expect(valueText("costs.vat_rate", 19.0)).toBe("19 %");
    expect(valueText("termination.auto_renewal", false)).toBe("Nein");
    expect(valueText("x", "")).toBeNull();
  });

  it("vergleicht ohne Leerraum und Zeichen („Frankfurtam Main“, „Impella®AIC“)", () => {
    expect(sameText("D-60488 Frankfurtam Main", "D-60488 Frankfurt am Main")).toBe(true);
    expect(sameText("Impella®AIC System", "Impella AIC System")).toBe(true);
    expect(sameText("01.04.2025", "01.05.2025")).toBe(false);
    expect(sameText("", "")).toBe(false);
  });

  it("markiert abweichende Wörter beider Seiten", () => {
    const diff = wordDiff("Krankenhaus Nordwest GmbH Frankfurt", "Krankenhaus Nordwest gGmbH Frankfurt");
    expect(diff.a.filter((token) => token.changed).map((token) => token.text)).toEqual(["GmbH"]);
    expect(diff.b.filter((token) => token.changed).map((token) => token.text)).toEqual(["gGmbH"]);
  });
});
