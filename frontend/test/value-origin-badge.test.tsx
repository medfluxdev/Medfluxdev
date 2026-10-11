import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ValueOriginBadge from "@/components/contracts/detail/ValueOriginBadge";

describe("Vertragswerte – Herkunft", () => {
  it.each([
    ["extracted", "KI-Vorschlag"],
    ["reviewed", "geprüft"],
    ["corrected", "korrigiert"],
    ["calculated", "berechnet"],
    ["missing", "Fehlt"],
    ["system", "gepflegt"],
  ] as const)("zeigt %s als %s", (kind, label) => {
    render(<ValueOriginBadge kind={kind} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
