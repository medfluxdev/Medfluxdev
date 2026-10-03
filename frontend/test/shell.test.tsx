import { render, screen } from "@testing-library/react";
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
}));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({
    account: {
      id: "u-1",
      email: "admin@example.test",
      display_name: "Test Admin",
      is_active: true,
      is_developer: false,
      last_login_at: null,
      memberships: [],
    },
    membership: {
      organization_id: "org-1",
      organization_slug: "test-klinik",
      organization_name: "Test Klinik",
      role: "admin",
    },
    memberships: [{
      organization_id: "org-1",
      organization_slug: "test-klinik",
      organization_name: "Test Klinik",
      role: "admin",
    }],
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
});

describe("App-Shell", () => {
  it("rendert die wichtigsten Navigationsziele", () => {
    render(<ClientNav>Inhalt</ClientNav>);
    expect(screen.getByRole("link", { name: "Übersicht" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Verträge" })).toHaveAttribute("href", "/contracts");
    expect(screen.getByRole("link", { name: "To-dos" })).toHaveAttribute("href", "/work-queue");
    expect(screen.getByRole("link", { name: "Import" })).toHaveAttribute("href", "/import");
    expect(screen.getByRole("link", { name: "Prüfungen" })).toHaveAttribute("href", "/review");
    expect(screen.getByRole("link", { name: "Einstellungen" })).toHaveAttribute("href", "/settings");
  });

  it("markiert den aktiven Navigationspunkt mit aria-current='page'", () => {
    navPath = "/contracts";
    render(<ClientNav>Inhalt</ClientNav>);
    expect(screen.getByRole("link", { name: "Verträge" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Übersicht" })).not.toHaveAttribute("aria-current");
  });

  it("liefert eine benannte Hauptnavigation und globale Suche", () => {
    render(<ClientNav>Inhalt</ClientNav>);
    expect(screen.getByRole("navigation", { name: "Hauptnavigation" })).toBeInTheDocument();
    expect(screen.getByRole("search", { name: "Verträge durchsuchen" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Vertragsnummer suchen" })).toBeInTheDocument();
  });

  it("hat keine automatisierten A11y-Verstöße im Shell-Grundzustand", async () => {
    const { container } = render(<ClientNav>Inhalt</ClientNav>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("rendert genau einen Hauptinhalt-Anker", () => {
    const { container } = render(<ClientNav>Inhalt</ClientNav>);
    expect(container.querySelectorAll("#main-content")).toHaveLength(1);
  });
});
