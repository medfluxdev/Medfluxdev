import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";
import { candidate, evidence as fieldEvidence, field, review as fieldReview } from "./fixtures/field-review";

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

const routerReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useParams: () => ({ "contract-id": CONTRACT_ID }),
  usePathname: () => `/contracts/${CONTRACT_ID}`,
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: routerReplace, refresh: vi.fn() }),
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
    // Feldprüfung: zwei wesentliche Felder, je ein Beleg des Vertrags (Vertragsbeginn mit Seite, Kosten ohne Seite).
    field_review: fieldReview([
      field({ fact_key: "dates.start_date", label: "Vertragsbeginn", current: "01.01.2024", document_value: "01.01.2024", candidates: [candidate({ key: "2024-01-01", display: "01.01.2024", value: "01.01.2024", evidence_ids: ["e-1"] })],
        evidence: [fieldEvidence({ evidence_id: "e-1", page: 2, snippet: "Laufzeit beginnt am 01.01.2024.", location: "approx", text_verified: false, source_state: "located", source_state_label: "Seite bekannt, Stelle ungefähr", document_version_id: "aaaa0000-0000-0000-0000-000000000001" })], primary_evidence_id: "e-1", source_state: "located" }),
      field({ fact_key: "costs.monthly_recurring", label: "Wiederkehrende Kosten (monatlich)", card: "cost", card_label: "Finanzen", current: "42.500 EUR", document_value: "42.500 EUR", candidates: [candidate({ key: "42500", display: "42.500 EUR", value: "42.500 EUR", evidence_ids: ["e-2"] })],
        evidence: [fieldEvidence({ evidence_id: "e-2", page: null, snippet: "Jährliche Vergütung 42.500 EUR.", location: "none", text_verified: false, source_state: "unresolved", source_state_label: "Fundstelle nicht aufgelöst", document_version_id: "aaaa0000-0000-0000-0000-000000000001" })], primary_evidence_id: "e-2", source_state: "unresolved" }),
      // Berechneter Wert (Jährliche Kosten im Kopf): kein eigener Bestätigungsauftrag.
      field({ fact_key: "costs.annual", label: "Jährliche Gesamtkosten", kind: "calculated", status: "waiting", status_label: "Berechnet – Eingaben offen", decision_needed: false, card: "cost", card_label: "Finanzen", tier: "important",
        current: "42.500 EUR", candidates: [], evidence: [], primary_evidence_id: null, source_state: null, inputs: [{ fact_key: "costs.monthly_recurring", label: "Wiederkehrende Kosten (monatlich)", present: true, decided: false }] }),
    ]),
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
    expect(await screen.findByRole("heading", { name: "Vertragsentscheidung" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Termine & Aufgaben" })).toBeInTheDocument();

    // „Im Dokument gefunden“ gibt es nicht mehr; Verknüpfungen zeigt Rahmenvertrag und Gerätearten.
    await openTab("Verknüpfungen");
    expect(screen.queryByRole("heading", { name: "Im Dokument gefunden" })).not.toBeInTheDocument();
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
    const who = within(header).getByRole("group", { name: "Zuständigkeit" });
    expect(within(who).getByText("Radiologie").closest(".tag-chip")).toHaveClass("tag-chip--cost");
    expect(within(who).getByText("Medizintechnik").closest(".tag-chip")).toHaveClass("tag-chip--department");
    expect(within(header).getByRole("button", { name: "05.05.2025" })).toHaveAttribute("title", "In den Vertragsdaten ansehen");
    expect(within(header).getByRole("button", { name: "Fristen ansehen" })).toBeInTheDocument();
  });

  it("Kopf: Zeile „Vertrag“ und Zeile „Zuständig“ – jede Angabe einmal, „Ändern“ öffnet die Organisationszuordnung", async () => {
    const user = userEvent.setup();
    const { container } = await renderWithData(detailFixture({
      business_status: "gueltig",
      partner: { id: "p-1", name: "ABIOMED Europe GmbH", short_name: "ABIOMED" },
      assignment: { contract_type: "Wartungsvertrag", contract_category: "Medizingerät", hospital: "Nordwest Krankenhaus", responsible_department: "Medizintechnik", beneficiary_departments: ["Röntgen Diagnostik", "Medizintechnik"], other_departments: [], cost_center: { code: "950000", name: "Radiologie" }, device_types: ["CT", "MRT", "Angiographie"], responsible: "Developer", further_responsible: [] },
    }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    const what = within(header).getByRole("group", { name: "Vertrag" });
    expect(within(what).getByRole("button", { name: "Kategorie: Medizingerät" })).toHaveClass("tag-chip--category");
    expect(within(what).getByRole("link", { name: "Vertragspartner: ABIOMED Europe GmbH" })).toBeInTheDocument();
    // Status steht rechts neben dem Titel, nicht in den Chip-Zeilen.
    expect(within(what).queryByText("Gültig")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 }).parentElement).toContainElement(within(header).getByText("Gültig"));
    const who = within(header).getByRole("group", { name: "Zuständigkeit" });
    expect(within(who).getByText("Developer").closest(".tag-chip")).toHaveClass("tag-chip--person");
    expect(within(who).getByText("Nordwest Krankenhaus").closest(".tag-chip")).toHaveClass("tag-chip--hospital");
    expect(within(who).getByText("Röntgen Diagnostik").closest(".tag-chip")).toHaveClass("tag-chip--secondary");
    expect(within(who).getByText("CT · MRT +1").closest(".tag-chip")).toHaveClass("tag-chip--device");
    // Keine Angabe doppelt: Abteilung nur einmal, Kostenstelle und Abteilung nicht mehr in Zeile 1.
    expect(within(header).getAllByText("Medizintechnik")).toHaveLength(1);
    expect(within(what).queryByText("Radiologie")).not.toBeInTheDocument();
    // Übersicht ohne Karte Zuständigkeit und ohne Kacheln (Finanzen, Leistungen & SLA, Daten & Nachweise).
    expect(screen.queryByRole("heading", { name: "Zuständigkeit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Daten & Nachweise" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Anzeigen/ })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    // „Bearbeiten“ steht bei den Kopfknöpfen (nicht in der Chip-Zeile) und öffnet die Vertragsdaten.
    expect(within(who).queryByRole("button", { name: /Ändern|Bearbeiten/ })).not.toBeInTheDocument();
    // Deckblatt nicht mehr als eigener Knopf, sondern als letzte Option unter „⋯“.
    expect(within(header).queryByText("Deckblatt (PDF)")).not.toBeInTheDocument();
    await user.click(within(header).getByRole("button", { name: "Weitere Aktionen" }));
    const options = within(screen.getByRole("menu", { name: "Weitere Aktionen" })).getAllByRole("menuitem").map((item) => item.textContent);
    expect(options[0]).toBe("Archivieren");
    expect(options[options.length - 1]).toBe("Deckblatt (PDF)");
    await user.keyboard("{Escape}");
    await user.click(within(header).getByRole("button", { name: "Bearbeiten" }));
    expect(screen.getByRole("tab", { name: /^Vertragsdaten/ })).toHaveAttribute("aria-selected", "true");
    // Jede Angabe führt zu ihrer Karte: Kostenstelle → Organisationszuordnung, Status → Karte „Vertragsstatus“ (Übersicht).
    routerReplace.mockClear();
    await user.click(within(who).getByRole("button", { name: /Kostenstelle: 950000/ }));
    expect(routerReplace).toHaveBeenLastCalledWith(`/contracts/${CONTRACT_ID}?tab=register&abschnitt=ownership`, { scroll: false });
    await user.click(within(header).getByRole("button", { name: /Gültig/ }));
    expect(routerReplace).toHaveBeenLastCalledWith(`/contracts/${CONTRACT_ID}?abschnitt=status`, { scroll: false });
  });

  it("KI-Plakette im Kopf führt direkt zur Prüfung der Angabe, aus der der Wert stammt", async () => {
    const fact = (fact_key: string, label_de: string, value: string) => ({ fact_key, label_de, present: true, state: "unreviewed", state_label_de: "Ungeprüft", original_value: value, effective_value: value, reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false, evidence_count: 0, linked_evidence: [], linked_evidence_refs: [], needs_evidence: false, is_critical: false });
    await renderWithData(detailFixture({
      register_facts: { contract_start: "2025-05-05", cancel_by: null, contract_end: null, annual_cost: null },
      fact_review_states: [fact("identity.contract_number", "Vertragsnummer", "CN-9876"), fact("costs.annual", "Jährliche Gesamtkosten", "42.500 EUR")],
    } as Partial<ContractDetailResponse>));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    await userEvent.click(within(header).getByRole("button", { name: /KI · Ungeprüft.*Prüfung öffnen/ }));
    // Die Karte öffnet dieselbe Entscheidungsansicht wie die geführte Prüfung – in einer Schublade, ohne den Ablauf zu starten.
    const drawer = await screen.findByRole("dialog", { name: "Jährliche Gesamtkosten" });
    // Berechnete Werte werden nicht einzeln bestätigt: die Schublade zeigt, woraus sie entstehen.
    expect(within(drawer).queryByRole("button", { name: "Bestätigen" })).not.toBeInTheDocument();
    expect(within(drawer).getByText("Wiederkehrende Kosten (monatlich)")).toBeInTheDocument();
    expect(within(drawer).getByText("Offen")).toBeInTheDocument();
  });

  it("Kopf: feste Laufzeit braucht kein „Kündbar bis“ – nichts Kritisches dazu", async () => {
    await renderWithData(detailFixture({ dates: { ...detailFixture().dates, latest_cancellation_date: null }, register_facts: { contract_start: "2025-05-05", term_model: "fixed_term", cancel_by: null, contract_end: "2029-03-31", annual_cost: null } }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).queryByText("Kündbar bis")).not.toBeInTheDocument();
    expect(within(header).queryByText("Nicht berechenbar")).not.toBeInTheDocument();
    expect(within(header).getByText("Feste Laufzeit – endet ohne Kündigung")).toBeInTheDocument();
  });

  it("Leistungen & SLA: Mietvertrag ohne Angaben ohne Reiter, „Leistungen & SLA hinzufügen“; mit KI-Angaben sichtbar", async () => {
    const user = userEvent.setup();
    const empty = { ...detailFixture().scope, maintenance: null, repair: null, remote_support: null } as ContractDetailResponse["scope"];
    const noSla = { response_time: null, resolution_time: null, service_hours: null, emergency_availability: null, availability_24_7: null, sla_notes: null };
    const rent = { type_label: "Mietvertrag", scope: false, sla: false, maintenance: false, equipment: true };
    const { unmount } = await renderWithData(detailFixture({ sections: rent, scope: empty, sla: noSla }));
    expect(screen.queryByRole("tab", { name: "Leistungen & SLA" })).not.toBeInTheDocument();
    expect(screen.queryByText("SLA unvollständig")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Leistungen & SLA hinzufügen" }));
    expect(screen.getByRole("tab", { name: "Leistungen & SLA" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Service-Level (SLA)" })).toBeInTheDocument();
    unmount();

    // Von der KI gelesene Angaben halten den Reiter sichtbar, auch wenn der Typ keinen Leistungsumfang vorsieht.
    await renderWithData(detailFixture({ sections: rent }));
    expect(screen.getByRole("tab", { name: "Leistungen & SLA" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Leistungen & SLA hinzufügen" })).not.toBeInTheDocument();
  });

  it("Kopf: nicht zugeordneter Vertragspartner führt zur Zuordnung, fehlender Beginn zum Feld", async () => {
    await renderWithData(detailFixture({ partner: null, supplier: "Siemens Healthineers", dates: { ...detailFixture().dates, start_date: null }, register_facts: { contract_start: null, cancel_by: null, contract_end: null, annual_cost: null } }));
    const header = screen.getByRole("heading", { level: 1 }).closest("header")!;
    expect(within(header).getByRole("button", { name: /Siemens Healthineers.*zuordnen/ })).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: "Vertragsbeginn erfassen" })).toBeInTheDocument();
  });

  it("zeigt die Quelldokumente und lädt den PDF-Viewer", async () => {
    await renderWithData(detailFixture());
    await openDocuments();
    // Arbeitsplatz: links Dateien (nach Art gruppiert), Stand oben rechts mit nächstem Schritt.
    const files = screen.getByRole("navigation", { name: "Quelldokumente" });
    expect(within(files).getByRole("button", { name: /wartung\.pdf/ })).toHaveAttribute("aria-current", "true");
    expect(within(files).getByRole("button", { name: /anhang\.docx/ })).toHaveTextContent("Anlage");
    expect(screen.getByLabelText("Stand der Dokumente")).toHaveTextContent(/Dateien · 2 Nachweise/);
    expect(screen.getByRole("button", { name: "Dateien" })).toHaveAttribute("aria-pressed", "true");
    // Seitenvorschau ist im Arbeitsplatz anfangs zu (die Leiste links ist schon da) und lässt sich öffnen.
    await waitFor(() => expect(screen.getByRole("button", { name: "Seiten" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Seiten" }));
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Seiten" })).toBeInTheDocument());
    expect(within(screen.getByRole("navigation", { name: "Seiten" })).getAllByRole("button", { name: /^Seite \d$/ })).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: "Seite 3" }));
    await waitFor(() => expect(document.querySelector(".page-indicator")).toHaveTextContent("Seite 3 / 3"));
  });

  it("Dateien und Nachweise teilen sich das Original; „Nachweise“ ist eine kompakte Tabelle ohne Zitate", async () => {
    await renderWithData(detailFixture());
    await openDocuments();
    expect(screen.queryByRole("button", { name: "Nachweise", pressed: true })).not.toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Dokumente und Prüfung" })).queryByRole("button", { name: "Nachweise" })).not.toBeInTheDocument();
    // Erneut erfassen hat einen festen Ort: Unterreiter „KI-Analyse“ (nicht mehr über dem Original).
    expect(within(screen.getByRole("navigation", { name: "Dokumente und Prüfung" })).getByRole("button", { name: "KI-Analyse" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Erneut aus dem Dokument erfassen" })).not.toBeInTheDocument();
    // Eine Prüfung, ein Einstieg: Felder zählen, nicht Nachweise.
    expect(screen.getByRole("button", { name: "Wesentliches prüfen · 2" })).toBeInTheDocument();
    expect(screen.getByText("0 von 2 wesentlichen Angaben entschieden")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nachweise prüfen/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Nachweise" }));
    // Klick auf „Nachweise“: Liste und gleich der Filter (Prüfstand, Abschnitt, Suche) im Aufklapper.
    const trigger = screen.getByRole("button", { name: "Nachweise filtern" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("group", { name: "Nach Prüfstand filtern" })).toBeInTheDocument();
    const panel = document.querySelector(".evf");
    expect(screen.getByText("Nachweise filtern", { selector: ".evf-title" })).toBeInTheDocument();
    expect(screen.getByText("Zeigt alle 2 Nachweise.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Offen/ }));
    // Erst „Filter anwenden“ übernimmt die Auswahl.
    expect(screen.queryByText(/^Nur Offen · 2$/)).not.toBeInTheDocument();
    expect(await axe(panel as HTMLElement)).toHaveNoViolations();
    await userEvent.click(screen.getByRole("button", { name: "Filter anwenden" }));
    expect(screen.getByText(/^Nur Offen · 2$/)).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAccessibleName("Nachweise filtern (2 von 2)");
    await userEvent.click(screen.getByRole("button", { name: "Filter aufheben" }));
    expect(screen.getByRole("button", { name: "Nachweise filtern" })).toBeInTheDocument();
    expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Nachweise dieses Vertrags" });
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["#", "Feld", "Seite", "Status"]);
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getAllByText("Offen")).toHaveLength(2);
    expect(within(table).queryByText(/Laufzeit beginnt am/)).not.toBeInTheDocument();
    expect(screen.getByText("2 Nachweise", { exact: false })).toBeInTheDocument();
  });

  it("der Filter der Nachweise-Liste ist nur eine Ansicht – die Prüfung bleibt ein einziger Ablauf", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    const list = screen.getByRole("group", { name: "Nach Prüfstand filtern" });
    await userEvent.type(screen.getByRole("searchbox", { name: "Nachweise durchsuchen" }), "start date");
    expect(within(list).getByRole("button", { name: /^Alle/ })).toHaveTextContent("1");
    expect(screen.getByText("1 Treffer")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Filter anwenden" }));
    expect(within(screen.getByRole("table", { name: "Nachweise dieses Vertrags" })).getAllByRole("row")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /Auswahl prüfen/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Wesentliches prüfen · 2" })).toBeInTheDocument();
  });

  it("ein Nachweis aus der Tabelle öffnet die geführte Prüfung an seiner Stelle im Original", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    await userEvent.click(within(screen.getByRole("table", { name: "Nachweise dieses Vertrags" })).getByRole("button", { name: /start date/i }));
    const panel = await screen.findByRole("region", { name: "Aktuelle Angabe" });
    expect(within(panel).getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Wesentliche Angaben prüfen" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("von 3", { exact: false })).toHaveTextContent("Seite 2 von 3"));
    // Aktueller Nachweis: Rahmen mit derselben Nummer wie in der Tabelle.
    await waitFor(() => expect(document.querySelector(".pdf-frame.is-current")).toHaveTextContent("1"));
  });

  it("Nachweis ohne Seitenangabe erfindet keinen Rahmen; zurück zum Vertrag beendet die Prüfung", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    await userEvent.click(within(screen.getByRole("table", { name: "Nachweise dieses Vertrags" })).getByRole("button", { name: /annual cost/i }));
    const panel = await screen.findByRole("region", { name: "Aktuelle Angabe" });
    expect(within(panel).getByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
    // Ungeklärte Fundstelle wird nicht als belegt ausgegeben.
    expect(within(panel).getByText("Fundstelle nicht aufgelöst", { selector: ".signal-label" })).toBeInTheDocument();
    expect(document.querySelector(".pdf-frame.is-current")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Zurück zum Vertrag" }));
    expect(screen.queryByRole("region", { name: "Aktuelle Angabe" })).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Nachweise dieses Vertrags" })).toBeInTheDocument();
  });

  it("hat im Dokument-Workspace keine automatisierten WCAG-A11y-Verstöße", async () => {
    const { container } = await renderWithData(detailFixture());
    await openDocuments();
    await waitFor(() => expect(screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })).toBeInTheDocument());
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("behält beim Wechsel zwischen Prüfung und Vertrags-Tabs den Workspace-Kontext", async () => {
    await renderWithData(detailFixture());
    await openDocuments("Nachweise");
    await userEvent.click(within(screen.getByRole("table", { name: "Nachweise dieses Vertrags" })).getByRole("button", { name: /start date/i }));
    await screen.findByRole("region", { name: "Aktuelle Angabe" });
    await openTab("Übersicht");
    expect(screen.getByRole("heading", { name: "MRT Wartungsvertrag" })).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfrist nähert sich")).toBeInTheDocument();
  });
});
