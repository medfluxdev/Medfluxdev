import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ValueOriginBadge from "@/components/contracts/detail/ValueOriginBadge";

describe("Vertragswerte – Herkunft", () => {
  it.each([
    ["extracted", "Extrahiert"],
    ["reviewed", "Geprüft"],
    ["corrected", "Korrigiert"],
    ["calculated", "Berechnet"],
    ["missing", "Fehlt"],
    ["system", "Systemwert"],
  ] as const)("zeigt %s als %s", (kind, label) => {
    render(<ValueOriginBadge kind={kind} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
