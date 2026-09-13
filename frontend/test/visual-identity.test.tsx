import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MedFluxLogo from "@/components/brand/MedFluxLogo";

describe("MedFlux visual identity", () => {
  it("renders approved Main Logo 01 as the canonical brand asset", () => {
    render(<MedFluxLogo />);
    const logo = screen.getByRole("img", { name: "MedFlux — Healthcare Intelligence Platform" });
    expect(logo).toHaveAttribute("src", expect.stringContaining("medflux-main-logo.png"));
  });

  it("uses the same Main Logo 01 asset in compact contexts", () => {
    const { container } = render(<MedFluxLogo compact />);
    const logo = screen.getByRole("img", { name: "MedFlux — Healthcare Intelligence Platform" });
    expect(logo).toHaveAttribute("src", expect.stringContaining("medflux-main-logo.png"));
    expect(container.querySelector(".medflux-logo--compact")).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeInTheDocument();
  });
});
