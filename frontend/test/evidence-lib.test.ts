import { describe, expect, it } from "vitest";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import {
  documentValue, evidenceStatus, factsByEvidence, guidedOrder, orderEvidence, precisionOf, roundSummary, sameText, storedValue, valueText, wordDiff,
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

describe("Prüfstand", () => {
  it("Ergebnis der Nachweisprüfung zählt; frühere Bestätigung nur bei genau belegter Fundstelle", () => {
    const confirmed = fact({ state: "confirmed" });
    expect(evidenceStatus(ref({ location: "exact" }), confirmed, undefined)).toBe("confirmed");
    // „Nur Seite“ und „ungefähr“ werden nicht automatisch geprüft, automatisch übernommene auch nicht.
    expect(evidenceStatus(ref({ location: "page", bbox: null }), confirmed, undefined)).toBe("open");
    expect(evidenceStatus(ref({ location: "approx" }), confirmed, undefined)).toBe("open");
    expect(evidenceStatus(ref({ location: "exact" }), fact({ state: "auto_accepted" }), undefined)).toBe("open");
    const review = (status: "confirmed" | "document" | "medflux" | "manual" | "skipped") => ({ evidence_id: "e-1", fact_key: null, status, status_label: "", note: null, reviewed_by_name: null, reviewed_at: "" });
    expect(evidenceStatus(ref({ location: "page" }), undefined, review("confirmed"))).toBe("confirmed");
    expect(evidenceStatus(ref({}), undefined, review("medflux"))).toBe("deviation");
    expect(evidenceStatus(ref({}), undefined, review("document"))).toBe("deviation");
    expect(evidenceStatus(ref({}), undefined, review("skipped"))).toBe("skipped");
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

  it("gespeicherter Wert: Vertragsdaten-Feld, sonst wirksamer Wert; reine Nachweise ohne", () => {
    expect(storedValue(fact({ register_field: "term_start_date", stored_value: "01.04.2025", effective_value: "2025-05-01" }))).toBe("01.04.2025");
    expect(storedValue(fact({ register_field: "term_start_date", stored_value: null }))).toBeNull();
    expect(storedValue(fact({ fact_key: "sla.service_hours", effective_value: "Mo–Fr 9–17 Uhr" }))).toBe("Mo–Fr 9–17 Uhr");
    expect(storedValue(fact({ is_evidence_item: true, effective_value: "Zitat" }))).toBeNull();
    expect(documentValue(ref({ snippet: "Zitat im Text" }), fact({ is_evidence_item: true }))).toBe("Zitat im Text");
    expect(documentValue(ref({}), fact({ original_value: "2025-04-01" }))).toBe("01.04.2025");
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

describe("Reihenfolge und Runde", () => {
  it("geführt nach Abschnitt (Partner, Laufzeit, Kosten), darin Lesereihenfolge", () => {
    const items = [
      ref({ evidence_id: "cost", field_ref: "costs.annual_cost.evidence.0", page: 1 }),
      ref({ evidence_id: "start", field_ref: "dates.start_date.evidence.0", page: 3 }),
      ref({ evidence_id: "customer", field_ref: "identity.customer.evidence.0", page: 1, bbox: { x0: 0, y0: 400, x1: 10, y1: 410 } }),
      ref({ evidence_id: "end", field_ref: "dates.end_date.evidence.0", page: 2 }),
    ];
    const facts = factsByEvidence([]);
    expect(guidedOrder(orderEvidence(items), facts).map((item) => item.evidence_id)).toEqual(["customer", "end", "start", "cost"]);
  });

  it("Zusammenfassung wie im Verlauf", () => {
    expect(roundSummary({ confirmed: 30, document: 2, medflux: 1, skipped: 1 })).toBe("34 geprüft: 30 bestätigt · 3 abweichend (übernommen 2, geklärt 1) · 1 übersprungen");
    expect(roundSummary({ confirmed: 2 })).toBe("2 geprüft: 2 bestätigt");
  });
});
