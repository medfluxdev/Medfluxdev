import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeletionQueuePage from "@/app/admin/deletion/page";

const api = vi.hoisted(() => ({
  getContractDeletionCapabilities: vi.fn(),
  getContractDeletionQueue: vi.fn(),
  cancelContractDeletion: vi.fn(),
  confirmContractDeletion: vi.fn(),
  restoreDeletedContract: vi.fn(),
}));
vi.mock("@/lib/domain-api/contracts", () => api);

describe("Verwaltung → Vertragslöschung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractDeletionCapabilities.mockResolvedValue({ can_request: true, can_delete: true, can_restore: true, requires_confirmation: true });
    api.getContractDeletionQueue.mockResolvedValue({
      items: [
        { contract_id: "c-1", contract_number: "40015645", register_number: "000002", short_description: "Impella AIC", lifecycle_state: "pending_deletion", by_name: "Maria Becker", deleted_at: null },
        { contract_id: "c-2", contract_number: null, register_number: "000007", short_description: "Reinigung", lifecycle_state: "deleted", by_name: "Admin", deleted_at: "2026-10-10T08:00:00Z" },
      ],
      has_more: false, next_offset: null,
    });
    api.confirmContractDeletion.mockResolvedValue({ contract_id: "c-1", lifecycle_state: "deleted" });
    api.restoreDeletedContract.mockResolvedValue({ contract_id: "c-2", lifecycle_state: "active" });
  });

  it("zeigt Anträge mit Antragsteller, bestätigt nach Rückfrage und stellt wieder her", async () => {
    const user = userEvent.setup();
    const { container } = render(<DeletionQueuePage />);
    const pending = await screen.findByRole("heading", { name: "Beantragt (1)" });
    expect(pending.closest("section")).toHaveTextContent("000002 · Impella AIC");
    expect(pending.closest("section")).toHaveTextContent("von Maria Becker");
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Löschung von 000002 · Impella AIC bestätigen" }));
    const dialog = await screen.findByRole("dialog", { name: "Löschung bestätigen?" });
    await user.click(within(dialog).getByRole("button", { name: "Ja, löschen" }));
    await waitFor(() => expect(api.confirmContractDeletion).toHaveBeenCalledWith("c-1", "test-klinik"));

    await user.click(await screen.findByRole("button", { name: "000007 · Reinigung wiederherstellen" }));
    await waitFor(() => expect(api.restoreDeletedContract).toHaveBeenCalledWith("c-2", "test-klinik"));
  });

  it("ausgeschaltet: sagt es ruhig", async () => {
    api.getContractDeletionCapabilities.mockResolvedValue({ can_request: false, can_delete: false, can_restore: false, requires_confirmation: true });
    render(<DeletionQueuePage />);
    expect(await screen.findByText("Vertragslöschung ist ausgeschaltet")).toBeInTheDocument();
  });
});
