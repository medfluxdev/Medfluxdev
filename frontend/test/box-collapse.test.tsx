import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it } from "vitest";
import { enhanceBoxes, revealBox } from "@/lib/box-collapse";

function Page() {
  return <main>
    <section className="cw-section" aria-labelledby="sla-heading">
      <div className="cw-section-head"><div><h2 id="sla-heading">SLA</h2><p>Zugesagte Zeiten</p></div></div>
      <p id="sla-body">Reaktionszeit 4 Stunden</p>
    </section>
    <section className="card"><h2>Offene Punkte <span>4</span></h2><p>Inhalt</p></section>
    <section className="cw-section collapsible"><div className="cw-section-head"><h2>Eigener Knopf</h2></div></section>
    <section className="cw-section" data-no-collapse><div className="cw-section-head"><h2>Ohne</h2></div></section>
    <section className="cw-section"><p>Ohne Überschrift</p></section>
  </main>;
}

describe("Jeder Kasten einklappbar", () => {
  beforeEach(() => window.localStorage.clear());

  it("Knopf nur an Kästen mit Überschrift, merkt den Zustand und klappt bei Sprüngen auf", async () => {
    const user = userEvent.setup();
    const { container, unmount } = render(<Page />);
    enhanceBoxes(container);
    enhanceBoxes(container); // mehrfach aufrufbar
    expect(container.querySelectorAll(".box-toggle")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Offene Punkte einklappen" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    const toggle = screen.getByRole("button", { name: "SLA einklappen" });
    await user.click(toggle);
    const box = container.querySelector("section[aria-labelledby='sla-heading']")!;
    expect(box).toHaveAttribute("data-collapsed");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAccessibleName("SLA aufklappen");
    unmount();

    // Neu gerendert: Zustand aus dem Speicher.
    const again = render(<Page />);
    enhanceBoxes(again.container);
    const restored = again.container.querySelector("section[aria-labelledby='sla-heading']")!;
    expect(restored).toHaveAttribute("data-collapsed");
    revealBox(again.container.querySelector("#sla-body"));
    expect(restored).not.toHaveAttribute("data-collapsed");
    expect(window.localStorage.getItem("medflux.collapsed-boxes")).toBe("[]");
  });
});
