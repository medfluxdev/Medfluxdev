import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import CommandPalette from "@/components/shell/CommandPalette";
import { setPageCommands } from "@/lib/page-commands";

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
