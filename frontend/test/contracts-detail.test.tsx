import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  scopedApiUrl: (path: string) => `http://test.local${path}`,
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  contentUrl: (contractId: string, versionId: string) =>
    `http://test.local/content/${contractId}/${versionId}`,
  sourceRegionUrl: () => "http://test.local/source-region",
}));

vi.mock("pdfjs-dist", () => {
  const pageStub = {
    getViewport: ({ scale }: { scale: number }) => ({ width: 400 * scale, height: 500 * scale }),
    render: () => ({ promise: Promise.resolve(), cancel: () => {} }),
  };
  const docStub = { numPages: 3, getPage: async () => pageStub, destroy: async () => {} };
  return {
    GlobalWorkerOptions: { workerSrc: "" },
    getDocument: () => ({ promise: Promise.resolve(docStub) }),
  };
});

const CONTRACT_ID = "11111111-1111-1111-1111-111111111111";

vi.mock("next/navigation", () => ({
  useParams: () => ({ "contract-id": CONTRACT_ID }),
  usePathname: () => `/contracts/${CONTRACT_ID}`,
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

function detailFixture(overrides: Partial<ContractDetailResponse> = {}): ContractDetailResponse {
  return {
    organization_slug: "krankenhaus",
    contract_id: CONTRACT_ID,
    is_archived: false,
    archived_at: null,
    contract_number: "CN-9876",
    contract_title: "MRT Wartungsvertrag",
    supplier: "Siemens Healthineers",
    status: "active",
    risk_level: "medium",
    identity: { contract_number: "CN-9876", contract_type: "Wartung", department: "Radiologie" },
    dates: {
      start_date: "2024-01-01",
      start_date_status: "explicit",
      calculated_end_date: "2027-06-30",
      calculated_end_status: "explicit",
      latest_cancellation_date: "2027-03-01",
      latest_cancellation_status: "computed",
      next_renewal_date: "2027-06-30",
      next_renewal_status: "computed",
      automatic_renewal: true,
      current_status: "active",
      current_status_explanation: "Vertrag ist aktiv.",
      review_required: false,
    } as ContractDetailResponse["dates"],
    costs: {
      annual_recurring: { amount: "42500", currency: "EUR", status: "explicit", explanation: null },
      monthly_recurring: { amount: null, currency: "EUR", status: null, explanation: null },
      total_contract_value_status: null,
      currency_conflict: false,
      tax_basis: null,
    } as ContractDetailResponse["costs"],
    scope: {
      included_services: ["Wartung", "Remote-Support"],
      excluded_services: ["Ersatzteile"],
      maintenance: true,
      inspection: null,
      repair: false,
      calibration: null,
      software_updates: null,
      remote_support: true,
      technical_support: null,
      spare_parts_included: null,
      consumables_included: null,
      emergency_service: null,
    } as ContractDetailResponse["scope"],
    sla: {
      response_time: "4 Stunden",
      resolution_time: null,
      service_hours: null,
      emergency_availability: null,
      availability_24_7: true,
      sla_notes: null,
    },
    equipment: [{
      id: "eq-1",
      equipment_id: "EQ-1",
      device_name: "MRT Magnetom",
      manufacturer: "Siemens",
      model: "Vida",
      serial_number: "SN-1",
      inventory_number: null,
      system_name: null,
      equipment_category: null,
      equipment_type: null,
      location: null,
      department: "Radiologie",
      service_scope: null,
      coverage_start: null,
      coverage_end: null,
      included_services: [],
      excluded_services: [],
      sla_notes: null,
      identification_quality: null,
      relationship_quality: null,
      requires_review: false,
      review_reasons: [],
      field_ref: null,
      page: null,
      source_type: null,
    }],
    review: { requires_manual_review: false, review_reasons: [], data_freshness: "current", warning_evaluation_as_of_date: "2026-08-31" },
    warnings: [{
      warning_type: "cancellation_deadline_approaching",
      severity: "medium",
      title_de: "Kündigungsfrist nähert sich",
      target_kind: "date",
      target_date: "2027-03-01",
      days_remaining: 182,
      requires_action: true,
      requires_review: false,
      action_state: null,
    }],
    work_items: [],
    documents: [
      { document_version_id: "aaaa0000-0000-0000-0000-000000000001", role: "main", original_filename: "wartung.pdf", mime_type: "application/pdf", file_size_bytes: 4582, viewer_supported: true },
      { document_version_id: "aaaa0000-0000-0000-0000-000000000002", role: "annex", original_filename: "anhang.docx", mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", file_size_bytes: 1200, viewer_supported: false },
    ],
    evidence: [
      {
        evidence_id: "e-1",
        field_ref: "dates.start_date",
        document_version_id: "aaaa0000-0000-0000-0000-000000000001",
        original_filename: "wartung.pdf",
        page: 2,
        source_type: "paragraph",
        paragraph_index: 3,
        table_index: null,
        snippet: "Laufzeit beginnt am 01.01.2024.",
        confidence: 0.98,
        requires_review: false,
        bbox: { x0: 40, y0: 200, x1: 200, y1: 260 },
        precision: "coarse",
        geometry_normalized: false,
        bbox_space: "pdf_points",
        supports_exact_navigation: true,
      },
      {
        evidence_id: "e-2",
        field_ref: "costs.annual_cost",
        document_version_id: "aaaa0000-0000-0000-0000-000000000001",
        original_filename: "wartung.pdf",
        page: null,
        source_type: "table",
        paragraph_index: null,
        table_index: 1,
        snippet: "Jährliche Vergütung 42.500 EUR.",
        confidence: 0.9,
        requires_review: true,
        bbox: null,
        precision: "none",
        geometry_normalized: false,
        bbox_space: "pdf_points",
        supports_exact_navigation: false,
      },
    ],
    overrides: [],
    audit_log: [],
    import_state: { import_state: "analysis_ok", state_label_de: "Analyse abgeschlossen", document_version_id: "aaaa0000-0000-0000-0000-000000000001", can_retry: false, message: null, analysis_status: "ok", requires_review: false },
    fact_review_states: [],
    fact_reviews: [],
    contract_review: { status: "unreviewed", status_label_de: "Nicht geprüft", reviewer_display_name: null, reviewer_identity_type: "manual_unverified", authenticated_actor_id: null, reviewed_at: null, changed_noted_at: null, completion_note: null, relevant_count: 0, reviewed_count: 0, unresolved_count: 0, critical_count: 0, critical_reviewed_count: 0, critical_unreviewed_count: 0 },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    arrayBuffer: async () => new ArrayBuffer(8),
    json: async () => ({}),
  });
});

async function renderWithData(data: ContractDetailResponse) {
  apiGetMock.mockResolvedValue(data);
  const utils = render(<ContractDetailPage />);
  await screen.findByRole("heading", { name: "MRT Wartungsvertrag" });
  return utils;
}

async function openTab(name: string) {
  await userEvent.click(screen.getByRole("tab", { name }));
}

async function openDocuments(subtab?: "Dokument" | "Nachweise" | "Prüfung" | "Historie") {
  await openTab("Dokumente");
  if (subtab && subtab !== "Dokument") {
    await userEvent.click(screen.getByRole("button", { name: subtab }));
  }
}

describe("Vertrags-Detail + Quellenanzeige (tabbed Contract Workspace)", () => {
  it("lädt die akzeptierte Wahrheit und zeigt fachliche Daten in den passenden Tabs", async () => {
    await renderWithData(detailFixture());
    expect(screen.getAllByText(/CN-9876/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Siemens/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("42.500,00 €").length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("Kündigungsfrist nähert sich")).toBeInTheDocument();

    await openTab("Fristen & Aufgaben");
    expect(screen.getAllByText(/01\.01\.2024/).length).toBeGreaterThanOrEqual(1);

    await openTab("Verknüpfungen");
    expect(screen.getAllByText("MRT Magnetom").length).toBeGreaterThanOrEqual(1);
  });

  it("Kopf: Vertragsbeginn, farbiger Status und Vertragspartner zum Öffnen", async () => {
    await renderWithData(detailFixture({
      business_status: "gueltig",
      partner: { id: "p-1", name: "ABIOMED Europe GmbH", short_name: "ABIOMED" },
      register_facts: { contract_start: "2025-04-01", cancel_by: null, contract_end: null, annual_cost: null },
    }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).getByText("Vertragsbeginn")).toBeInTheDocument();
    expect(within(header.querySelector("dl")!).getByText("01.04.2025")).toBeInTheDocument();
    expect(within(header).getByText("Gültig").closest(".status-badge")).toHaveClass("status-badge--success");
    expect(within(header).getByRole("link", { name: "Vertragspartner: ABIOMED Europe GmbH" })).toHaveAttribute("href", "/stammdaten/vertragspartner?id=p-1");
  });

  it("Kopf: Hauptangaben mit Kennfarbe führen zur Organisationszuordnung, Werte zu ihrer Quelle", async () => {
    await renderWithData(detailFixture({
      assignment: { contract_type: "Wartungsvertrag", contract_category: null, hospital: "Nordwest", responsible_department: "Medizintechnik", beneficiary_departments: [], other_departments: [], cost_center: { code: "950000", name: "Radiologie" }, responsible: null, further_responsible: [] },
      register_facts: { contract_start: "2025-05-05", cancel_by: null, contract_end: null, annual_cost: null },
    }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).getByRole("button", { name: "Vertragstyp: Wartungsvertrag" })).toHaveClass("tag-chip--type");
    expect(within(header).getByRole("button", { name: /Kostenstelle 950000/ })).toHaveClass("tag-chip--cost");
    expect(within(header).getByRole("button", { name: "Verantwortliche Abteilung: Medizintechnik" })).toHaveClass("tag-chip--department");
    expect(within(header).getByRole("button", { name: "05.05.2025" })).toHaveAttribute("title", "In den Vertragsdaten ansehen");
    expect(within(header).getByRole("button", { name: "Fristen ansehen" })).toBeInTheDocument();
  });

  it("Kopf: feste Laufzeit braucht kein „Kündbar bis“ – nichts Kritisches dazu", async () => {
    await renderWithData(detailFixture({ dates: { ...detailFixture().dates, latest_cancellation_date: null }, register_facts: { contract_start: "2025-05-05", term_model: "fixed_term", cancel_by: null, contract_end: "2029-03-31", annual_cost: null } }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).queryByText("Kündbar bis")).not.toBeInTheDocument();
    expect(within(header).queryByText("Nicht berechenbar")).not.toBeInTheDocument();
    expect(within(header).getByText("Feste Laufzeit – endet ohne Kündigung")).toBeInTheDocument();
  });

  it("Abschnitte je Vertragstyp: Mietvertrag blendet leeren Leistungsumfang/SLA aus, Daten bleiben sichtbar", async () => {
    const user = userEvent.setup();
    const empty = { ...detailFixture().scope, maintenance: null, repair: null, remote_support: null } as ContractDetailResponse["scope"];
    const noSla = { response_time: null, resolution_time: null, service_hours: null, emergency_availability: null, availability_24_7: null, sla_notes: null };
    const rent = { type_label: "Mietvertrag", scope: false, sla: false, maintenance: false, equipment: true };
    const { unmount } = await renderWithData(detailFixture({ sections: rent, scope: empty, sla: noSla }));
    expect(screen.queryByRole("heading", { name: "Leistungsumfang" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "SLA" })).not.toBeInTheDocument();
    expect(screen.queryByText("SLA unvollständig")).not.toBeInTheDocument();
    expect(screen.getByText(/Für Mietvertrag ausgeblendet: Leistungsumfang, SLA/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Trotzdem anzeigen" }));
    expect(screen.getByRole("heading", { name: "SLA" })).toBeInTheDocument();
    unmount();

    // Mit gefundenen Angaben bleibt der Abschnitt sichtbar, auch wenn der Typ ihn nicht vorsieht.
    await renderWithData(detailFixture({ sections: rent }));
    expect(screen.getByRole("heading", { name: "Leistungsumfang" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "SLA" })).toBeInTheDocument();
    expect(screen.queryByText(/ausgeblendet/)).not.toBeInTheDocument();
  });

  it("Kopf: nicht zugeordneter Vertragspartner führt zur Zuordnung, fehlender Beginn zum Feld", async () => {
    await renderWithData(detailFixture({ partner: null, supplier: "Siemens Healthineers", dates: { ...detailFixture().dates, start_date: null }, register_facts: { contract_start: null, cancel_by: null, contract_end: null, annual_cost: null } }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).getByRole("button", { name: /Siemens Healthineers.*zuordnen/ })).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Vertragsbeginn erfassen" })).toBeInTheDocument();
  });

  it("zeigt den belegten Systemnamen, wenn device_name fehlt", async () => {
    const equipment = detailFixture().equipment;
    await renderWithData(detailFixture({
      equipment: [{ ...equipment[0], device_name: null, system_name: "Impella AIC System", model: null }],
    }));
    await openTab("Verknüpfungen");
    expect(screen.getByText("Impella AIC System")).toBeInTheDocument();
  });

  it("zeigt den belegten Modellnamen, wenn Geräte- und Systemname fehlen", async () => {
    const equipment = detailFixture().equipment;
    await renderWithData(detailFixture({
      equipment: [{ ...equipment[0], device_name: null, system_name: null, model: "Accutron MR" }],
    }));
    await openTab("Verknüpfungen");
    expect(screen.getAllByText("Accutron MR").length).toBeGreaterThanOrEqual(1);
  });

  it("zeigt die Quelldokumente und lädt den PDF-Viewer", async () => {
    await renderWithData(detailFixture());
    await openDocuments();
    expect(screen.getByRole("button", { name: /wartung\.pdf/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /anhang\.docx/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument());
  });

  it("zeigt Nachweise mit ehrlicher Navigations-Präzision", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    expect(screen.getByText("Positionsbestimmt")).toBeInTheDocument();
    expect(screen.getByText("Ohne Positionsangabe")).toBeInTheDocument();
    expect(screen.getAllByText(/KI-Konfidenz 98 %/).length).toBeGreaterThan(0);
  });

  it("markiert eine ausgewählte Quelle und öffnet das Original im PDF-Viewer", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    const sourceBtn = screen.getByRole("button", { name: /start date/i });
    await userEvent.click(sourceBtn);
    expect(sourceBtn).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/Seite 2 \/ 3/)).toBeInTheDocument());
  });

  it("Quelle ohne Seitenangabe erfindet keine Hervorhebung", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    const sourceBtn = screen.getByRole("button", { name: /annual cost/i });
    await userEvent.click(sourceBtn);
    expect(screen.getByText(/Keine Seitenangabe/)).toBeInTheDocument();
    expect(screen.queryByText(/hervorgehoben/)).not.toBeInTheDocument();
  });

  it("hat im Dokument-Workspace keine automatisierten WCAG-A11y-Verstöße", async () => {
    const { container } = await renderWithData(detailFixture());
    await openDocuments();
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument());
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("behält beim Wechsel zwischen Quelle und Vertrags-Tabs den Workspace-Kontext", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    await userEvent.click(screen.getByRole("button", { name: /start date/i }));
    await waitFor(() => expect(screen.getByText(/Seite 2 \/ 3/)).toBeInTheDocument());
    await openTab("Übersicht");
    expect(screen.getByRole("heading", { name: "MRT Wartungsvertrag" })).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfrist nähert sich")).toBeInTheDocument();
  });
});