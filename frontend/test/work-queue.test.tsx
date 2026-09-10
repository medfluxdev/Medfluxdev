import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkQueuePage from "@/app/work-queue/page";
import type { WorkItemList, WorkItemSummary } from "@/lib/pr4-types";

const apiGetMock = vi.fn();
const apiPatchMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPatch: (...args: unknown[]) => apiPatchMock(...args),
}));

function item(overrides: Partial<WorkItemSummary> = {}): WorkItemSummary {
  return {
    id: "wi-1",
    contract_id: "c-1",
    contract_number: "CN-1",
    supplier: "Lieferant",
    equipment_id: null,
    contract_equipment_id: null,
    source_warning_id: null,
    item_type: "cancellation_deadline",
    severity: "high",
    status: "open",
    title_de: "Kündigungsfrist nähert sich",
    why_de: "Vertrag kann noch bis 2026-06-01 gekündigt werden.",
    action_hint_de: "Kündigung prüfen.",
    target_date: "2026-06-01",
    days_remaining: 14,
    requires_review: false,
    active: true,
    references: null,
    first_seen_at: null,
    last_seen_at: null,
    equipment_device_name: null,
    equipment_manufacturer: null,
    equipment_model: null,
    equipment_serial_number: null,
    ...overrides,
  };
}

function list(...items: WorkItemSummary[]): WorkItemList {
  return { items, total: items.length };
}

beforeEach(() => {
  vi.clearAllMocks();
});

async function renderWithData(data: WorkItemList) {
  apiGetMock.mockResolvedValue(data);
  const utils = render(<WorkQueuePage />);
  await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
  return utils;
}

describe("Arbeitsliste (PR-4)", () => {
  it("zeigt einen Ladezustand während des Ladens", () => {
    apiGetMock.mockImplementation(() => new Promise(() => {}));
    render(<WorkQueuePage />);
    expect(screen.getByText("Arbeitspunkte werden geladen…")).toBeInTheDocument();
  });

  it("zeigt einen generischen Fehlerzustand bei Backend-Fehler", async () => {
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<WorkQueuePage />);
    await waitFor(() =>
      expect(
        screen.getByText("Arbeitsliste konnte nicht geladen werden.")
      ).toBeInTheDocument()
    );
  });

  it("zeigt 'keine offenen Punkte' bei leerer Liste", async () => {
    const empty = list();
    await renderWithData(empty);
    expect(
      screen.getByText("Derzeit keine offenen Arbeitspunkte.")
    ).toBeInTheDocument();
  });

  it("zeigt die Arbeitsposition, ohne eine Geräte-Zeile zu erfinden", async () => {
    await renderWithData(list(item()));
    expect(screen.queryByText(/Gerät/)).not.toBeInTheDocument();
  });

  it("zeigt die Geräte-Identität des betroffenen Equipments (UAT Wartung)", async () => {
    await renderWithData(
      list(
        item({
          equipment_device_name: "Accutron MR",
          equipment_manufacturer: "MEDTRON",
          equipment_model: "X-9000",
          equipment_serial_number: "88024307",
        })
      )
    );
    expect(
      screen.getByText(/Accutron MR · MEDTRON \(X-9000\) · Seriennr\. 88024307/)
    ).toBeInTheDocument();
  });

  it("zeigt offene Punkte mit Vertrags-Link und Status", async () => {
    await renderWithData(list(item()));
    expect(screen.getByText(/Kündigungsfrist: Kündigungsfrist nähert sich/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CN-1" })).toHaveAttribute(
      "href",
      "/contracts/c-1"
    );
    expect(screen.getByText("Offen")).toBeInTheDocument();
    expect(screen.getByText(/in 14 Tagen/)).toBeInTheDocument();
  });

  it("übernimmt einen offenen Punkt (acknowledged) per PATCH", async () => {
    const wi = item();
    apiPatchMock.mockResolvedValue({ ...wi, status: "acknowledged" });
    await renderWithData(list(wi));
    await userEvent.click(screen.getByRole("button", { name: "In Bearbeitung" }));
    await waitFor(() =>
      expect(apiPatchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/work-queue/wi-1"),
        { status: "acknowledged" }
      )
    );
    expect(screen.getByText("In Bearbeitung")).toBeInTheDocument();
  });

  it("erledigt einen Punkt (resolved) per PATCH und entfernt ihn aus der aktiven Liste", async () => {
    apiPatchMock.mockResolvedValue({ ...item(), status: "resolved", active: false });
    await renderWithData(list(item()));
    await userEvent.click(screen.getByRole("button", { name: "Erledigt" }));
    await waitFor(() =>
      expect(apiPatchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/work-queue/wi-1"),
        { status: "resolved" }
      )
    );
    await waitFor(() =>
      expect(
        screen.getByText("Derzeit keine offenen Arbeitspunkte.")
      ).toBeInTheDocument()
    );
  });

  it("meldet einen Fehler, wenn die Status-Aktualisierung fehlschlägt", async () => {
    apiPatchMock.mockRejectedValue(new Error("Datenbankkonflikt beim Aktualisieren – bitte erneut versuchen."));
    await renderWithData(list(item()));
    await userEvent.click(screen.getByRole("button", { name: "Erledigt" }));
    await waitFor(() =>
      expect(
        screen.getByText("Datenbankkonflikt beim Aktualisieren – bitte erneut versuchen.")
      ).toBeInTheDocument()
    );
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im normalen Zustand", async () => {
    const { container } = await renderWithData(list(item()));
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
