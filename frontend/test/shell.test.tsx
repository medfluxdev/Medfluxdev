import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClientNav, { NAV_ITEMS } from "@/components/ClientNav";
import RootLayout from "@/app/layout";

vi.mock("next/navigation", () => ({
  usePathname: () => navPath,
  useRouter: () => ({ push: vi.fn() }),
}));

let navPath = "/";

beforeEach(() => {
  navPath = "/";
});

describe("App-Shell (STEP 15)", () => {
  it("rendert die Navigationspunkte mit den erwarteten Zielen", () => {
    render(<ClientNav />);
    expect(screen.getByRole("link", { name: "Übersicht" })).toHaveAttribute(
      "href",
      "/"
    );
    expect(screen.getByRole("link", { name: "Verträge" })).toHaveAttribute(
      "href",
      "/contracts"
    );
    expect(screen.getByRole("link", { name: "Arbeitsliste" })).toHaveAttribute(
      "href",
      "/work-queue"
    );
    expect(screen.getByRole("link", { name: "Geräte" })).toHaveAttribute(
      "href",
      "/equipment"
    );
    expect(screen.getByRole("link", { name: "Import" })).toHaveAttribute(
      "href",
      "/import"
    );
    expect(screen.getByRole("link", { name: "Einstellungen" })).toHaveAttribute(
      "href",
      "/settings"
    );
    expect(NAV_ITEMS).toHaveLength(6);
  });

  it("markiert den aktiven Navigationspunkt mit aria-current='page'", () => {
    navPath = "/contracts";
    render(<ClientNav />);
    expect(
      screen.getByRole("link", { name: "Verträge" })
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Übersicht" })).not.toHaveAttribute(
      "aria-current"
    );
  });

  it("indiziert die Hauptnavigation korrekt (kein aria-Disabled-Stub mehr)", () => {
    render(<ClientNav />);
    const nav = screen.getByRole("navigation", { name: "Hauptnavigation" });
    expect(nav.querySelectorAll("[aria-disabled]")).toHaveLength(0);
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße in der Navigation", async () => {
    const { container } = render(<ClientNav />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("liefert einen Skip-Link zum Hauptinhalt im Root-Layout", () => {
    render(<RootLayout>{null}</RootLayout>);
    const skip = screen.getByRole("link", {
      name: "Zum Hauptinhalt springen",
    });
    expect(skip).toHaveAttribute("href", "#main-content");
    expect(skip).toHaveClass("skip-link");
  });
});