import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import CollapsibleSection from "@/components/ui/CollapsibleSection";

describe("Karten starten eingeklappt", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("zu, bis die Person aufklappt; das Aufklappen gilt für die Sitzung", async () => {
    const user = userEvent.setup();
    const view = render(<CollapsibleSection id="start-closed" title="Testkarte" defaultCollapsed><p>Inhalt</p></CollapsibleSection>);
    expect(screen.getByRole("button", { name: "Testkarte aufklappen" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Inhalt")).not.toBeVisible();
    await user.click(screen.getByRole("button", { name: "Testkarte aufklappen" }));
    expect(screen.getByText("Inhalt")).toBeVisible();
    view.unmount();
    render(<CollapsibleSection id="start-closed" title="Testkarte" defaultCollapsed><p>Inhalt</p></CollapsibleSection>);
    expect(screen.getByText("Inhalt")).toBeVisible();
  });

  it("forceOpen (z. B. Bearbeiten, Sprungziel) öffnet trotzdem", () => {
    render(<CollapsibleSection id="start-forced" title="Testkarte 2" defaultCollapsed forceOpen><p>Sichtbar</p></CollapsibleSection>);
    expect(screen.getByText("Sichtbar")).toBeVisible();
  });
});
