import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { ToastProvider } from "@/components/ui/Toast";
import type { AISnapshot } from "@/lib/ai-types";

const apiGetMock = vi.fn();
const apiPostMock = vi.fn();
const apiPutMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
  apiPut: (...args: unknown[]) => apiPutMock(...args),
}));

function modelFixture(id: string, caps: Partial<{ text: boolean; vision: boolean | null; embedding: boolean | null }> = {}) {
  return {
    provider_id: "ollama",
    model_id: id,
    display_name: null,
    state: "available" as const,
    loaded: null,
    context_length: 40960,
    quantization: "Q4_K_M",
    family: "qwen3",
    parameter_size: "8.2B",
    capabilities: { text: true, vision: null, embedding: null, ...caps },
  };
}

function snapshotFixture(overrides: Partial<AISnapshot> = {}): AISnapshot {
  return {
    selection: {
      provider_id: "ollama",
      model_id: "qwen3:8b-q4",
      source: "env",
      state: "ready",
      provider_reachable: true,
      model_available: true,
      message_de: "Die lokale KI ist betriebsbereit.",
    },
    providers: [
      {
        provider_id: "ollama",
        display_name: "Ollama",
        kind: "native",
        endpoint: "http://127.0.0.1:11434",
        reachable: true,
        detection: "native",
        message_de: null,
        models: [
          modelFixture("qwen3:8b-q4"),
          modelFixture("qwen3-vl:8b-instruct", { vision: true }),
        ],
      },
      {
        provider_id: "lmstudio",
        display_name: "LM Studio",
        kind: "openai-compatible",
        endpoint: "http://127.0.0.1:1234",
        reachable: false,
        detection: null,
        message_de: "Provider 'LM Studio' ist nicht erreichbar.",
        models: [],
      },
    ],
    configured_default_provider: "ollama",
    configured_default_model: "qwen3:8b",
    application_version: "0.1.0",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  apiPostMock.mockReset();
  apiPutMock.mockReset();
});

async function renderWithSnapshot(snapshot: AISnapshot, provider = ToastProvider) {
  apiGetMock.mockImplementation((path: string) =>
    path === "/api/auth/me"
      ? Promise.reject(new Error("Request failed: 503"))
      : Promise.resolve(snapshot)
  );
  const Provider = provider;
  const renderFn = (ui: React.ReactNode) =>
    Provider === ToastProvider ? <ToastProvider>{ui}</ToastProvider> : (ui as React.ReactElement);
  const utils = render(renderFn(<SettingsPage />));
  await waitFor(() =>
    expect(apiGetMock).toHaveBeenCalledWith("/api/ai/snapshot", undefined, 40000)
  );
  await userEvent.click(screen.getByRole("button", { name: "Lokale KI" }));
  await waitFor(() => expect(screen.getByText("Aktive Auswahl")).toBeInTheDocument());
  return utils;
}

describe("Einstellungen (STEP 6B, Anbieter-unabhängig)", () => {
  it("zeigt Ladezustand und Fehler ehrlich an", async () => {
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<SettingsPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Einstellungen konnten nicht geladen werden.")
      ).toBeInTheDocument()
    );
  });

  it("zeigt die aktive Auswahl als 'Bereit' inkl. Provider und Modell", async () => {
    await renderWithSnapshot(snapshotFixture());
    expect(
      screen.getByRole("heading", { name: "Einstellungen" })
    ).toBeInTheDocument();
    expect(screen.getByText("Bereit")).toBeInTheDocument();
    expect(screen.getByText("Die lokale KI ist betriebsbereit.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /qwen3:8b-q4/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Ollama/ })).toBeInTheDocument();
    expect(screen.getByText("Text")).toBeInTheDocument();
  });

  it("meldet fehlendes Modell ehrlich (kein erfundener Zustand)", async () => {
    await renderWithSnapshot(
      snapshotFixture({
        selection: {
          provider_id: "ollama",
          model_id: "geister-modell",
          source: "db",
          state: "unavailable",
          provider_reachable: true,
          model_available: false,
          message_de:
            "Das Modell 'geister-modell' ist bei 'Ollama' nicht (mehr) installiert.",
        },
      })
    );
    expect(screen.getByText("Nicht verfügbar")).toBeInTheDocument();
    expect(
      screen.getByText("Das Modell 'geister-modell' ist bei 'Ollama' nicht (mehr) installiert.")
    ).toBeInTheDocument();
  });

  it("meldet nicht erreichbaren Provider ehrlich an", async () => {
    await renderWithSnapshot(
      snapshotFixture({
        selection: {
          provider_id: "ollama",
          model_id: "qwen3:8b-q4",
          source: "env",
          state: "unavailable",
          provider_reachable: false,
          model_available: false,
          message_de: "Ollama ist nicht erreichbar.",
        },
      })
    );
    expect(screen.getByText("Nicht erreichbar")).toBeInTheDocument();
    expect(screen.getByText("Ollama ist nicht erreichbar.")).toBeInTheDocument();
  });

  it("Zeigt nach Provider-Wechsel die Modelle des gewählten Providers", async () => {
    const snap = snapshotFixture();
    snap.providers[1] = {
      ...snap.providers[1],
      reachable: true,
      detection: "openai-compatible",
      models: [modelFixture("lm-modell")],
    };
    await renderWithSnapshot(snap);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText(/KI-Provider/), ["lmstudio"]);
    await waitFor(() =>
      expect(screen.getByRole("option", { name: /lm-modell/ })).toBeInTheDocument()
    );
    expect(screen.getByText("Text")).toBeInTheDocument();
  });

  it("speichert die Auswahl via PUT und bestätigt mit Toast", async () => {
    const snap = snapshotFixture();
    apiPutMock.mockResolvedValue(
      snapshotFixture({
        selection: { ...snap.selection, source: "db" },
      })
    );
    const user = userEvent.setup();
    await renderWithSnapshot(snap);

    await user.click(screen.getByRole("button", { name: "Auswahl speichern" }));
    await waitFor(() =>
      expect(apiPutMock).toHaveBeenCalledWith(
        "/api/ai/selection",
        expect.objectContaining({
          provider_id: "ollama",
          model_id: "qwen3:8b-q4",
          endpoint: "http://127.0.0.1:11434",
        })
      )
    );
    await waitFor(() =>
      expect(screen.getByText("KI-Auswahl gespeichert.")).toBeInTheDocument()
    );
  });

  it("zeigt Backend-Fehler beim Speichern ehrlich an", async () => {
    apiPutMock.mockRejectedValue(
      new Error("Provider 'Ollama' ist nicht erreichbar und kann nicht ausgewählt werden.")
    );
    const user = userEvent.setup();
    await renderWithSnapshot(snapshotFixture());
    await user.click(screen.getByRole("button", { name: "Auswahl speichern" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "Provider 'Ollama' ist nicht erreichbar und kann nicht ausgewählt werden."
        )
      ).toBeInTheDocument()
    );
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße", async () => {
    const { container } = await renderWithSnapshot(snapshotFixture());
    await waitFor(() => screen.getByText("Bereit"));
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});