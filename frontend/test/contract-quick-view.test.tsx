import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import ContractQuickView from "@/components/register/ContractQuickView";

vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  getContractRegister: vi.fn().mockResolvedValue({
    contract_id: "c-1", register_number: "000001", business_status: "gueltig", review_pending: true,
    fields: {
      short_description: { value: "Wartung CT", display: null }, partner_id: { value: "p-1", display: "SIEMENS" },
      term_model: { value: "auto_renewal", display: null }, contract_type_id: { value: "t-1", display: "Wartung" },
      reminder_recipient_account_id: { value: null, display: null },
    },
    terms: { cancel_by: "2027-09-30", possible_end: "2027-12-31", actual_end: null, reminder_date: "2027-06-30" },
    retention: { deletion_from: "2038-01-01" },
    confidentiality: { effective: false },
  }),
}));

describe("Schnellansicht", () => {
  it("zeigt Kernfakten und schließt mit Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<ContractQuickView organizationSlug="test-klinik" contractId="c-1" onClose={onClose} />);
    expect(await screen.findByRole("heading", { name: "Wartung CT" })).toBeInTheDocument();
    expect(screen.getByText("Gültig · SIEMENS")).toBeInTheDocument();
    expect(screen.getByText("Kündbar bis").nextElementSibling).toHaveTextContent("30.09.2027");
    expect(screen.getByText(/noch nicht vollständig geprüft/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Öffnen" })).toHaveAttribute("href", "/contracts/c-1");
    expect(await axe(container)).toHaveNoViolations();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
