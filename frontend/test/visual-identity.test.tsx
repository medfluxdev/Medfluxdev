import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MedFluxLogo from "@/components/brand/MedFluxLogo";

describe("MedFlux visual identity", () => {
  it("renders the approved product name and descriptor", () => {
    const { container } = render(<MedFluxLogo showDescriptor />);
    expect(screen.getByLabelText("MedFlux")).toBeInTheDocument();
    expect(screen.getByText("Med")).toBeInTheDocument();
    expect(screen.getByText("Flux")).toBeInTheDocument();
    expect(screen.getByText("Healthcare Intelligence Platform")).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a mark-only compact version without duplicate visible copy", () => {
    const { container } = render(<MedFluxLogo compact />);
    expect(screen.getByLabelText("MedFlux")).toBeInTheDocument();
    expect(container.querySelector(".medflux-logo__copy")).not.toBeInTheDocument();
    expect(container.querySelector(".medflux-logo__mark")).toBeInTheDocument();
  });
});
