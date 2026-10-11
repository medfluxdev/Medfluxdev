import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractGaps, { useContractGaps } from "@/components/contracts/detail/ContractGaps";
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
  return <ContractGaps contractId="c-1" gaps={gaps} />;
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
  it("„Was fehlt noch?“ listet jede Lücke einmal, jede mit Link zur Stelle", async () => {
    const { container } = render(<Gaps hasAnnualCost={false} reviewPending documentCount={0} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: /Was fehlt · 8/ }));
    const card = screen.getByRole("group", { name: "Was fehlt noch?" });
    const links = within(card).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["Vertragsbeginn", "/contracts/c-1?tab=register&feld=term_start_date"],
      ["Vertragspartner", "/contracts/c-1?tab=register&feld=partner_id"],
      ["Kündigungsfrist", "/contracts/c-1?tab=register&feld=notice_period"],
      ["Jährliche Kosten", "/contracts/c-1?tab=finance&abschnitt=entries"],
      ["Verantwortliche Person", "/contracts/c-1?tab=register&abschnitt=ownership"],
      ["Prüfung der KI-Werte", "/contracts/c-1?tab=documents&subtab=review"],
      ["Vertragsdokument", "/contracts/c-1?tab=documents&subtab=attachments"],
      ["Jährliche Kosten sind nicht erfasst", "/contracts/c-1?tab=finance&abschnitt=entries"],
    ]);
    expect(within(card).getAllByText("nötig für „Gültig“")).toHaveLength(2);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("„Was fehlt noch?“ erscheint nicht, wenn nichts fehlt", async () => {
    api.getContractRegister.mockResolvedValue({ business_status: "gueltig", fields: {}, missing_for_valid: [], terms: { missing: [] } });
    api.getContractOwnership.mockResolvedValue({ responsible_account_id: "a-1" });
    api.getContractRules.mockResolvedValue({ status: "Erfüllt", items: [] });
    const { container } = render(<Gaps hasAnnualCost reviewPending={false} documentCount={1} />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });

  it("Vertragsregeln mit fehlender Angabe verlinken auf die Stelle, erfüllte nicht", async () => {
    render(<ContractRulesSection organizationSlug="test-klinik" contractId="c-1" />);
    const section = (await screen.findByRole("heading", { name: "Vertragsregeln" })).closest("section")!;
    expect(within(section).getByRole("link", { name: "Kosten höchstens 50.000 €: Kosten erfassen" })).toHaveAttribute("href", "/contracts/c-1?tab=finance&abschnitt=entries");
    expect(within(section).queryByRole("link", { name: /Mindestkündigungsfrist/ })).not.toBeInTheDocument();
  });
});
