import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeadlinesAndTasksPage from "@/app/fristen/page";
import AdminNav from "@/components/shell/AdminNav";

const auth = vi.hoisted(() => ({ role: "admin", is_developer: false }));
vi.mock("@/components/auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => ({
    account: { id: "u-1", is_developer: auth.is_developer, memberships: [] },
    organizationSlug: "test-klinik",
    role: auth.role,
    previewOf: null,
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/roles",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/components/deadlines/DeadlineList", () => ({ default: () => <p>Terminliste</p> }));
vi.mock("@/components/deadlines/RenewalOverview", () => ({ default: () => <p>Entscheidungsliste</p> }));
vi.mock("@/components/work-queue/TaskQueue", () => ({ default: () => <p>Aufgabenliste</p> }));

beforeEach(() => {
  auth.role = "admin";
  auth.is_developer = false;
  window.history.replaceState(null, "", "/fristen");
});

describe("Fristen & Aufgaben", () => {
  it("zeigt Aufgaben (zuerst), Termine und Entscheidungen als Reiter und merkt den Reiter in der Adresse", async () => {
    const user = userEvent.setup();
    const { container } = render(<DeadlinesAndTasksPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Fristen & Aufgaben" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Aufgaben", "Termine", "Kündigungsentscheidungen"]);
    expect(screen.getByRole("tab", { name: "Aufgaben" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Aufgabenliste")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Kündigungsentscheidungen" }));
    expect(screen.getByText("Entscheidungsliste")).toBeInTheDocument();
    expect(window.location.search).toBe("?ansicht=entscheidungen");

    await user.click(screen.getByRole("tab", { name: "Termine" }));
    expect(screen.getByText("Terminliste")).toBeInTheDocument();
    expect(window.location.search).toBe("?ansicht=termine");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("öffnet den Reiter aus der Adresse", () => {
    window.history.replaceState(null, "", "/fristen?ansicht=aufgaben");
    render(<DeadlinesAndTasksPage />);
    expect(screen.getByRole("tab", { name: "Aufgaben" })).toHaveAttribute("aria-selected", "true");
  });

  it("zeigt Lesern keine Aufgaben", () => {
    auth.role = "viewer";
    window.history.replaceState(null, "", "/fristen?ansicht=aufgaben");
    render(<DeadlinesAndTasksPage />);
    expect(screen.queryByRole("tab", { name: "Aufgaben" })).not.toBeInTheDocument();
    expect(screen.getByText("Terminliste")).toBeInTheDocument();
  });
});

describe("Verwaltung – Bereichsnavigation", () => {
  it("zeigt Administratoren alle Verwaltungsseiten und markiert die aktuelle", async () => {
    const { container } = render(<AdminNav />);
    const nav = screen.getByRole("navigation", { name: "Verwaltung" });
    for (const name of ["Übersicht", "Benutzer", "Rollen & Rechte", "Stammdaten", "Nummernkreis", "Vertragslöschung", "Einstellungen"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    expect(within(nav).getByRole("link", { name: "Rollen & Rechte" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).queryByRole("link", { name: "Entwicklung" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt anderen Rollen nur, was sie öffnen dürfen", () => {
    auth.role = "contract_manager";
    render(<AdminNav />);
    const nav = screen.getByRole("navigation", { name: "Verwaltung" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Rollen & Rechte", "Stammdaten", "Vertragsregeln", "Aktivitäten & Protokoll", "Sicherheit & Datenschutz"]);
  });
});
