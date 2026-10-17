import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScopeCard, ScopeListCard, SlaCard, type ScopeList, type ScopeRow, type SlaRow } from "@/components/contracts/detail/FactCards";
import type { FactReviewStateDto } from "@/lib/contract-detail-types";

const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error { status = 0; },
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

const PATH = "/api/contracts/c1/fact-reviews?organization_slug=klinik";

function fact(key: string, state: string, value: unknown): FactReviewStateDto {
  return { fact_key: key, label_de: key, present: value != null, state, state_label_de: state, original_value: value, effective_value: value, reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false, evidence_count: 1, linked_evidence: [], linked_evidence_refs: [], needs_evidence: false, is_critical: false };
}

const slaRows: SlaRow[] = [
  { key: "response_time", label: "Reaktionszeit", value: "4 Stunden", suggestion: "4 Stunden", empty: "Nicht im Vertrag gefunden", fact: fact("sla.response_time", "unreviewed", "4 Stunden") },
  { key: "resolution_time", label: "Lösungszeit", value: null, suggestion: null, empty: "Nicht im Vertrag gefunden", fact: fact("sla.resolution_time", "unreviewed", null) },
];

function scopeRow(overrides: Partial<ScopeRow> = {}): ScopeRow {
  return { key: "repair", label: "Reparatur", state: { label: "Inklusive", tone: "yes", evidence: null, open: true }, suggestion: "Inklusive", fact: fact("scope.repair", "needs_review", "Inklusive"), ...overrides };
}

const lists: ScopeList[] = [
  { key: "other_included", label: "Weitere inklusive Leistungen", value: "Schulung", suggestion: "Schulung", fact: fact("scope.other_included", "unreviewed", "Schulung") },
];

function renderScope(rows: ScopeRow[] = [scopeRow()]) {
  return render(<ScopeCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} rows={rows} historyHref="/contracts/c1?tab=documents&subtab=history" source={() => null} />);
}

beforeEach(() => {
  window.localStorage.clear();
  apiPostMock.mockReset().mockResolvedValue({});
});

describe("SLA-Karte", () => {
  it("ein Bearbeiten für die ganze Karte; eigener Wert wird als Korrektur der Faktprüfung gespeichert", async () => {
    const saved = vi.fn();
    const user = userEvent.setup();
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit onSaved={saved} rows={slaRows} />);
    expect(screen.getAllByRole("button", { name: /bearbeiten/ })).toHaveLength(1);
    expect(screen.getByText("KI · Ungeprüft")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Service-Level (SLA) bearbeiten" }));
    expect(screen.getByRole("textbox", { name: "Reaktionszeit" })).toHaveValue("4 Stunden");
    await user.type(screen.getByRole("textbox", { name: "Lösungszeit" }), "8 Stunden");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(PATH, expect.objectContaining({ fact_key: "sla.resolution_time", action: "corrected", corrected_value: "8 Stunden" }));
    await waitFor(() => expect(saved).toHaveBeenCalled());
  });

  it("zeigt die KI-Sicherheit am Vorschlag", () => {
    const rows = [{ ...slaRows[0], fact: { ...fact("sla.response_time", "unreviewed", "4 Stunden"), ai_confidence: 0.92 } }];
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} rows={rows} />);
    expect(screen.getByText("KI · Ungeprüft").closest(".ai-origin")).toHaveAttribute("title", expect.stringContaining("KI-Sicherheit 92 %"));
  });

  it("ohne KI-Sicherheit: „Regel“, wenn feste Regeln den Wert wörtlich fanden", () => {
    const rows = [{ ...slaRows[0], fact: { ...fact("sla.response_time", "unreviewed", "4 Stunden"), ai_confidence: null, found_by_rule: true } }];
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} rows={rows} />);
    expect(screen.getByText("KI · Ungeprüft").closest(".ai-origin")).toHaveAttribute("title", expect.stringContaining("von festen Regeln wörtlich gefunden"));
  });

  it("eine Bestätigung lässt sich zurücknehmen", async () => {
    const user = userEvent.setup();
    const rows = [{ ...slaRows[0], fact: fact("sla.response_time", "confirmed", "4 Stunden") }];
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} rows={rows} />);
    // Bestätigen/Zurücknehmen stehen im „⋯“-Menü der Zeile.
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen: Reaktionszeit" }));
    await user.click(screen.getByRole("menuitem", { name: "Bestätigung zurücknehmen" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith(PATH, { fact_key: "sla.response_time", action: "reopened", expected_reviewed_at: null }));
  });

  it("bestätigt einen KI-Vorschlag", async () => {
    const user = userEvent.setup();
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} rows={slaRows} />);
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen: Reaktionszeit" }));
    await user.click(screen.getByRole("menuitem", { name: "Bestätigen" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith(PATH, { fact_key: "sla.response_time", action: "confirmed", expected_reviewed_at: null }));
  });

  it("zeigt bestätigte Werte als „KI · Bestätigt“, ohne Recht kein Bearbeiten", () => {
    const rows = [{ ...slaRows[0], fact: fact("sla.response_time", "confirmed", "4 Stunden") }];
    render(<SlaCard contractId="c1" orgSlug="klinik" canEdit={false} onSaved={() => {}} rows={rows} />);
    expect(screen.getByText("KI · Bestätigt")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Service-Level (SLA) bearbeiten" })).not.toBeInTheDocument();
  });
});

