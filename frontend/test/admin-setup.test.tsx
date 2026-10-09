import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import SetupChecklist from "@/components/admin/SetupChecklist";

const api = vi.hoisted(() => ({
  getSetupStatus: vi.fn().mockResolvedValue({
    done: 1, total: 3, required: 2, required_open: 1,
    items: [
      { key: "organization", label: "Organisationsstruktur", status: "ok", detail: "1 Krankenhäuser, 2 Bereiche, 0 Kostenstellen", href: "/stammdaten/abteilungen" },
      { key: "users", label: "Benutzer und Rollen", status: "todo", detail: "1 aktive Zugänge", href: "/settings/users" },
      { key: "mail", label: "E-Mail-Versand (SMTP)", status: "optional", detail: "nicht eingerichtet", href: "/settings" },
    ],
  }),
}));

vi.mock("@/lib/domain-api/adminSetup", () => api);

describe("Einrichtungs-Checkliste", () => {
  it("zeigt offene, erledigte und optionale Schritte mit Link", async () => {
    const { container } = render(<SetupChecklist organizationSlug="test-klinik" />);
    expect(await screen.findByText(/1 notwendige Schritte offen · 1 von 3 erledigt/)).toBeInTheDocument();
    const users = screen.getByRole("link", { name: "Benutzer und Rollen" }).closest("li")!;
    expect(within(users).getByText("Offen")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Organisationsstruktur" })).toHaveAttribute("href", "/stammdaten/abteilungen");
    expect(screen.getByText("Optional")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bietet bei Fehler erneutes Laden an", async () => {
    api.getSetupStatus.mockRejectedValueOnce(new Error("x"));
    render(<SetupChecklist organizationSlug="test-klinik" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("konnte nicht geladen werden");
  });
});
