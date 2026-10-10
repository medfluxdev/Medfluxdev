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

  it("macht mit href die ganze Kachel zum Link und bleibt neutral (Ruhe & Signal)", async () => {
    const { container } = render(
      <KpiTile label="Ungelesene Erinnerungen" value={2} icon={<svg viewBox="0 0 24 24" />} hint="Erinnerungen" href="/postfach" linkLabel="Zum Postfach" />,
    );
    const link = screen.getByRole("link", { name: /Ungelesene Erinnerungen.*Zum Postfach/ });
    expect(link).toHaveAttribute("href", "/postfach");
    expect(link).toHaveClass("kpi");
    expect(link.className).not.toMatch(/kpi--(warning|danger|info|success)/);
    expect(link.querySelector(".kpi-icon")).toHaveAttribute("aria-hidden", "true");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt Aufmerksamkeit nur als Signal mit Form und Wort", () => {
    const { container } = render(<KpiTile label="Jährliche Kosten" value={null} signal={{ tone: "warning", label: "Kosten fehlen bei 3 Verträgen" }} />);
    expect(screen.getByText("Kosten fehlen bei 3 Verträgen").closest(".signal")).toHaveClass("signal--warning");
    expect(container.querySelector(".signal svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByText("Noch keine Daten")).not.toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("zeigt die ruhige Variante grau mit Titel und Text und bleibt barrierefrei", async () => {
    const { container } = render(<EmptyState variant="calm" title="Alles entschieden">Nichts offen.</EmptyState>);
    expect(container.querySelector(".empty-state-calm")).not.toBeNull();
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
