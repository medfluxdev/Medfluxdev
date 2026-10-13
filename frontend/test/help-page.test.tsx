import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import HelpPage from "@/app/hilfe/page";
import ShortcutHelp from "@/components/shell/ShortcutHelp";
import { SHORTCUTS } from "@/components/shell/useShortcuts";
import { HELP_SECTIONS, searchHelp } from "@/lib/help-content";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/hilfe" }));

describe("Hilfe", () => {
  it("zeigt alle Themen, das Inhaltsverzeichnis und alle Tastenkürzel; ohne Verstöße (axe)", async () => {
    const { container } = render(<HelpPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Hilfe" })).toBeInTheDocument();
    for (const section of HELP_SECTIONS) {
      expect(screen.getByRole("heading", { level: 2, name: section.title })).toBeInTheDocument();
      expect(within(screen.getByRole("navigation", { name: "Themen" })).getByRole("link", { name: section.title })).toHaveAttribute("href", `#${section.id}`);
    }
    const table = within(container.querySelector("#tastenkuerzel") as HTMLElement).getByRole("table");
    for (const item of SHORTCUTS) expect(within(table).getByText(item.keys)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Suche filtert Antworten und Kürzel und öffnet die Treffer", async () => {
    const user = userEvent.setup();
    render(<HelpPage />);
    await user.type(screen.getByLabelText("Hilfe durchsuchen"), "Kündigungsfrist");
    const entry = screen.getByText("Woher kommen die Fristen?").closest("details");
    expect(entry).toHaveAttribute("open");
    expect(screen.queryByText("Was zeigt „Mein Tag“?")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tastenkürzel" })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Hilfe durchsuchen"));
    await user.type(screen.getByLabelText("Hilfe durchsuchen"), "Strg");
    expect(screen.getByRole("heading", { name: "Tastenkürzel" })).toBeInTheDocument();
    expect(screen.getByText("Strg + S")).toBeInTheDocument();
    expect(screen.queryByText("g dann s")).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Hilfe durchsuchen"));
    await user.type(screen.getByLabelText("Hilfe durchsuchen"), "xyzxyz");
    expect(screen.getByRole("status")).toHaveTextContent("Keine Treffer.");
  });

  it("Suche ignoriert Umlaute und findet über den Abschnittstitel", () => {
    expect(searchHelp("kundigungsfrist").flatMap((section) => section.entries).map((entry) => entry.id)).toContain("fristen-berechnung");
    const finance = searchHelp("Kosten und Finanzen");
    expect(finance.map((section) => section.id)).toEqual(["finanzen"]);
    expect(finance[0].entries.length).toBe(HELP_SECTIONS.find((section) => section.id === "finanzen")?.entries.length);
    expect(searchHelp("  ")).toBe(HELP_SECTIONS);
  });

  it("interne Links zeigen auf vorhandene Sprungmarken", () => {
    const ids = new Set(HELP_SECTIONS.flatMap((section) => [section.id, ...section.entries.map((entry) => entry.id)]));
    for (const link of HELP_SECTIONS.flatMap((section) => section.entries.flatMap((entry) => entry.links ?? []))) {
      if (link.href.startsWith("/hilfe#")) expect(ids.has(link.href.slice(7))).toBe(true);
    }
  });

  it("Sprungmarken sind eindeutig", () => {
    const ids = [...HELP_SECTIONS.map((section) => section.id), ...HELP_SECTIONS.flatMap((section) => section.entries.map((entry) => entry.id)), "tastenkuerzel"];
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("Dialog „?“ führt zur Hilfe", () => {
    render(<ShortcutHelp open onClose={() => undefined} />);
    expect(screen.getByRole("link", { name: "Zur Hilfe" })).toHaveAttribute("href", "/hilfe#tastenkuerzel");
  });
});
