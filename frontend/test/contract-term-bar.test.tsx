import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import ContractTermBar, { remaining } from "@/components/contracts/detail/ContractTermBar";

describe("Laufzeitleiste", () => {
  it("zeigt Beginn, Heute mit Restlaufzeit, Ende und beschreibt alles in Worten", async () => {
    const { container } = render(<ContractTermBar start="2025-05-05" end="2029-03-31" cancelBy={null} today="2026-10-11" />);
    const bar = screen.getByRole("img");
    expect(bar).toHaveAccessibleName(/Laufzeit vom 05\.05\.2025 bis 31\.03\.2029, heute \d+ Prozent vergangen, noch 2 Jahre, 5 Monate, Kündigungsfrist fehlt/);
    expect(screen.getByText("Kündigungsfrist fehlt").closest(".signal")).toHaveClass("signal--critical");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Kündigungstermin: neutral, in 30 Tagen Warnung, verstrichen kritisch", () => {
    const { rerender } = render(<ContractTermBar start="2025-01-01" end="2028-12-31" cancelBy="2027-09-30" today="2026-10-11" />);
    expect(screen.getByText("Kündbar bis 30.09.2027")).not.toHaveClass("signal");
    rerender(<ContractTermBar start="2025-01-01" end="2028-12-31" cancelBy="2026-10-31" today="2026-10-11" />);
    expect(screen.getByText("Kündbar bis 31.10.2026").closest(".signal")).toHaveClass("signal--warning");
    rerender(<ContractTermBar start="2025-01-01" end="2028-12-31" cancelBy="2026-09-30" today="2026-10-11" />);
    expect(screen.getByText("Kündbar bis 30.09.2026 – verstrichen").closest(".signal")).toHaveClass("signal--critical");
  });

  it("ohne Beginn oder Ende keine Leiste; Restlaufzeit in Worten", () => {
    const { container } = render(<ContractTermBar start="2025-01-01" end={null} cancelBy={null} today="2026-10-11" />);
    expect(container).toBeEmptyDOMElement();
    expect(remaining("2026-10-11", "2026-10-20")).toBe("noch 9 Tage");
    expect(remaining("2026-10-11", "2027-10-11")).toBe("noch 1 Jahr");
    expect(remaining("2026-10-11", "2027-01-11")).toBe("noch 3 Monate");
  });
});
