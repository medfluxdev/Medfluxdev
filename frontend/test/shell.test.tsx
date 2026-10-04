import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClientNav from "@/components/ClientNav";

let navPath = "/";
const push = vi.fn();
const logout = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => navPath,
  useRouter: () => ({ push, replace: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({ status: "ok" }),
  apiPut: vi.fn().mockResolvedValue({}),
}));

vi.mock("@/lib/domain-api/registerGrid", () => ({
  getGrid: vi.fn().mockResolvedValue({ items: [{ contract_id: "c-1", values: { register_number: "000001", short_description: "Wartung CT", partner: "SIEMENS" }, group: [] }] }),
}));

vi.mock("@/lib/domain-api/catalogs", () => ({
  listPartners: vi.fn().mockResolvedValue({ total: 1, items: [{ id: "p-1", short_name: "SIEMENS", name1: "Siemens Healthcare GmbH" }] }),
}));

vi.mock("@/components/assistant/FloatingAssistant", () => ({ default: () => null }));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({
    account: { id: "u-1", email: "admin@example.test", display_name: "Test Admin", is_active: true, is_developer: false, last_login_at: null, memberships: [] },
    membership: { organization_id: "org-1", organization_slug: "test-klinik", organization_name: "Test Klinik", role: "admin" },
    memberships: [{ organization_id: "org-1", organization_slug: "test-klinik", organization_name: "Test Klinik", role: "admin" }],
    organizationSlug: "test-klinik",
    loading: false,
    role: "admin",
    refresh: vi.fn(),
    selectOrganization: vi.fn(),
    logout,
  }),
}));

vi.mock("@/components/OrganizationScopePicker", () => ({
  default: () => <div aria-label="Arbeitsbereich auswählen">Test Klinik</div>,
}));

beforeEach(() => {
  navPath = "/";
  push.mockClear();
  logout.mockClear();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-text-size");
});

describe("App-Shell", () => {
  it("zeigt sechs Bereiche mit den wichtigsten Zielen", () => {
    render(<ClientNav>Inhalt</ClientNav>);
    const nav = screen.getByRole("navigation", { name: "Hauptnavigation" });
    expect(within(nav).getAllByRole("heading").map((heading) => heading.textContent)).toEqual(["Start", "Verträge", "Fristen", "Prüfung", "Auswertungen", "Verwaltung"]);
    expect(within(nav).getByRole("link", { name: "Mein Tag" })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: "Vertragsliste" })).toHaveAttribute("href", "/register");
    expect(within(nav).getByRole("link", { name: "Aufgaben" })).toHaveAttribute("href", "/work-queue");
    expect(within(nav).getByRole("link", { name: "Verwaltung" })).toHaveAttribute("href", "/admin");
    expect(within(nav).queryByRole("link", { name: "Entwicklung" })).not.toBeInTheDocument();
  });

  it("markiert den aktiven Bereich auch auf einer Vertragsseite", () => {
    navPath = "/contracts/c-1";
    render(<ClientNav>Inhalt</ClientNav>);
    const nav = screen.getByRole("navigation", { name: "Hauptnavigation" });
    expect(within(nav).getByRole("link", { name: "Vertragsliste" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("navigation", { name: "Brotkrümelnavigation" })).toHaveTextContent("VerträgeVertragslisteVertrag");
  });

  it("öffnet die Befehlspalette mit Strg+K und springt zu einem Vertrag", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.keyboard("{Control>}k{/Control}");
    const palette = screen.getByRole("dialog", { name: "Befehle und Suche" });
    await user.type(within(palette).getByRole("combobox"), "wartung");
    const option = await within(palette).findByRole("option", { name: /000001 · Wartung CT/ });
    await user.click(option);
    expect(push).toHaveBeenCalledWith("/contracts/c-1?tab=register");
  });

  it("bietet in der Palette die Volltextsuche und Seiten an", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByRole("button", { name: "Suchen und Befehle (Strg+K)" }));
    const input = within(screen.getByRole("dialog", { name: "Befehle und Suche" })).getByRole("combobox");
    await user.type(input, "hotline");
    await waitFor(() => expect(screen.getByRole("option", { name: /In allen Vertragsdokumenten suchen/ })).toBeInTheDocument());
    await user.clear(input);
    await user.type(input, "termi");
    await user.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/termine");
  });

  it("zeigt die Tastenkürzel mit ? und navigiert mit g v", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.keyboard("?");
    expect(screen.getByRole("dialog", { name: "Tastenkürzel" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.keyboard("gv");
    expect(push).toHaveBeenCalledWith("/register");
  });

  it("speichert Design und Textgröße aus dem Kontomenü", async () => {
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByLabelText("Kontomenü öffnen"));
    await user.selectOptions(screen.getByLabelText("Design"), "dark");
    await user.selectOptions(screen.getByLabelText("Textgröße"), "large");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(document.documentElement).toHaveAttribute("data-text-size", "large");
    expect(JSON.parse(localStorage.getItem("medflux.preferences") ?? "{}")).toMatchObject({ theme: "dark", textSize: "large" });
  });

  it("klappt die Seitenleiste ein und öffnet sie auf dem Telefon über die Menütaste", async () => {
    const user = userEvent.setup();
    const { container } = render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByRole("button", { name: "Seitenleiste einklappen" }));
    expect(container.querySelector(".shell")).toHaveClass("shell--collapsed");
    await user.click(screen.getByRole("button", { name: "Navigation öffnen" }));
    expect(container.querySelector(".shell-sidebar")).toHaveClass("is-open");
  });

  it("hat keine automatisierten A11y-Verstöße und genau einen Hauptinhalt", async () => {
    const { container } = render(<ClientNav>Inhalt</ClientNav>);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
    expect(await axe(container)).toHaveNoViolations();
  });
});
