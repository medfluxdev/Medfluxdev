import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import SettingsNavigation from "@/components/SettingsNavigation";

beforeEach(() => {
  window.history.replaceState(null, "", "/settings");
  window.scrollTo = vi.fn();
  window.matchMedia = vi.fn().mockReturnValue({ matches: true });
});

it("navigates with history, active indication, reduced motion and focus", () => {
  render(<><SettingsNavigation /><h2 id="settings-lokale-ki" tabIndex={-1}>Target</h2></>);
  fireEvent.click(screen.getByRole("link", { name: "Lokale KI" }));
  expect(window.location.hash).toBe("#settings-lokale-ki");
  expect(screen.getByRole("link", { name: "Lokale KI" })).toHaveAttribute("aria-current", "location");
  expect(screen.getByText("Target")).toHaveFocus();
  expect(window.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ behavior: "auto" }));
});

it("handles back/forward hashes without adding history entries", async () => {
  render(<><SettingsNavigation /><h2 id="settings-diagnose" tabIndex={-1}>Target</h2></>);
  window.history.replaceState(null, "", "#settings-diagnose");
  fireEvent.popState(window);
  await waitFor(() => expect(screen.getByRole("link", { name: "System & Diagnose" }))
    .toHaveAttribute("aria-current", "location"));
});
