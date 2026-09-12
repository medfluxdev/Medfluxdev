import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EquipmentPage from "@/app/equipment/page";
import EquipmentDetailPage from "@/app/equipment/[equipment-id]/page";
import type { EquipmentDetail, EquipmentSummary } from "@/lib/pr4-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ "equipment-id": "eq-1" }),
}));

function summary(overrides: Partial<EquipmentSummary> = {}): EquipmentSummary {
  return {
    id: "eq-1",
    device_name: "Computertomograph",
    manufacturer: "Siemens Healthineers",
    model: "SOMATOM X",
    serial_number: "SN-123",
    inventory_number: null,
    equipment_type: "CT",
    equipment_category: "Bildgebung",
    location: null,
    department: "Radiologie",
    identification_quality: "exact",
    contract_count: 2,
    ...overrides,
  };
}

function detail(overrides: Partial<EquipmentDetail> = {}): EquipmentDetail {
  return {
    ...summary(),
    contracts: [
      {
        contract_id: "c-1",
        supplier: "Siemens Healthineers",
        contract_number: "CN-1",
        relationship_quality: "exact",
        requires_review: false,
        service_scope: "Wartung inkl. Ersatzteile",
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Geräte-Liste (PR-4)", () => {
  it("zeigt einen Ladezustand", () => {
    apiGetMock.mockImplementation(() => new Promise(() => {}));
    render(<EquipmentPage />);
    expect(screen.getByText("Geräte werden geladen…")).toBeInTheDocument();
  });

  it("zeigt einen Fehlerzustand", async () => {
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<EquipmentPage />);
    await waitFor(() =>
      expect(screen.getByText("Geräte konnten nicht geladen werden.")).toBeInTheDocument()
    );
  });

  it("zeigt Geräte mit Identität, Vertragszahl und Detail-Link", async () => {
    apiGetMock.mockResolvedValue([summary()]);
    render(<EquipmentPage />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Computertomograph" })).toBeInTheDocument()
    );
    expect(screen.getByText("Eindeutig (Seriennr./Inventarnr.)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Computertomograph" })).toHaveAttribute(
      "href",
      "/equipment/eq-1"
    );
  });

  it("zeigt 'keine Geräte' bei leerer Liste", async () => {
    apiGetMock.mockResolvedValue([]);
    render(<EquipmentPage />);
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Geräte vorhanden/)).toBeInTheDocument()
    );
  });

  it("hat keine A11y-Verstöße im normalen Zustand", async () => {
    apiGetMock.mockResolvedValue([summary()]);
    const { container } = render(<EquipmentPage />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Computertomograph" })).toBeInTheDocument()
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe("Geräte-Detail (PR-4)", () => {
  it("zeigt die volle Geräte-Ansicht mit verbundenen Verträgen", async () => {
    apiGetMock.mockResolvedValue(detail());
    render(<EquipmentDetailPage />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Computertomograph" })).toBeInTheDocument());
    expect(screen.getByText("SN-123")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /CN-1/ })).toHaveAttribute(
      "href",
      "/contracts/c-1"
    );
    expect(screen.getByText("Belegt exakt")).toBeInTheDocument();
  });

  it("zeigt Review-Status für prüfpflichtige Zuordnungen", async () => {
    const d = detail({
      contracts: [
        {
          contract_id: "c-2",
          supplier: "Lieferant",
          contract_number: "CN-2",
          relationship_quality: "partial",
          requires_review: true,
          service_scope: null,
        },
      ],
    });
    apiGetMock.mockResolvedValue(d);
    render(<EquipmentDetailPage />);
    await waitFor(() => expect(screen.getByText("Zu prüfen")).toBeInTheDocument());
    expect(screen.getByText("Teilweise belegt")).toBeInTheDocument();
  });

  it("hat keine A11y-Verstöße im normalen Zustand", async () => {
    apiGetMock.mockResolvedValue(detail());
    const { container } = render(<EquipmentDetailPage />);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Computertomograph" })).toBeInTheDocument()
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
