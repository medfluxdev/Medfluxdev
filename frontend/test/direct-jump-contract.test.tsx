import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useContractGaps } from "@/components/contracts/detail/ContractGaps";
import OpenPoints, { buildOpenPoints } from "@/components/contracts/detail/OpenPoints";
import ContractRulesSection from "@/components/contracts/detail/ContractRulesSection";
import { asFixTarget, contractHref, fixLabel, normalizeTarget, warningTarget, workItemTarget } from "@/lib/fix-targets";

const api = vi.hoisted(() => ({ getContractRegister: vi.fn(), getContractOwnership: vi.fn(), getContractRules: vi.fn() }));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/register")>()), getContractRegister: api.getContractRegister }));
vi.mock("@/lib/domain-api/ownership", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/ownership")>()), getContractOwnership: api.getContractOwnership }));
vi.mock("@/lib/domain-api/rules", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/rules")>()), getContractRules: api.getContractRules }));
vi.mock("@/lib/use-permissions", () => ({ usePermissions: () => ({ can: () => true, loaded: true }) }));

const field = (label: string) => ({ value: null, label });

// Karte über den Hook, so wie die Vertragsakte sie verwendet.
function Gaps(props: { hasAnnualCost: boolean; reviewPending: boolean; documentCount: number }) {
  const gaps = useContractGaps({ contractId: "c-1", orgSlug: "test-klinik", ...props });
  if (gaps === null) return null;
  const points = buildOpenPoints({ gaps, tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 10 });
  return <OpenPoints contractId="c-1" points={points} onOpen={() => undefined} />;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getContractRegister.mockResolvedValue({
    business_status: "in_arbeit",
    fields: { term_start_date: field("Vertragsbeginn"), partner_id: field("Vertragspartner"), notice_period_value: field("Kündigungsfrist") },
    missing_for_valid: ["term_start_date", "partner_id"],
    terms: { missing: ["term_start_date", "notice_period_value"] },
  });
  api.getContractOwnership.mockResolvedValue({ responsible_account_id: null });
  api.getContractRules.mockResolvedValue({
    status: "Unvollständig",
    items: [
      { rule_id: "r-1", label: "Kosten höchstens 50.000 €", outcome: "unknown", detail: "Jährliche Kosten sind nicht erfasst.", target: { tab: "finance", section: "entries" } },
      { rule_id: "r-2", label: "Mindestkündigungsfrist", outcome: "pass", detail: "Kündigungsfrist 3 Monate.", target: { tab: "register", field: "notice_period" } },
    ],
  });
});

describe("Direkt zur Stelle: Ziele für Aufgaben, Warnungen und API-Antworten", () => {
  it("führt Aufgaben und Warnungen dorthin, wo sie erledigt werden", () => {
    expect(workItemTarget("missing_cost")).toEqual({ tab: "finance", section: "entries" });
    expect(workItemTarget("manual_review")).toEqual({ tab: "documents", subtab: "review" });
    expect(workItemTarget("equipment_coverage_review")).toEqual({ tab: "relations" });
    expect(workItemTarget("sla_issue")).toBeNull();
    expect(workItemTarget("missing_cost", true)).toEqual({ tab: "documents", subtab: "review" });
    expect(warningTarget("missing_cost_data")).toEqual({ tab: "finance", section: "entries" });
    expect(warningTarget("cancellation_deadline_passed")).toEqual({ tab: "deadlines", section: "renewal" });
    expect(warningTarget("unbekannt")).toBeNull();
  });

  it("prüft Ziele aus dem Backend und führt Zuständigkeitsfelder zum Abschnitt", () => {
    expect(asFixTarget({ tab: "register", field: "notice_period" })).toEqual({ tab: "register", field: "notice_period" });
    expect(asFixTarget({ tab: "nirgendwo" })).toBeNull();
    expect(asFixTarget(null)).toBeNull();
    expect(normalizeTarget({ tab: "register", field: "responsible_account_id" })).toEqual({ tab: "register", section: "ownership" });
    expect(contractHref("c-1", { tab: "register", field: "responsible_account_id" })).toBe("/contracts/c-1?tab=register&abschnitt=ownership");
    expect(fixLabel({ tab: "finance", section: "entries" })).toBe("Kosten erfassen");
    expect(fixLabel({ tab: "documents", subtab: "review" })).toBe("KI-Werte prüfen");
  });
});

describe("Direkt zur Stelle: Vertragsakte", () => {
  it("„Offene Punkte“: jede Lücke einmal, fristrelevante zuerst als kritisch, je ein Link zur Stelle", async () => {
    const { container } = render(<Gaps hasAnnualCost={false} reviewPending documentCount={0} />);
    const card = (await screen.findByRole("heading", { name: /Offene Punkte/ })).closest("section")!;
    const items = within(card).getAllByRole("listitem");
    expect(items.map((item) => [item.querySelector(".signal-label")?.textContent, within(item).getByRole("link").textContent, within(item).getByRole("link").getAttribute("href")])).toEqual([
      ["Kritisch", "Vertragsbeginn erfassen", "/contracts/c-1?tab=register&feld=term_start_date"],
      ["Kritisch", "Kündigungsfrist erfassen", "/contracts/c-1?tab=register&feld=notice_period"],
      ["KI-Prüfung", "Werte prüfen", "/contracts/c-1?tab=documents&subtab=review"],
      ["Prüfen", "Vertragspartner erfassen", "/contracts/c-1?tab=register&feld=partner_id"],
      ["Prüfen", "Kosten erfassen", "/contracts/c-1?tab=finance&abschnitt=entries"],
      ["Prüfen", "Verantwortliche Person festlegen", "/contracts/c-1?tab=register&abschnitt=ownership"],
      ["Prüfen", "Vertragsdokument hinzufügen", "/contracts/c-1?tab=documents&subtab=attachments"],
      ["Prüfen", "Jährliche Kosten sind nicht erfasst – erfassen", "/contracts/c-1?tab=finance&abschnitt=entries"],
    ]);
    // Genau ein Primärknopf: der erste kritische Punkt.
    expect(card.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(within(items[0]).getByRole("link")).toHaveClass("btn-primary");
    expect(within(card).getByLabelText("8 offen")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("„Offene Punkte“ ohne Lücken: ruhige Meldung", async () => {
    api.getContractRegister.mockResolvedValue({ business_status: "gueltig", fields: {}, missing_for_valid: [], terms: { missing: [] } });
    api.getContractOwnership.mockResolvedValue({ responsible_account_id: "a-1" });
    api.getContractRules.mockResolvedValue({ status: "Erfüllt", items: [] });
    render(<Gaps hasAnnualCost reviewPending={false} documentCount={1} />);
    expect(await screen.findByText("Keine offenen Punkte")).toBeInTheDocument();
    expect(screen.getByText("Jeder Punkt führt direkt zur passenden Stelle im Vertrag.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fristen & Aufgaben anzeigen" })).toHaveAttribute("href", expect.stringContaining("tab=deadlines"));
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });

  it("Vertragsregeln mit fehlender Angabe verlinken auf die Stelle, erfüllte nicht", async () => {
    render(<ContractRulesSection organizationSlug="test-klinik" contractId="c-1" />);
    const section = (await screen.findByRole("heading", { name: "Vertragsregeln" })).closest("section")!;
    expect(within(section).getByRole("link", { name: "Kosten höchstens 50.000 €: Kosten erfassen" })).toHaveAttribute("href", "/contracts/c-1?tab=finance&abschnitt=entries");
    expect(within(section).queryByRole("link", { name: /Mindestkündigungsfrist/ })).not.toBeInTheDocument();
  });
});
