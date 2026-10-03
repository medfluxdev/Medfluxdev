import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractTable from "@/components/contracts/ContractTable";
import type { ContractListItem } from "@/lib/contract-types";

const replaceMock = vi.fn();
const pushMock = vi.fn();
let search = "status=active&requires_review=true";

vi.mock("next/navigation", () => ({
  usePathname: () => "/contracts",
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  useSearchParams: () => new URLSearchParams(search),
}));

const contract: ContractListItem = {
  contract_id: "11111111-1111-1111-1111-111111111111",
  contract_number: "V-100",
  contract_title: "Wartungsvertrag MRT",
  supplier: "MedTech GmbH",
  status: "active",
  risk_level: "medium",
  annual_cost: { currency: "EUR", amount: "12000", unreliable: false },
  contract_end_date: "2026-12-31",
  latest_cancellation_date: "2026-09-30",
  primary_warning: { warning_type: "contract_end_approaching", severity: "medium", title_de: "Vertragsende nähert sich", target_date: "2026-12-31" },
  requires_action: true,
  requires_review: true,
};

beforeEach(() => {
  replaceMock.mockReset();
  pushMock.mockReset();
  search = "status=active&requires_review=true";
  localStorage.clear();
  sessionStorage.clear();
});

describe("Vertragsliste – Arbeitsansicht", () => {
  it("zeigt aktive Filter als einzeln entfernbare Chips", async () => {
    const user = userEvent.setup();
    render(<ContractTable items={[contract]} />);

    const chip = screen.getByRole("button", { name: /Status active entfernen/ });
    expect(chip).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Manuelle Prüfung Ja entfernen/ })).toBeInTheDocument();

    await user.click(chip);
    expect(replaceMock).toHaveBeenCalledWith("/contracts?requires_review=true", { scroll: false });
  });

  it("speichert Dichte und Spaltenpräferenz lokal", async () => {
    const user = userEvent.setup();
    render(<ContractTable items={[contract]} />);

    await user.click(screen.getByRole("button", { name: "Kompakt" }));
    expect(localStorage.getItem("medflux.contractTable.density")).toBe("compact");

    await user.click(screen.getByRole("button", { name: "Spalten" }));
    await user.click(screen.getByRole("checkbox", { name: "Warnung" }));
    expect(localStorage.getItem("medflux.contractTable.columns")).toContain('"warning":false');
  });

  it("öffnet eine Schnellansicht ohne die Liste zu verlassen", async () => {
    const user = userEvent.setup();
    render(<ContractTable items={[contract]} />);

    await user.click(screen.getByRole("button", { name: /Wartungsvertrag MRT in Schnellansicht öffnen/ }));
    const preview = screen.getByRole("complementary", { name: "Vertrag Schnellansicht" });
    expect(preview).toBeInTheDocument();
    expect(within(preview).getByText((content) => content.replace(/\s/g, " ").includes("12.000,00") && content.includes("€"))).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("speichert eine lokale Ansicht mit der aktuellen Query", async () => {
    const user = userEvent.setup();
    render(<ContractTable items={[contract]} />);

    const nameField = screen.getByRole("textbox", { name: "Name der Ansicht" });
    await user.type(nameField, "Prüfung offen");
    await user.click(screen.getByRole("button", { name: "Ansicht speichern" }));

    const stored = localStorage.getItem("medflux.contracts.savedViews") ?? "";
    expect(stored).toContain("Prüfung offen");
    expect(stored).toContain("requires_review=true");
  });
});