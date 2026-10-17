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
    scopeToCheck: 3,
    scopeTotal: 4,
  });

  it("ordnet Kritisch → Prüfen (hoch) → KI-Prüfung → Prüfen → Hinweis", () => {
    expect(points.map((point) => [point.word, point.title])).toEqual([
      ["Kritisch", "Vertragsart fehlt"],
      ["Kritisch", "Frist verstrichen"],
      ["Prüfen", "Berechnungskonflikt"],
      ["KI-Prüfung", "KI-Wert prüfen"],
      ["Prüfen", "Vertragspartner"],
      ["Prüfen", "Leistungsumfang ungeklärt"],
      ["Hinweis", "Kosten nachtragen"],
    ]);
    // Eine Warnung, die eine Prüfung verlangt, folgt ihrem Schweregrad – mit „Priorität hoch“.
    expect(points[2].why).toBe("Bitte prüfen · Priorität hoch");
    expect(points[5].why).toBe("3 von 4 Leistungen aus dem Dokument sind noch nicht bestätigt.");
    // Nicht im Vertrag und nicht von der KI gefunden = nichts zu prüfen (kein Punkt „SLA unvollständig“).
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
    expect(within(section).getByRole("link", { name: "Leistungen" })).toHaveAttribute("href", "/contracts/c-1?tab=services&abschnitt=leistungsumfang");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Offene Punkte – Kündbar bis nicht berechenbar", () => {
  it("steht als erster kritischer Punkt, außer eine fristrelevante Lücke ist schon genannt", () => {
    const base = { tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 10, cancelByUnknown: true };
    expect(buildOpenPoints({ ...base, gaps: [] }).map((point) => [point.word, point.title, point.action])).toEqual([
      ["Kritisch", "Kündigungstermin nicht berechenbar", "Kündigungsfrist erfassen"],
    ]);
    const withGap = buildOpenPoints({ ...base, gaps: [{ key: "notice_period_value", label: "Kündigungsfrist", reason: "nötig für die Fristberechnung", command: "Kündigungsfrist erfassen", target: { tab: "register", field: "notice_period_value" }, blocksDeadline: true }] });
    expect(withGap.map((point) => point.title)).toEqual(["Kündigungsfrist fehlt"]);
  });

  it("zählt nur noch nicht bestätigte Werte; alles bestätigt = kein Punkt", () => {
    const base = { gaps: [], tasks: [], warnings: [] };
    const open = buildOpenPoints({ ...base, scopeToCheck: 1, scopeTotal: 4, slaToCheck: 2 });
    expect(open.map((point) => point.why)).toEqual([
      "1 von 4 Leistungen aus dem Dokument ist noch nicht bestätigt.",
      "2 SLA-Werte aus dem Dokument sind noch nicht bestätigt.",
    ]);
    expect(buildOpenPoints({ ...base, scopeToCheck: 0, scopeTotal: 4, slaToCheck: 0 })).toEqual([]);
  });
});

describe("Offene Punkte – Entscheidung treffen", () => {
  const base = { gaps: [], tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 0 };
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
    const base = { gaps: [], tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 0 };
    const stepInput = { label: "Kündigen", title: "Status auf „Gekündigt“ setzen", detail: "Mit Datum.", due: "2026-08-20", target: { tab: "register", section: "status" }, done: 1, total: 4, today: "2026-08-15" };
    const [point] = buildOpenPoints({ ...base, decisionStep: stepInput });
    expect([point.word, point.title, point.action]).toEqual(["Prüfen", "Kündigen: Status auf „Gekündigt“ setzen", "Status setzen"]);
    expect(point.why).toBe("Schritt 2 von 4. Bis 20.08.2026. Mit Datum.");
    expect(point.target).toEqual({ tab: "register", section: "status" });
    const [late] = buildOpenPoints({ ...base, decisionStep: { ...stepInput, today: "2026-09-01", target: { action: "change_decision" } } });
    expect([late.word, late.action, late.target]).toEqual(["Kritisch", "Umsetzung ansehen", { tab: "deadlines", section: "decision" }]);
  });

  it("offene Nachweise: ein Punkt „Nachweise prüfen“, der die geführte Prüfung öffnet", () => {
    const base = { gaps: [], tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 0 };
    expect(buildOpenPoints({ ...base, evidenceOpen: 0 })).toEqual([]);
    const [point] = buildOpenPoints({ ...base, evidenceOpen: 3 });
    expect([point.word, point.title, point.why, point.action]).toEqual(["KI-Prüfung", "Nachweise prüfen", "3 Nachweise sind noch nicht mit dem Dokument abgeglichen.", "Nachweise prüfen"]);
    expect(point.target).toEqual({ tab: "documents", subtab: "evidence", section: "nachweise-pruefen" });
  });
});