describe("Leistungsumfang-Karte", () => {
  it("geprüfte Leistung ohne „Zu prüfen“; ohne KI-Angabe neutral „Nicht angegeben“", () => {
    renderScope([
      scopeRow({ state: { label: "Inklusive", tone: "yes", evidence: null, open: false }, fact: fact("scope.repair", "confirmed", "Inklusive") }),
      scopeRow({ key: "calibration", label: "Kalibrierung", suggestion: null, state: { label: "Nicht angegeben", tone: "none", evidence: null, open: false }, fact: fact("scope.calibration", "unreviewed", null) }),
    ]);
    const table = screen.getByRole("table");
    expect(within(table).getByText("KI · Bestätigt")).toBeInTheDocument();
    expect(within(table).getByText("Nicht angegeben")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reparatur bestätigen" })).not.toBeInTheDocument();
  });

  it("Bearbeiten zeigt den angezeigten Wert; „Alle KI-Vorschläge bestätigen“ speichert Bestätigungen", async () => {
    const user = userEvent.setup();
    renderScope();
    expect(within(screen.getByRole("table")).getByText("Inklusive")).toBeInTheDocument();
    expect(screen.getAllByText("KI · Ungeprüft").length).toBeGreaterThan(0);
    expect(within(screen.getByRole("table")).queryByText(/^Zu prüfen$/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Leistungsumfang bearbeiten" }));
    expect(screen.getByRole("combobox", { name: "Reparatur" })).toHaveValue("Inklusive");
    await user.click(screen.getByRole("button", { name: "Alle KI-Vorschläge bestätigen" }));
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith(PATH, expect.objectContaining({ fact_key: "scope.repair", action: "confirmed" })));
  });

  it("legt eine Leistung selbst als exklusive fest und ergänzt eine eigene Leistung", async () => {
    const user = userEvent.setup();
    renderScope();
    await user.click(screen.getByRole("button", { name: "Leistungsumfang bearbeiten" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Reparatur" }), "Exklusive");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(1));
    expect(apiPostMock).toHaveBeenCalledWith(PATH, expect.objectContaining({ fact_key: "scope.repair", action: "corrected", corrected_value: "Exklusive" }));
  });

  it("Tabelle Leistung · Abdeckung · Herkunft mit Filtern; Link zur Analyse-Historie", async () => {
    const user = userEvent.setup();
    renderScope([scopeRow(), scopeRow({ key: "calibration", label: "Kalibrierung", state: { label: "Nicht angegeben", tone: "none", evidence: null, open: false }, suggestion: null, fact: undefined })]);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["Leistung", "Abdeckung", "Herkunft", "Aktionen"]);
    expect(within(table).getByRole("rowheader", { name: "Kalibrierung" })).toBeInTheDocument();
    const filters = screen.getByRole("group", { name: "Leistungen filtern" });
    expect(within(filters).getByRole("button", { name: /^Alle/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(filters).getByRole("button", { name: /Nicht angegeben/ }));
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["Kalibrierung"]);
    expect(screen.getByRole("link", { name: "Analyse-Historie" })).toHaveAttribute("href", "/contracts/c1?tab=documents&subtab=history");
  });

  it("weitere inklusive Leistungen: eigene Karte, eigene Leistung ergänzen", async () => {
    const user = userEvent.setup();
    render(<ScopeListCard contractId="c1" orgSlug="klinik" canEdit onSaved={() => {}} list={lists[0]} />);
    expect(screen.getByText("Schulung")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Weitere inklusive Leistungen bearbeiten" }));
    await user.type(screen.getByRole("textbox", { name: "Weitere inklusive Leistungen: Eintrag hinzufügen" }), "Hotline{Enter}");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith(PATH, expect.objectContaining({ fact_key: "scope.other_included", action: "corrected", corrected_value: "Schulung; Hotline" })));
  });

  it("exklusive Leistungen in der warmen Karte", () => {
    render(<ScopeListCard contractId="c1" orgSlug="klinik" canEdit={false} onSaved={() => {}} list={{ key: "other_excluded", label: "Exklusive Leistungen", value: "Sturzschäden; Vorsatz", suggestion: null, fact: undefined }} />);
    expect(screen.getByRole("heading", { name: "Exklusive Leistungen" }).closest("section")).toHaveClass("scope-list-card--excluded");
    // Exklusive Leistungen als Text (Entwurf), nicht als Aufzählung.
    expect(screen.getByText("Sturzschäden")).toBeInTheDocument();
    expect(screen.getByText("Vorsatz")).toBeInTheDocument();
  });
});

describe("Weitere inklusive Leistungen – thematisch", () => {
  it("fasst nach festen Stichwörtern zusammen, mit Zahl je Gruppe", () => {
    const value = "Sicherheitstest nach IEC 62353; Sichtprüfung der Geräte; Austausch der Akkus; Softwareupdates; Hotline werktags";
    render(<ScopeListCard contractId="c1" orgSlug="klinik" canEdit={false} onSaved={() => {}} list={{ key: "other_included", label: "Weitere inklusive Leistungen", value, suggestion: null, fact: undefined }} />);
    expect(screen.getByText("Prüfung & Sicherheit").closest("summary")).toHaveTextContent("2 Punkte");
    expect(screen.getByText("Wartung & Verschleißteile").closest("summary")).toHaveTextContent("1 Punkt");
    expect(screen.getByText("Software & Hardware")).toBeInTheDocument();
    expect(screen.getByText("Service & Support")).toBeInTheDocument();
  });
});
