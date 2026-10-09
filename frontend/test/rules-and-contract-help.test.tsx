import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FloatingAssistant from "@/components/assistant/FloatingAssistant";
import AiFillSummary from "@/components/contracts/detail/AiFillSummary";
import ContractRulesSection from "@/components/contracts/detail/ContractRulesSection";
import { ruleDefinition } from "@/components/master-data/definitions/rules";
import EntityManager from "@/components/master-data/EntityManager";
import AddContractMenu from "@/components/register/AddContractMenu";
import type { ContractRegister, RegisterField } from "@/lib/domain-api/register";
import { masterDataSection } from "@/lib/master-data";
import { resetPermissionCache } from "@/lib/use-permissions";

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("@/components/auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => ({ account: { id: "u-1", is_developer: false, memberships: [] }, organizationSlug: "test-klinik", role: auth.role, previewOf: null, loading: false }),
}));

vi.mock("@/lib/domain-api/access", () => ({
  getPermissionMatrix: vi.fn().mockResolvedValue({
    role: "admin", roles: [], granted: [],
    permissions: [
      { key: "catalog.admin", label: "", area: "", roles: ["admin"] },
      { key: "contract.create", label: "", area: "", roles: ["admin", "contract_manager"] },
      { key: "export", label: "", area: "", roles: ["admin", "contract_manager"] },
      { key: "audit.view", label: "", area: "", roles: ["admin", "contract_manager"] },
    ],
  }),
}));

const rules = vi.hoisted(() => ({ listRules: vi.fn(), createRule: vi.fn(), updateRule: vi.fn(), getContractRules: vi.fn() }));
vi.mock("@/lib/domain-api/rules", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/rules")>()), ...rules }));
vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  listContractTypes: vi.fn().mockResolvedValue({ contract_types: [{ id: "t-1", code: "wartung", label: "Wartungsvertrag", description: null, is_confidential: false, is_active: true, sort_order: 0, retention_years: null }], contract_categories: [] }),
}));
vi.mock("@/lib/domain-api/masterData", () => ({ getMasterDataUsage: vi.fn().mockResolvedValue({ kind: "rule", counts: { "r-1": 4 }, tracked_lookup_fields: null }) }));
vi.mock("@/lib/domain-api/history", () => ({ listHistory: vi.fn() }));

const api = vi.hoisted(() => ({ apiPost: vi.fn(), apiGet: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), ...api }));

let pathname = "/stammdaten/vertragsregeln";
vi.mock("next/navigation", () => ({ usePathname: () => pathname, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const CATALOG = {
  kinds: [
    { key: "min_notice_months", label: "Kündigungsfrist mindestens", unit: "Monate" },
    { key: "required_field", label: "Pflichtangabe vorhanden", unit: null },
  ],
  required_fields: [{ key: "partner_id", label: "Vertragspartner" }],
  items: [{ id: "r-1", label: "Kündigungsfrist ≥ 3 Monate", description: null, rule_kind: "min_notice_months", threshold: "3.00", field_key: null, contract_type_ids: [], is_active: true, sort_order: 0, updated_at: null }],
};

beforeEach(() => {
  vi.clearAllMocks();
  resetPermissionCache();
  auth.role = "admin";
  pathname = "/stammdaten/vertragsregeln";
  window.history.replaceState(null, "", "/");
  rules.listRules.mockResolvedValue(CATALOG);
});

describe("Vertragsregeln pflegen", () => {
  it("zeigt Regel, Prüfung und Verstöße mit Link in die Vertragsliste und legt eine Pflichtangabe-Regel an", async () => {
    const user = userEvent.setup();
    rules.createRule.mockResolvedValue({ ...CATALOG.items[0], id: "r-2" });
    const { container } = render(<EntityManager definition={ruleDefinition} section={masterDataSection("vertragsregeln")!} organizationSlug="test-klinik" />);
    const table = await screen.findByRole("table", { name: "Vertragsregeln" });
    expect(within(table).getByText("Kündigungsfrist mindestens 3 Monate")).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: /Verstöße/ })).toBeInTheDocument();
    const link = await within(table).findByRole("link", { name: /4 Verträge mit Kündigungsfrist/ });
    expect(decodeURIComponent(link.getAttribute("href") ?? "")).toContain('"op":"contains"');
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Vertragsregel anlegen" }));
    const drawer = screen.getByRole("dialog", { name: "Vertragsregel anlegen" });
    expect(within(drawer).getByLabelText(/Grenzwert \(Monate\)/)).toBeInTheDocument();
    await user.type(within(drawer).getByLabelText("Bezeichnung *"), "Partner erfasst");
    await user.selectOptions(within(drawer).getByLabelText("Was wird geprüft? *"), "required_field");
    expect(within(drawer).queryByLabelText(/Grenzwert/)).not.toBeInTheDocument();
    await user.selectOptions(within(drawer).getByLabelText("Pflichtangabe *"), "partner_id");
    await user.click(within(drawer).getByRole("checkbox", { name: "Wartungsvertrag" }));
    await user.click(within(drawer).getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(rules.createRule).toHaveBeenCalledWith("test-klinik", expect.objectContaining({
      label: "Partner erfasst", rule_kind: "required_field", field_key: "partner_id", threshold: null, contract_type_ids: ["t-1"],
    })));
  });
});

