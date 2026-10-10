import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import CoverageValue from "@/components/ui/CoverageValue";
import { coverageNote } from "@/lib/format";

describe("CoverageValue", () => {
  it("zeigt unbekannte Summen als „—“ statt 0,00 €", () => {
    render(<CoverageValue value={null} known={0} missing={3} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText(/Keine gepflegten Kostendaten \(3 Verträge\)/)).toBeInTheDocument();
    expect(screen.queryByText(/0,00/)).not.toBeInTheDocument();
  });

  it("kennzeichnet Teilsummen und verlinkt die fehlenden Verträge", async () => {
    const { container } = render(<CoverageValue value="4200.00" known={3} missing={4} missingHref="/register?x=1" />);
    expect(screen.getByText(/4\.200,00/)).toBeInTheDocument();
    expect(screen.getByText(/bekannt für 3 von 7 Verträgen/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "fehlende anzeigen" })).toHaveAttribute("href", "/register?x=1");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt einen echten Nullbetrag normal und andere Währungen getrennt", () => {
    render(<CoverageValue value="0.00" known={1} missing={0} otherCurrencies={{ CHF: "50.00" }} />);
    expect(screen.getByText(/^0,00/)).toBeInTheDocument();
    expect(screen.getByText(/50,00.*CHF/)).toBeInTheDocument();
  });
});

describe("coverageNote", () => {
  it("ist leer, wenn alles bekannt ist oder nichts zu zählen ist", () => {
    expect(coverageNote(5, 0)).toBe("");
    expect(coverageNote(0, 0)).toBe("");
    expect(coverageNote(2, 1)).toBe("bekannt für 2 von 3 Verträgen");
    expect(coverageNote(0, 1, true)).toBe("Keine gepflegten Kostendaten (1 Vertrag)");
  });
});
