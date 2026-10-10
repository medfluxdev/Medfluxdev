import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewModeSetting from "@/components/settings/ReviewModeSetting";
import type { ReviewSettingsDto } from "@/lib/domain-api/reviewSettings";

const api = vi.hoisted(() => ({ getReviewSettings: vi.fn(), updateReviewSettings: vi.fn() }));
vi.mock("@/lib/domain-api/reviewSettings", () => api);

function settings(overrides: Partial<ReviewSettingsDto> = {}): ReviewSettingsDto {
  return {
    review_mode: "manual",
    review_mode_label: "Jede Angabe prüft ein Mensch",
    options: [
      { value: "manual", label: "Jede Angabe prüft ein Mensch" },
      { value: "auto_noncritical", label: "Nicht-kritische Angaben mit eindeutigem Beleg automatisch übernehmen" },
    ],
    can_edit: true,
    ...overrides,
  };
}

describe("Prüfmodus der Organisation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("zeigt beide Modi, erklärt die Grenze und speichert die Auswahl", async () => {
    const user = userEvent.setup();
    api.getReviewSettings.mockResolvedValue(settings());
    api.updateReviewSettings.mockResolvedValue(settings({ review_mode: "auto_noncritical" }));
    const { container } = render(<ReviewModeSetting />);
    const manual = await screen.findByRole("radio", { name: "Jede Angabe prüft ein Mensch" });
    expect(manual).toBeChecked();
    expect(screen.getByText(/Kritische Angaben .* prüft immer ein Mensch/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("radio", { name: /automatisch übernehmen/ }));
    expect(api.updateReviewSettings).toHaveBeenCalledWith("test-klinik", "auto_noncritical");
    await waitFor(() => expect(screen.getByRole("radio", { name: /automatisch übernehmen/ })).toBeChecked());
  });

  it("ist ohne Berechtigung nur lesbar", async () => {
    api.getReviewSettings.mockResolvedValue(settings({ can_edit: false }));
    render(<ReviewModeSetting />);
    expect(await screen.findByRole("radio", { name: "Jede Angabe prüft ein Mensch" })).toBeDisabled();
    expect(screen.getByText("Nur Administratoren können den Prüfmodus ändern.")).toBeInTheDocument();
  });

  it("zeigt einen Ladefehler statt einer stillen Voreinstellung", async () => {
    api.getReviewSettings.mockRejectedValue(new Error("offline"));
    render(<ReviewModeSetting />);
    expect(await screen.findByText("Der Prüfmodus konnte nicht geladen werden.")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });
});
