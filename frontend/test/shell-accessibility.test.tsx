import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppTopbar from "@/components/shell/AppTopbar";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/contracts",
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/OrganizationScopePicker", () => ({
  default: () => <button type="button">Arbeitsbereich</button>,
}));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({
    account: {
      id: "u-1",
      display_name: "Max Mustermann",
      email: "max@example.test",
      is_developer: false,
    },
    membership: {
      organization_slug: "krankenhaus",
      organization_name: "Klinik",
    },
    role: "admin",
    logout: vi.fn(),
  }),
}));

describe("Application shell accessibility", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("opens Mein Profil directly and closes the account menu", async () => {
    const user = userEvent.setup();
    render(<AppTopbar />);

    const summary = screen.getByLabelText("Kontomenü öffnen");
    await user.click(summary);
    const profileButton = screen.getByRole("button", { name: "Mein Profil" });
    await user.click(profileButton);

    expect(pushMock).toHaveBeenCalledWith("/profile");
    expect((summary.closest("details") as HTMLDetailsElement).open).toBe(false);
  });

  it("closes the account menu with Escape and restores focus to its summary", async () => {
    const user = userEvent.setup();
    render(<AppTopbar />);

    const summary = screen.getByLabelText("Kontomenü öffnen");
    await user.click(summary);
    expect(screen.getByRole("button", { name: "Mein Profil" })).toBeVisible();

    const profileButton = screen.getByRole("button", { name: "Mein Profil" });
    profileButton.focus();
    await user.keyboard("{Escape}");

    const details = summary.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(summary).toHaveFocus();
  });

  it("submits the accessible global contract search into the contract list", async () => {
    const user = userEvent.setup();
    render(<AppTopbar />);

    const search = screen.getByRole("searchbox", { name: "Vertragsnummer suchen" });
    await user.type(search, "  CN-42  {Enter}");

    expect(pushMock).toHaveBeenCalledWith("/contracts?q=CN-42");
  });
});
