import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { triggerEditShortcut, useShortcuts } from "@/components/shell/useShortcuts";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function Box({ name }: { name: string }) {
  const [editing, setEditing] = useState(false);
  return <section aria-label={name}>
    <h2>{name}</h2>
    <button type="button" data-shortcut="edit" onClick={() => setEditing(true)}>{name} bearbeiten</button>
    {editing ? <input aria-label={`${name} Feld`} /> : <span>{name} Ansicht</span>}
    <button type="button">{name} anderes</button>
  </section>;
}

function Page() {
  useShortcuts(() => undefined, () => undefined);
  return <><Box name="Erster" /><Box name="Zweiter" /></>;
}

describe("Tastenkürzel E: Bearbeiten", () => {
  it("bearbeitet den Kasten mit dem Fokus und setzt den Fokus ins erste Feld", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Page />);
    screen.getByRole("button", { name: "Zweiter anderes" }).focus();
    await user.keyboard("e");
    expect(screen.getByLabelText("Zweiter Feld")).toBeInTheDocument();
    expect(screen.queryByLabelText("Erster Feld")).not.toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(60); });
    expect(screen.getByLabelText("Zweiter Feld")).toHaveFocus();
    vi.useRealTimers();
  });

  it("nicht beim Tippen in einem Feld", async () => {
    const user = userEvent.setup();
    render(<Page />);
    act(() => screen.getByRole("button", { name: "Erster bearbeiten" }).click());
    await user.click(screen.getByLabelText("Erster Feld"));
    await user.keyboard("e");
    expect(screen.getByLabelText("Erster Feld")).toHaveValue("e");
    expect(screen.queryByLabelText("Zweiter Feld")).not.toBeInTheDocument();
  });

  it("ohne passende Knöpfe: false", () => {
    render(<p>Leer</p>);
    expect(triggerEditShortcut()).toBe(false);
  });
});
