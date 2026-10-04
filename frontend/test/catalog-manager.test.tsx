import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import CatalogManager from "@/components/catalogs/CatalogManager";

vi.mock("@/lib/domain-api/catalogs", () => ({
  LOOKUP_FIELD_LABEL: { storage_location: "Ablageort" },
  listContractTypes: vi.fn().mockResolvedValue({
    contract_types: [{ id: "t-1", code: "wartung", label: "Wartungsvertrag", is_active: true, is_confidential: false, retention_years: 10 }],
    contract_categories: [],
  }),
  listLookups: vi.fn().mockResolvedValue({ field_keys: ["storage_location"], items: [] }),
  getNumberRange: vi.fn().mockResolvedValue({ prefix: "", padding: 6, next_value: 12, reserved: [] }),
  createContractCategory: vi.fn(), createContractType: vi.fn(), createLookup: vi.fn(), loadDefaultCatalogs: vi.fn(),
  reserveNumbers: vi.fn(), updateContractCategory: vi.fn(), updateContractType: vi.fn(), updateLookup: vi.fn(), updateNumberRange: vi.fn(),
}));

describe("Kataloge", () => {
  it("nutzt echte Reiter mit Tastaturbedienung und bleibt barrierefrei", async () => {
    const user = userEvent.setup();
    const { container } = render(<CatalogManager organizationSlug="test-klinik" />);
    expect(await screen.findByRole("rowheader", { name: "Wartungsvertrag" })).toBeInTheDocument();
    const types = screen.getByRole("tab", { name: "Vertragstypen" });
    expect(types).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", types.id);
    expect(screen.getByRole("button", { name: "Standardkatalog ergänzen" })).toBeInTheDocument();
    types.focus();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Nummernkreis" })).toHaveAttribute("aria-selected", "true");
    expect(await axe(container)).toHaveNoViolations();
  });
});
