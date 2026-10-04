import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClientNav from "@/components/ClientNav";
import SettingsPage from "@/app/settings/page";
import NachweisePage from "@/app/nachweise/page";
import type { AISnapshot, AITestResponse } from "@/lib/ai-types";
import type { ContractListResponse } from "@/lib/contract-types";

const apiGetMock = vi.fn();
const apiPutMock = vi.fn();
const apiPostMock = vi.fn();

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
  apiPut: (...args: unknown[]) => apiPutMock(...args),
  apiUpload: vi.fn(),
  contentUrl: vi.fn(() => "http://localhost:8000/x"),
}));

const pushMock = vi.fn();
let navPath = "/";
vi.mock("next/navigation", () => ({
  usePathname: () => navPath,
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  apiPostMock.mockReset();
  pushMock.mockReset();
  navPath = "/";
});

describe("Shell: Topbar-Eingaben", () => {
  it("zeigt keine veraltete Import-CTA in der Topbar", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/health") return Promise.resolve({ status: "ok" });
      if (path === "/api/ai/status") return Promise.resolve({ provider: "ollama", available: true, model: "qwen", model_available: true, message: "Bereit" });
      return Promise.resolve({});
    });
    render(<ClientNav>Inhalt</ClientNav>);
    expect(screen.queryByRole("link", { name: "Vertrag importieren" })).not.toBeInTheDocument();
  });

  it("oeffnet die Suche ueber die Kopfzeile (Befehlspalette)", async () => {
    apiGetMock.mockResolvedValue({ status: "ok" });
    const user = userEvent.setup();
    render(<ClientNav>Inhalt</ClientNav>);
    await user.click(screen.getByRole("button", { name: "Suchen und Befehle (Strg+K)" }));
    expect(screen.getByRole("dialog", { name: "Befehle und Suche" })).toBeInTheDocument();
  });

  it("fragt API- und KI-Status getrennt ab und zeigt den KI-Status", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/health") return Promise.resolve({ status: "ok" });
      if (path === "/api/ai/status") return Promise.resolve({ provider: "ollama", available: true, model: "qwen", model_available: true, message: "Bereit" });
      return Promise.resolve({});
    });
    render(<ClientNav>Inhalt</ClientNav>);
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith("/health"));
    await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith("/api/ai/status"));
    expect(await screen.findByText("Lokale KI bereit (qwen)")).toBeInTheDocument();
  });
});

describe("Einstellungen: KI-Test error-path ehrlich und terminiert", () => {
  function snapshotFixture(): AISnapshot {
    return {
      selection: { provider_id: "ollama", model_id: "qwen3:8b-q4", source: "env", state: "unavailable", provider_reachable: false, model_available: false, message_de: "Ollama ist nicht erreichbar." },
      providers: [{ provider_id: "ollama", display_name: "Ollama", kind: "native", endpoint: "http://127.0.0.1:11434", reachable: false, detection: null, message_de: "Ollama ist nicht erreichbar.", models: [] }],
      configured_default_provider: "ollama", configured_default_model: "qwen3:8b", application_version: "0.1.0",
    };
  }

  it("zeigt beim Test-Fehler das ehrliche Fehler-Banner statt Dauerladen", async () => {
    apiGetMock.mockResolvedValue(snapshotFixture());
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByText("Nicht erreichbar")).toBeInTheDocument());
    const errorResult: AITestResponse = { provider: "ollama", model: "qwen3:8b-q4", response: null, error: "Die lokale KI ist derzeit nicht verfügbar." };
    apiPostMock.mockResolvedValue(errorResult);
    await user.click(screen.getByRole("button", { name: "KI-Verbindung testen" }));
    await waitFor(() => expect(screen.getByText("Der Test-Endpunkt meldet: Die lokale KI ist derzeit nicht verfügbar.")).toBeInTheDocument());
    expect(screen.queryByText(/Test läuft…/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Verbindung erfolgreich/)).not.toBeInTheDocument();
  });

  it("fuehrt bei Erfolg einen echten POST aus und zeigt Erfolgsbanner", async () => {
    apiGetMock.mockResolvedValue(snapshotFixture());
    const user = userEvent.setup();
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByText("Nicht erreichbar")).toBeInTheDocument());
    const okResult: AITestResponse = { provider: "ollama", model: "qwen3:8b-q4", response: "Betriebsbereit.", error: null };
    apiPostMock.mockResolvedValue(okResult);
    await user.click(screen.getByRole("button", { name: "KI-Verbindung testen" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith("/api/ai/test", expect.objectContaining({ text: expect.any(String) }), 120000));
    expect(screen.getByText(/Verbindung erfolgreich/)).toBeInTheDocument();
  });
});

describe("Nachweise: Detailfehler trennt sich von der Auswahlliste", () => {
  function listFixture(): ContractListResponse {
    return { items: [{ contract_id: "c1", contract_number: "4001", contract_title: "Wartungsvertrag", supplier: "ABIOMED" } as ContractListResponse["items"][number]], total_count: 1, page: 1, page_size: 100 };
  }

  it("bleibt nach fehlgeschlagenem Detail-Load bedienbar und bietet Retry", async () => {
    apiGetMock.mockResolvedValueOnce(listFixture());
    apiGetMock.mockRejectedValueOnce(new Error("detail gone"));
    apiGetMock.mockResolvedValueOnce({ contract_id: "c1", documents: [], evidence: [], overrides: [], audit_log: [], fact_reviews: [] });
    const user = userEvent.setup();
    render(<NachweisePage />);
    await waitFor(() => expect(screen.getByText("Vertragsdetail konnte nicht geladen werden.")).toBeInTheDocument());
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select).toBeEnabled();
    expect(select.options.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Erneut laden" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Erneut laden" }));
    await waitFor(() => expect(screen.getByText("Quellen")).toBeInTheDocument());
    expect(screen.getByText("Belege")).toBeInTheDocument();
    expect(screen.queryByText("Vertragsdetail konnte nicht geladen werden.")).not.toBeInTheDocument();
  });
});