import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import OpenPoints, { buildOpenPoints } from "@/components/contracts/detail/OpenPoints";

const warning = (severity: string, title: string, requiresReview = false) => ({
  warning_type: "calculation_conflict", severity, title_de: title, target_kind: null, target_date: null, days_remaining: null,
  requires_action: true, requires_review: requiresReview, action_state: null,
});

describe("Offene Punkte – freigegebene Zuordnung", () => {
  const points = buildOpenPoints({
    gaps: [
      { key: "partner_id", label: "Vertragspartner", reason: "nötig für „Gültig“", command: "Vertragspartner erfassen", target: { tab: "register", field: "partner_id" } },
      { key: "term_model", label: "Vertragsart", reason: "nötig für die Fristberechnung", command: "Vertragsart erfassen", target: { tab: "register", field: "term_model" }, blocksDeadline: true },
    ],
    tasks: [
      { work_item_id: "t1", item_type: "missing_annual_cost", severity: "low", title_de: "Kosten nachtragen", why_de: null, requires_review: false },
      { work_item_id: "t2", item_type: "review_required", severity: "medium", title_de: "KI-Wert prüfen", why_de: null, requires_review: true },
    ],
    warnings: [warning("high", "Berechnungskonflikt", true), warning("critical", "Frist verstrichen")],
    fieldReview: { essentialOpen: 3, conflicts: 0, missing: 0, deferred: 0 },
  });

  it("ordnet Kritisch → Prüfen (hoch) → KI-Prüfung → Prüfen → Hinweis", () => {
    expect(points.map((point) => [point.word, point.title])).toEqual([
      ["Kritisch", "Vertragsart fehlt"],
      ["Kritisch", "Frist verstrichen"],
      ["Prüfen", "Berechnungskonflikt"],
      ["KI-Prüfung", "KI-Wert prüfen"],
      ["KI-Prüfung", "Wesentliche Angaben entscheiden"],
      ["Prüfen", "Vertragspartner"],
      ["Hinweis", "Kosten nachtragen"],
    ]);
    // Eine Warnung, die eine Prüfung verlangt, folgt ihrem Schweregrad – mit „Priorität hoch“.
    expect(points[2].why).toBe("Bitte prüfen · Priorität hoch");
    // Die Prüfung ist ein einziger Punkt – Leistungen, SLA und Belege sind keine eigenen Pflichtpunkte.
    expect(points.find((point) => point.key === "field-review")?.why).toBe("3 wesentliche Entscheidungen warten.");
    expect(points.some((point) => /Leistungsumfang|SLA|Nachweise prüfen/.test(point.title))).toBe(false);
  });

  it("zeigt Signal + Wort, Zähler und genau einen Primärknopf; Knöpfe führen zur Stelle", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const { container } = render(<OpenPoints contractId="c-1" points={points} onOpen={onOpen} />);
    const section = screen.getByRole("region", { name: /Offene Punkte/ });
    expect(within(section).getByLabelText("7 offen")).toBeInTheDocument();
    expect(section.querySelectorAll(".btn-primary")).toHaveLength(1);
    await user.click(within(section).getByRole("link", { name: "Vertragsart erfassen" }));
    expect(onOpen).toHaveBeenCalledWith({ tab: "register", field: "term_model" });
    const review = within(section).getAllByRole("link", { name: "Prüfen" }).find((link) => link.getAttribute("href")?.includes("abschnitt=nachweise-pruefen"));
    expect(review).toBeDefined();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Offene Punkte – Kündbar bis nicht berechenbar", () => {
  it("steht als erster kritischer Punkt, außer eine fristrelevante Lücke ist schon genannt", () => {
    const base = { tasks: [], warnings: [], cancelByUnknown: true };
    expect(buildOpenPoints({ ...base, gaps: [] }).map((point) => [point.word, point.title, point.action])).toEqual([
      ["Kritisch", "Kündigungstermin nicht berechenbar", "Kündigungsfrist erfassen"],
    ]);
    const withGap = buildOpenPoints({ ...base, gaps: [{ key: "notice_period_value", label: "Kündigungsfrist", reason: "nötig für die Fristberechnung", command: "Kündigungsfrist erfassen", target: { tab: "register", field: "notice_period_value" }, blocksDeadline: true }] });
    expect(withGap.map((point) => point.title)).toEqual(["Kündigungsfrist fehlt"]);
  });

  it("Feldprüfung: ein Punkt für die wesentlichen Entscheidungen, Widersprüche und Lücken benannt; nichts offen = kein Punkt", () => {
    const base = { gaps: [], tasks: [], warnings: [] };
    const [point] = buildOpenPoints({ ...base, fieldReview: { essentialOpen: 4, conflicts: 1, missing: 2, deferred: 1 } });
    expect([point.word, point.title]).toEqual(["Prüfen", "Wesentliche Angaben entscheiden"]);
    expect(point.why).toBe("4 wesentliche Entscheidungen warten · 1 Widerspruch oder Änderung · 2 nicht im Dokument gefunden · 1 zurückgestellt.");
    expect(point.target).toEqual({ tab: "documents", subtab: "document", section: "nachweise-pruefen" });
    expect(buildOpenPoints({ ...base, fieldReview: { essentialOpen: 0, conflicts: 0, missing: 0, deferred: 0 } })).toEqual([]);
    expect(buildOpenPoints({ ...base, fieldReview: null })).toEqual([]);
    // Die bisherige „Prüfung der KI-Werte“-Lücke wird nicht doppelt gezeigt.
    const gap = { key: "review", label: "Wesentliche Angaben prüfen", reason: "x", command: "Wesentliche Angaben prüfen", target: { tab: "documents" } };
    expect(buildOpenPoints({ ...base, gaps: [gap], fieldReview: { essentialOpen: 1, conflicts: 0, missing: 0, deferred: 0 } })).toHaveLength(1);
  });
});

describe("Offene Punkte – Entscheidung treffen", () => {
  const base = { gaps: [], tasks: [], warnings: [] };
  it("nennt eine fehlende Entscheidung, Dringlichkeit nach der Frist, mit Sprung zur Karte", () => {
    const [soon] = buildOpenPoints({ ...base, decision: { due: "2026-09-30", byCancel: true, urgency: "soon" } });
    expect([soon.word, soon.title, soon.action]).toEqual(["Hinweis", "Entscheidung treffen", "Entscheiden"]);
    expect(soon.why).toBe("Bis 30.09.2026 entscheiden: verlängern, neu verhandeln, kündigen oder beobachten.");
    expect(soon.target).toEqual({ tab: "deadlines", section: "decision" });
    expect(buildOpenPoints({ ...base, decision: { due: "2026-09-30", byCancel: true, urgency: "critical" } })[0].word).toBe("Prüfen");
    expect(buildOpenPoints({ ...base, decision: { due: "2026-09-30", byCancel: true, urgency: "missed" } })[0].word).toBe("Kritisch");
    expect(buildOpenPoints({ ...base, decision: null })).toEqual([]);
  });
});

describe("Offene Punkte – nächster Umsetzungsschritt", () => {
  it("nennt den ersten offenen Schritt mit Frist; überfällig = Kritisch", () => {
    const base = { gaps: [], tasks: [], warnings: [] };
    const stepInput = { label: "Kündigen", title: "Status auf „Gekündigt“ setzen", detail: "Mit Datum.", due: "2026-08-20", target: { tab: "register", section: "status" }, done: 1, total: 4, today: "2026-08-15" };
    const [point] = buildOpenPoints({ ...base, decisionStep: stepInput });
    expect([point.word, point.title, point.action]).toEqual(["Prüfen", "Kündigen: Status auf „Gekündigt“ setzen", "Status setzen"]);
    expect(point.why).toBe("Schritt 2 von 4. Bis 20.08.2026. Mit Datum.");
    expect(point.target).toEqual({ tab: "register", section: "status" });
    const [late] = buildOpenPoints({ ...base, decisionStep: { ...stepInput, today: "2026-09-01", target: { action: "change_decision" } } });
    expect([late.word, late.action, late.target]).toEqual(["Kritisch", "Umsetzung ansehen", { tab: "deadlines", section: "decision" }]);
  });

});
