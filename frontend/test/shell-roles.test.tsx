import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClientNav from "@/components/ClientNav";
import { recordRequest, clearRequestLog } from "@/lib/request-log";

const auth = vi.hoisted(() => ({
  role: "admin" as string,
  previewOf: null as string | null,
  isDeveloper: false,
  setPreviewRole: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/register",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({ apiGet: vi.fn().mockResolvedValue({ status: "ok" }) }));
vi.mock("@/components/assistant/FloatingAssistant", () => ({ default: () => null }));
vi.mock("@/components/OrganizationScopePicker", () => ({ default: () => <div>Test Klinik</div> }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({
    account: { id: "u-1", email: "dev@example.test", display_name: "Dana Dev", is_active: true, is_developer: auth.isDeveloper, last_login_at: null, memberships: [] },
    membership: { organization_id: "org-1", organization_slug: "test-klinik", organization_name: "Test Klinik", role: auth.role },
    memberships: [],
    organizationSlug: "test-klinik",
    loading: false,
    role: auth.role,
    previewOf: auth.previewOf,
    setPreviewRole: auth.setPreviewRole,
    refresh: vi.fn(),
    selectOrganization: vi.fn(),
    logout: vi.fn(),
  }),
}));

beforeEach(() => {
  auth.role = "admin";
  auth.previewOf = null;
  auth.isDeveloper = false;
  auth.setPreviewRole.mockClear();
  localStorage.clear();
  clearRequestLog();
});

describe("Rollenvorschau", () => {
  it("lässt Administratoren eine Rolle zur Vorschau wählen", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByLabelText("Kontomenü öffnen"));
    await user.selectOptions(screen.getByLabelText("Ansicht als Rolle"), "viewer");
    expect(auth.setPreviewRole).toHaveBeenCalledWith("viewer");
  });

  it("zeigt während der Vorschau einen Hinweis mit Ausweg und blendet Verwaltung aus", async () => {
    const user = userEvent.setup();
    auth.role = "viewer";
    auth.previewOf = "admin";
    render(<ClientNav>Inhalt</ClientNav>);
    expect(screen.getByText(/Sie sehen Medflux wie die Rolle/).closest("[role=status]")).toHaveTextContent("Ihre Rechte bleiben unverändert");
    expect(screen.queryByRole("link", { name: /Verwaltung/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Vorschau beenden" }));
    expect(auth.setPreviewRole).toHaveBeenCalledWith(null);
  });

  it("bietet Nicht-Administratoren keine Vorschau an", async () => {
    const user = userEvent.setup();
    auth.role = "reviewer";
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByLabelText("Kontomenü öffnen"));
    expect(screen.queryByLabelText("Ansicht als Rolle")).not.toBeInTheDocument();
  });
});

describe("Entwicklermodus", () => {
  it("ist nur für Entwickler schaltbar und zeigt API-Zeiten ohne Inhalte", async () => {
    const user = userEvent.setup();
    auth.isDeveloper = true;
    const { container } = render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByLabelText("Kontomenü öffnen"));
    await user.click(screen.getByLabelText(/Entwicklermodus/));
    recordRequest("GET", "http://localhost:8000/api/register/grid?organization_slug=test-klinik&q=geheim", 200, 1520.4);
    await user.click(screen.getByRole("button", { name: "Entwicklerdetails öffnen" }));
    const dialog = screen.getByRole("dialog", { name: "Entwicklerdetails" });
    expect(within(dialog).getByText("/api/register/grid")).toBeInTheDocument();
    expect(within(dialog).getByText("1520 ms")).toBeInTheDocument();
    expect(within(dialog).getByText(/1 langsamer als 1 s/)).toBeInTheDocument();
    expect(dialog).not.toHaveTextContent("geheim");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bietet den Schalter normalen Konten nicht an", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByLabelText("Kontomenü öffnen"));
    expect(screen.queryByLabelText(/Entwicklermodus/)).not.toBeInTheDocument();
  });
});
