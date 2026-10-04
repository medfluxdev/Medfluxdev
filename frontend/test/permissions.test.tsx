import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import PermissionMatrixView from "@/components/access/PermissionMatrixView";

vi.mock("@/lib/domain-api/access", () => ({
  getPermissionMatrix: vi.fn().mockResolvedValue({
    roles: [{ key: "admin", label: "Administration" }, { key: "viewer", label: "Lesen" }],
    permissions: [
      { key: "contract.read", label: "Verträge ansehen", area: "Verträge", roles: ["admin", "viewer"] },
      { key: "catalog.admin", label: "Kataloge und Nummernkreis", area: "Administration", roles: ["admin"] },
    ],
    role: "viewer",
    granted: ["contract.read"],
  }),
}));

describe("Rollen & Rechte", () => {
  it("zeigt die Matrix und markiert eigene Rechte", async () => {
    const { container } = render(<PermissionMatrixView organizationSlug="test-klinik" />);
    const row = (await screen.findByRole("rowheader", { name: /Kataloge und Nummernkreis/ })).closest("tr")!;
    expect(within(row).getByLabelText("erlaubt")).toBeInTheDocument();
    expect(within(row).getByLabelText("nicht erlaubt")).toBeInTheDocument();
    expect(screen.getByText("Lesen", { selector: "strong" })).toBeInTheDocument();
    expect(within(screen.getByRole("rowheader", { name: /Verträge ansehen/ })).getByText("Ihr Recht")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
