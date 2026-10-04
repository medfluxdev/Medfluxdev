import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CalculationBasisPanel, { hasCalculationBasis } from "@/components/contracts/detail/CalculationBasisPanel";

describe("Berechnungsgrundlage", () => {
  it("zeigt deterministische Berechnung inklusive Inputs", () => {
    render(
      <CalculationBasisPanel
        title="Spätester Kündigungstermin"
        basis={{
          explanation: "Vertragsende minus Kündigungsfrist.",
          inputs: {
            contract_end_date: "31.12.2026",
            notice_period: "3 Monate",
          },
        }}
      />
    );

    expect(screen.getByText("Berechnet")).toBeInTheDocument();
    expect(screen.getByText("Spätester Kündigungstermin")).toBeInTheDocument();
    expect(screen.getByText("Vertragsende minus Kündigungsfrist.")).toBeInTheDocument();
    expect(screen.getByText("31.12.2026")).toBeInTheDocument();
    expect(screen.getByText("3 Monate")).toBeInTheDocument();
    expect(screen.getByText(/nicht von der KI geschätzt/)).toBeInTheDocument();
  });

  it("rendert ohne echte Grundlage nichts", () => {
    const { container } = render(
      <CalculationBasisPanel title="Berechnung" basis={{ explanation: null, inputs: {} }} />
    );
    expect(container).toBeEmptyDOMElement();
    expect(hasCalculationBasis({ explanation: null, inputs: {} })).toBe(false);
  });
});
