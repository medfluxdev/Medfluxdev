import { render, screen, waitFor, within } from "@testing-library/react";
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

function taskRow(contractNumber = "CN-1") {
  return screen.getByRole("link", { name: contractNumber }).closest("tr") as HTMLTableRowElement;
}

describe("To-dos (PR-4 / FE-09)", () => {
  it("zeigt einen Ladezustand während des Ladens", () => {
    apiGetMock.mockImplementation(() => new Promise(() => {}));
    render(<WorkQueuePage />);
    expect(screen.getByText("To-dos werden geladen…")).toBeInTheDocument();
  });

  it("zeigt einen generischen Fehlerzustand bei Backend-Fehler", async () => {
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<WorkQueuePage />);
    await waitFor(() => expect(screen.getByText("To-dos konnten nicht geladen werden.")).toBeInTheDocument());
  });

  it("zeigt 'keine offenen To-dos' bei leerer Liste", async () => {
    await renderWithData(list());
    expect(screen.getByText("Keine offenen To-dos")).toBeInTheDocument();
    expect(screen.getByText("Aktuell sind keine offenen Aufgaben vorhanden.")).toBeInTheDocument();
  });

  it("zeigt die Arbeitsposition, ohne eine Geräte-Zeile zu erfinden", async () => {
    await renderWithData(list(item()));
    expect(within(taskRow()).queryByText(/Gerät/)).not.toBeInTheDocument();
  });

  it("zeigt die Geräte-Identität des betroffenen Equipments", async () => {
    await renderWithData(list(item({ equipment_device_name: "Accutron MR", equipment_manufacturer: "MEDTRON", equipment_model: "X-9000", equipment_serial_number: "88024307" })));
    expect(screen.getByText(/Accutron MR · MEDTRON \(X-9000\) · Seriennr\. 88024307/)).toBeInTheDocument();
  });

  it("zeigt Vertrags-Link, Status, Terminart und nächsten Schritt", async () => {
    await renderWithData(list(item()));
    const row = taskRow();
    expect(within(row).getByText(/Kündigungsfrist: Kündigungsfrist nähert sich/)).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "CN-1" })).toHaveAttribute("href", "/contracts/c-1");
    expect(within(row).getByText("Offen")).toBeInTheDocument();
    expect(within(row).getByText(/in 14 Tagen/)).toBeInTheDocument();
    expect(within(row).getByText("Kündigungsfrist", { selector: ".work-deadline-kind" })).toBeInTheDocument();
    expect(within(row).getByText(/Nächster Schritt:/)).toBeInTheDocument();
    expect(within(row).getByText(/Kündigung prüfen/)).toBeInTheDocument();
  });

  it("öffnet bei Prüfbedarf direkt die Vertragsprüfung", async () => {
    await renderWithData(list(item({ requires_review: true, item_type: "manual_review" })));
    expect(screen.getByRole("link", { name: "Prüfung öffnen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=review");
  });

  it("sendet unterstützte Filter an die Work-Queue-API", async () => {
    apiGetMock.mockResolvedValue(list(item()));
    render(<WorkQueuePage />);
    await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
    await userEvent.selectOptions(screen.getByLabelText("Priorität filtern"), "high");
    await waitFor(() => expect(apiGetMock).toHaveBeenLastCalledWith(expect.stringContaining("severity=high")));
    await userEvent.selectOptions(screen.getByLabelText("Aufgabentyp filtern"), "cancellation_deadline");
    await waitFor(() => expect(apiGetMock).toHaveBeenLastCalledWith(expect.stringContaining("item_type=cancellation_deadline")));
  });

  it("unterscheidet Kündigungsfrist und Vertragsende textuell", async () => {
    await renderWithData(list(item(), item({ id: "wi-2", item_type: "contract_expiry", title_de: "Vertragsende nähert sich" })));
    expect(screen.getAllByText("Kündigungsfrist").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Vertragsende").length).toBeGreaterThan(0);
  });

  it("übernimmt einen offenen Punkt (acknowledged) per PATCH", async () => {
    const wi = item();
    apiPatchMock.mockResolvedValue({ ...wi, status: "acknowledged" });
    await renderWithData(list(wi));
    await userEvent.click(within(taskRow()).getByRole("button", { name: "In Bearbeitung" }));
    await waitFor(() => expect(apiPatchMock).toHaveBeenCalledWith(expect.stringContaining("/api/work-queue/wi-1"), { status: "acknowledged" }));
    expect(within(taskRow()).getByText("In Bearbeitung")).toBeInTheDocument();
  });

  it("erledigt einen Punkt (resolved) per PATCH und entfernt ihn aus der aktiven Liste", async () => {
    apiPatchMock.mockResolvedValue({ ...item(), status: "resolved", active: false });
    await renderWithData(list(item()));
    await userEvent.click(within(taskRow()).getByRole("button", { name: "Erledigt" }));
    await waitFor(() => expect(apiPatchMock).toHaveBeenCalledWith(expect.stringContaining("/api/work-queue/wi-1"), { status: "resolved" }));
    await waitFor(() => expect(screen.getByText("Keine offenen To-dos")).toBeInTheDocument());
  });

  it("meldet einen Fehler, wenn die Status-Aktualisierung fehlschlägt", async () => {
    apiPatchMock.mockRejectedValue(new Error("Datenbankkonflikt beim Aktualisieren – bitte erneut versuchen."));
    await renderWithData(list(item()));
    await userEvent.click(within(taskRow()).getByRole("button", { name: "Erledigt" }));
    await waitFor(() => expect(screen.getByText("Datenbankkonflikt beim Aktualisieren – bitte erneut versuchen.")).toBeInTheDocument());
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im normalen Zustand", async () => {
    const { container } = await renderWithData(list(item()));
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
