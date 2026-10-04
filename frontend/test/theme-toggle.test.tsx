import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import ThemeToggle from "@/components/shell/ThemeToggle";

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("Design-Schalter", () => {
  it("wechselt zwischen Hell und Dunkel und merkt sich die Wahl", () => {
    render(<ThemeToggle />);
    const toggle = screen.getByRole("switch", { name: "Dunkles Design" });
    expect(toggle).toHaveAttribute("aria-checked", "false");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(JSON.parse(localStorage.getItem("medflux.preferences") ?? "{}")).toMatchObject({ theme: "dark" });

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });
});
