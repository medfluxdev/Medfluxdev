import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import EmptyState from "@/components/ui/EmptyState";
import KpiTile from "@/components/ui/KpiTile";

describe("KpiTile", () => {
  it("zeigt ohne echte Zahlen „—“ mit „Noch keine Daten“ statt eines erfundenen Werts", () => {
    const { rerender } = render(<KpiTile label="Jährliche Kosten" value={null} hint="aus den Finanzdaten" />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("Noch keine Daten")).toBeInTheDocument();
    expect(screen.queryByText("aus den Finanzdaten")).not.toBeInTheDocument();
    expect(screen.getByRole("article")).toHaveClass("kpi--empty");

    rerender(<KpiTile label="Jährliche Kosten" value={null} loading />);
    expect(screen.getByText("…")).toBeInTheDocument();
    expect(screen.queryByText("Noch keine Daten")).not.toBeInTheDocument();

    rerender(<KpiTile label="Laufende Verträge" value={0} hint="von 3" />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("von 3")).toBeInTheDocument();
    expect(screen.getByRole("article")).not.toHaveClass("kpi--empty");
  });

  it("macht mit href die ganze Kachel zum Link und traegt den Ton als Klasse", async () => {
    const { container } = render(
      <KpiTile label="Ungelesene Erinnerungen" value={2} tone="warning" icon={<svg viewBox="0 0 24 24" />} hint="Erinnerungen" href="/postfach" linkLabel="Zum Postfach" />,
    );
    const link = screen.getByRole("link", { name: /Ungelesene Erinnerungen.*Zum Postfach/ });
    expect(link).toHaveAttribute("href", "/postfach");
    expect(link).toHaveClass("kpi", "kpi--warning");
    expect(link.querySelector(".kpi-icon")).toHaveAttribute("aria-hidden", "true");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ist ohne Ton neutral", () => {
    render(<KpiTile label="Kosten" value="1 €" />);
    expect(screen.getByRole("article")).toHaveClass("kpi--neutral");
  });
});

describe("EmptyState", () => {
  it("zeigt die kompakte Variante mit Titel und Text und bleibt barrierefrei", async () => {
    const { container } = render(<EmptyState variant="compact" title="Alles entschieden">Nichts offen.</EmptyState>);
    expect(container.querySelector(".empty-state-compact")).not.toBeNull();
    expect(container.querySelector(".empty-state")).toBeNull();
    expect(screen.getByText("Alles entschieden")).toBeInTheDocument();
    expect(screen.getByText("Nichts offen.")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bleibt ohne variant beim bisherigen Block", () => {
    const { container } = render(<EmptyState title="Leer">Text</EmptyState>);
    expect(container.querySelector(".empty-state")).not.toBeNull();
  });
});
