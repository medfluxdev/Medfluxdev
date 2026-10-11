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
    scopeToCheck: 10,
    scopeTotal: 10,
    slaMissing: ["Reaktionszeit", "Lösungszeit"],
  });

  it("ordnet Kritisch → Prüfen (hoch) → KI-Prüfung → Prüfen → Hinweis", () => {
    expect(points.map((point) => [point.word, point.title])).toEqual([
      ["Kritisch", "Vertragsart fehlt"],
      ["Kritisch", "Frist verstrichen"],
      ["Prüfen", "Berechnungskonflikt"],
      ["KI-Prüfung", "KI-Wert prüfen"],
      ["Prüfen", "Vertragspartner"],
      ["Prüfen", "Leistungsumfang ungeklärt"],
      ["Prüfen", "SLA unvollständig"],
      ["Hinweis", "Kosten nachtragen"],
    ]);
    // Eine Warnung, die eine Prüfung verlangt, folgt ihrem Schweregrad – mit „Priorität hoch“.
    expect(points[2].why).toBe("Bitte prüfen · Priorität hoch");
    expect(points[5].why).toBe("10 von 10 Leistungen sind noch zu prüfen.");
    expect(points[6].why).toBe("Reaktionszeit und Lösungszeit wurden im Vertrag nicht gefunden.");
  });

  it("zeigt Signal + Wort, Zähler und genau einen Primärknopf; Knöpfe führen zur Stelle", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const { container } = render(<OpenPoints contractId="c-1" points={points} onOpen={onOpen} />);
    const section = screen.getByRole("region", { name: /Offene Punkte/ });
    expect(within(section).getByLabelText("8 offen")).toBeInTheDocument();
    expect(section.querySelectorAll(".btn-primary")).toHaveLength(1);
    await user.click(within(section).getByRole("link", { name: "Vertragsart erfassen" }));
    expect(onOpen).toHaveBeenCalledWith({ tab: "register", field: "term_model" });
    expect(within(section).getByRole("link", { name: "SLA" })).toHaveAttribute("href", "#sla-heading");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Offene Punkte – Kündbar bis nicht berechenbar", () => {
  it("steht als erster kritischer Punkt, außer eine fristrelevante Lücke ist schon genannt", () => {
    const base = { tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 10, slaMissing: [], cancelByUnknown: true };
    expect(buildOpenPoints({ ...base, gaps: [] }).map((point) => [point.word, point.title, point.action])).toEqual([
      ["Kritisch", "Kündigungsfrist nicht berechenbar", "Laufzeit erfassen"],
    ]);
    const withGap = buildOpenPoints({ ...base, gaps: [{ key: "notice_period_value", label: "Kündigungsfrist", reason: "nötig für die Fristberechnung", command: "Kündigungsfrist erfassen", target: { tab: "register", field: "notice_period_value" }, blocksDeadline: true }] });
    expect(withGap.map((point) => point.title)).toEqual(["Kündigungsfrist fehlt"]);
  });
});