describe("Vertragsseite", () => {
  it("zeigt die Regelergebnisse eines Vertrags; nicht zutreffende Regeln werden nur gezählt", async () => {
    rules.getContractRules.mockResolvedValue({ status: "Verstoß", items: [
      { rule_id: "r-1", label: "Kündigungsfrist ≥ 3 Monate", outcome: "fail", detail: "Kündigungsfrist 1 Monate (mindestens 3)." },
      { rule_id: "r-2", label: "Partner erfasst", outcome: "pass", detail: "Vertragspartner ist erfasst." },
      { rule_id: "r-3", label: "Verlängerung ≤ 12 Monate", outcome: "na", detail: "Keine automatische Verlängerung." },
    ] });
    const { container } = render(<ContractRulesSection organizationSlug="test-klinik" contractId="c-1" />);
    expect(await screen.findByRole("heading", { name: "Vertragsregeln" })).toBeInTheDocument();
    expect(screen.getByText("Verstoß")).toBeInTheDocument();
    expect(screen.getByText("Verletzt")).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfrist 1 Monate (mindestens 3).")).toBeInTheDocument();
    expect(screen.queryByText("Verlängerung ≤ 12 Monate")).not.toBeInTheDocument();
    expect(screen.getByText("1 Regel gilt für diesen Vertrag nicht.")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("lädt Administratoren ein, Regeln festzulegen, wenn es noch keine gibt", async () => {
    rules.getContractRules.mockResolvedValue({ status: null, items: [] });
    render(<ContractRulesSection organizationSlug="test-klinik" contractId="c-1" />);
    expect(await screen.findByRole("link", { name: "Regeln festlegen" })).toHaveAttribute("href", "/stammdaten/vertragsregeln");
  });

  it("fasst zusammen, was die KI übernommen hat, und führt zur Prüfung", async () => {
    const field = (label: string, origin: RegisterField["origin"]): RegisterField => ({
      value: "x", label, group: "identity", display: null, origin, source_field: null, extraction_id: null,
      ai_proposed_value: null, confirmed_by_name: null, confirmed_at: null, updated_by_name: null, updated_at: null,
    });
    const register = {
      has_ai_analysis: true, review_pending: true,
      fields: { a: field("Kurzbeschreibung", "ai"), b: field("Vertragsbeginn", "ai"), c: field("Kündigungsfrist", "ai_confirmed"), d: field("Interne Nummer", "manual") },
    } as unknown as ContractRegister;
    const { container } = render(<AiFillSummary register={register} contractId="c-1" />);
    expect(screen.getByRole("heading", { name: "KI hat 3 Angaben aus dem Dokument übernommen" })).toBeInTheDocument();
    expect(screen.getByText("2 noch nicht bestätigt · 1 bestätigt")).toBeInTheDocument();
    expect(screen.getByText("Prüfung offen")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Jetzt prüfen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=review");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bietet im Assistenten häufige Fragen zum Vertrag an und stellt sie per Klick", async () => {
    const user = userEvent.setup();
    pathname = "/contracts/0f8a3c2e-1b2d-4e5f-8a9b-0c1d2e3f4a5b";
    api.apiPost.mockResolvedValue({ answer: "Wartung und Störungsbeseitigung.", contract_id: "0f8a3c2e-1b2d-4e5f-8a9b-0c1d2e3f4a5b", evidence: [] });
    render(<FloatingAssistant />);
    act(() => { window.dispatchEvent(new Event("medflux:assistant-toggle")); });
    await user.click(await screen.findByRole("button", { name: "Was umfasst die Leistung (Leistungsumfang)?" }));
    await waitFor(() => expect(api.apiPost).toHaveBeenCalledWith(expect.stringContaining("/api/ai/assistant"), { message: "Was umfasst die Leistung (Leistungsumfang)?", contract_id: "0f8a3c2e-1b2d-4e5f-8a9b-0c1d2e3f4a5b" }, 180000, expect.anything()));
    expect(await screen.findByText(/Wartung und Störungsbeseitigung/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Häufige Fragen" })).not.toBeInTheDocument();
  });
});

describe("Vertrag hinzufügen", () => {
  it("bietet Import und Anlegen ohne Dokument an und schließt mit Escape", async () => {
    const user = userEvent.setup();
    render(<AddContractMenu />);
    const button = await screen.findByRole("button", { name: /Vertrag hinzufügen/ });
    await user.click(button);
    expect(screen.getByRole("link", { name: /Dokument importieren/ })).toHaveAttribute("href", "/import");
    expect(screen.getByRole("link", { name: /Ohne Dokument anlegen/ })).toHaveAttribute("href", "/contracts/new");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("link", { name: /Dokument importieren/ })).not.toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it("zeigt Lesern keinen Knopf", async () => {
    auth.role = "viewer";
    const { container } = render(<AddContractMenu />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(container).toBeEmptyDOMElement();
  });
});
