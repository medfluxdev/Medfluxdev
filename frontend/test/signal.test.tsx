import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import Badge from "@/components/ui/Badge";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import StatusBadge from "@/components/ui/StatusBadge";

const TONES = ["critical", "warning", "info", "done", "ai", "neutral"] as const;

describe("Signal", () => {
  it("traegt Wort, Form und Farbklasse; die Form ist dekorativ", async () => {
    const { container } = render(<div>{TONES.map((tone) => <Signal key={tone} tone={tone}>{tone}</Signal>)}</div>);
    for (const tone of TONES) {
      const element = screen.getByText(tone).closest(".signal")!;
      expect(element).toHaveClass(`signal--${tone}`);
      expect(element.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    }
    expect(await axe(container)).toHaveNoViolations();
  });

  it("gibt jeder Stufe eine eigene Form (Farbsehschwäche)", () => {
    const { container } = render(<div>{TONES.map((tone) => <Signal key={tone} tone={tone}>{tone}</Signal>)}</div>);
    const shapes = Array.from(container.querySelectorAll(".signal svg")).map((svg) => svg.innerHTML);
    expect(new Set(shapes).size).toBe(TONES.length);
  });

  it("Badge, StatusBadge und InlineAlert nutzen die Formen der Signalstufen", () => {
    const { container } = render(<>
      <Badge tone="danger">Fehler</Badge>
      <Badge>Neutral</Badge>
      <StatusBadge tone="review" label="Zu prüfen" />
      <InlineAlert tone="success">Gespeichert</InlineAlert>
    </>);
    expect(screen.getByText("Fehler").querySelector(".signal-icon")).not.toBeNull();
    expect(screen.getByText("Neutral").querySelector(".signal-icon")).toBeNull();
    expect(screen.getByText("Zu prüfen").querySelector(".signal-icon")).not.toBeNull();
    expect(container.querySelector(".alert .signal-icon")).not.toBeNull();
    expect(container.querySelector(".sb-dot")).toBeNull();
  });
});
