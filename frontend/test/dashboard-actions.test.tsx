import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import KpiCard from "@/components/dashboard/KpiCard";
import DeadlineDistribution from "@/components/dashboard/DeadlineDistribution";
import FinancialOverview from "@/components/dashboard/FinancialOverview";

describe("Dashboard – handlungsorientierte Indikatoren", () => {
  it("verlinkt unterstützte KPI-Karten auf gefilterte Vertragslisten", () => {
    render(
      <KpiCard
        card={{ label_de: "Kritische Kündigungsfristen", value: 3, secondary_de: null, status_de: null }}
        href="/contracts?critical_cancellation=true"
      />
    );
    expect(screen.getByRole("link", { name: /Kritische Kündigungsfristen/i })).toHaveAttribute(
      "href",
      "/contracts?critical_cancellation=true"
    );
    expect(screen.getByText("Verträge anzeigen")).toBeInTheDocument();
  });

  it("trennt Kündigungsfristen von Vertragsenden", () => {
    render(
      <DeadlineDistribution
        buckets={[
          { threshold_days: 30, label_de: "30 Tage", contract_count: 5, cancellation: 3, contract_end: 2 },
        ]}
      />
    );
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfristen")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Vertragsenden")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /3 Kündigungsfristen/i })).toHaveAttribute(
      "href",
      "/contracts?critical_cancellation=true"
    );
  });

  it("zeigt fehlende Kostenabdeckung explizit und nie als Nullbetrag", () => {
    render(
      <FinancialOverview
        financial={{
          annual_recurring: [],
          total_contract_value: [],
          contracts_without_reliable_annual_cost: 4,
          contracts_without_reliable_total_value: 2,
          multi_currency: false,
        }}
      />
    );
    expect(screen.getByText("Keine verlässlichen Kosten verfügbar.")).toBeInTheDocument();
    expect(screen.getByText(/Unbekannte oder widersprüchliche Kosten werden nicht als 0 € dargestellt/)).toBeInTheDocument();
    expect(screen.getByText(/4 ohne verlässliche Jahreskosten/)).toBeInTheDocument();
    expect(screen.getByText(/2 ohne verlässlichen Gesamtwert/)).toBeInTheDocument();
  });
});
