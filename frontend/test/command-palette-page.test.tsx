import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import CommandPalette from "@/components/shell/CommandPalette";
import { setPageCommands } from "@/lib/page-commands";
import { HELP_SECTIONS } from "@/lib/help-content";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/contracts/c-1" }));

afterEach(() => { act(() => setPageCommands([])); vi.clearAllMocks(); });

describe("Strg+K: was dem Vertrag fehlt", () => {
  it("zeigt die Lücken der offenen Vertragsakte zuerst und springt mit Enter dorthin", async () => {
    const user = userEvent.setup();
    act(() => setPageCommands([
      { id: "gap:term_start_date", label: "Vertragsbeginn erfassen", hint: "nötig für „Gültig“", href: "/contracts/c-1?tab=register&feld=term_start_date" },
      { id: "gap:annual_cost", label: "Kosten erfassen", hint: "keine Finanzeinträge gepflegt", href: "/contracts/c-1?tab=finance&abschnitt=entries" },
    ]));
    render(<CommandPalette open onClose={() => undefined} onShowShortcuts={() => undefined} />);
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("Vertragsbeginn erfassen");
    expect(screen.getByText("Dieser Vertrag")).toBeInTheDocument();

    await user.type(screen.getByRole("combobox"), "kosten");
    expect(screen.getAllByRole("option")[0]).toHaveTextContent("Kosten erfassen");
    await user.keyboard("{Enter}");
    expect(router.push).toHaveBeenCalledWith("/contracts/c-1?tab=finance&abschnitt=entries");
  });

  it("ohne Vertragsakte gibt es keine Vertragsbefehle", () => {
    render(<CommandPalette open onClose={() => undefined} onShowShortcuts={() => undefined} />);
    expect(screen.queryByText("Dieser Vertrag")).not.toBeInTheDocument();
  });
});

describe("Strg+K: Antworten aus der Hilfe", () => {
  it("findet Hilfe-Antworten ohne Umlaute und springt zur Antwort", async () => {
    const user = userEvent.setup();
    render(<CommandPalette open onClose={() => undefined} onShowShortcuts={() => undefined} />);
    await user.type(screen.getByRole("combobox"), "kundigungsentscheidung");
    const option = screen.getByRole("option", { name: /Kündigungsentscheidung vor/ });
    expect(screen.getByText("Hilfe")).toBeInTheDocument();
    await user.click(option);
    expect(router.push).toHaveBeenCalledWith("/hilfe#kuendigungsentscheidung");
  });

  it("zeigt bei einem Zeichen noch keine Hilfe-Antworten", async () => {
    const user = userEvent.setup();
    render(<CommandPalette open onClose={() => undefined} onShowShortcuts={() => undefined} />);
    await user.type(screen.getByRole("combobox"), "k");
    const questions = HELP_SECTIONS.flatMap((section) => section.entries.map((entry) => entry.question));
    expect(screen.queryAllByRole("option").some((option) => questions.includes(option.textContent ?? ""))).toBe(false);
  });
});
