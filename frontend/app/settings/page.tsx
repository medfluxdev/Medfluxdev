"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { useCallback, useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import DefinitionList from "@/components/ui/DefinitionList";
import StatusBadge from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import type {
  AISnapshot,
  AITestResponse,
  LocalModel,
  ProviderInfo,
  SelectionInfo,
} from "@/lib/ai-types";

const TEST_TEXT = "Antworte kurz und sachlich auf Deutsch.";

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="card card-pad settings-section"
      aria-labelledby={`settings-${id}`}
    >
      <h2 className="card-title" id={`settings-${id}`} tabIndex={-1}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function capabilityChips(model: LocalModel | null) {
  if (!model) return [];
  const caps: {
    key: "text" | "vision" | "embedding";
    label: string;
  }[] = [
    { key: "text", label: "Text" },
    { key: "vision", label: "Vision / Bild" },
    { key: "embedding", label: "Embedding" },
  ];
  return caps
    .filter((c) => model.capabilities[c.key] === true)
    .map((c) => c.label);
}

function selectionBadge(sel: SelectionInfo) {
  if (sel.state === "ready") {
    return <StatusBadge tone="success" label="Bereit" />;
  }
  if (sel.provider_reachable) {
    return <StatusBadge tone="warning" label="Nicht verfügbar" />;
  }
  return <StatusBadge tone="critical" label="Nicht erreichbar" />;
}

const SETTINGS_SECTIONS = [
  { id: "allgemein", label: "Allgemein" },
  { id: "lokale-ki", label: "Lokale KI" },
  { id: "dokumente", label: "Dokumentenverarbeitung" },
  { id: "speicher", label: "Speicher & Daten" },
  { id: "sicherheit", label: "Benutzer & Sicherheit" },
  { id: "diagnose", label: "System & Diagnose" },
] as const;

type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number]["id"];

export default function SettingsPage() {
  const push = useToast();
  const { account, role } = useAuth();
  const canManageAi = Boolean(account?.is_developer || role === "admin");
  const [activeSection, setActiveSection] =
    useState<SettingsSectionId>("lokale-ki");

  const [snapshot, setSnapshot] = useState<AISnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [providerId, setProviderId] = useState("");
  const [modelId, setModelId] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AITestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGet<AISnapshot>("/api/ai/snapshot", undefined, 40000);
      setSnapshot(res);
      setProviderId(res.selection.provider_id);
      setModelId(res.selection.model_id);
    } catch {
      setError("Einstellungen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const providers = useMemo<ProviderInfo[]>(
    () => (snapshot ? snapshot.providers : []),
    [snapshot]
  );

  const activeProvider = useMemo<ProviderInfo | null>(
    () => providers.find((p) => p.provider_id === providerId) ?? null,
    [providers, providerId]
  );

  const activeModel = useMemo<LocalModel | null>(() => {
    if (!activeProvider) return null;
    return (
      activeProvider.models.find((m) => m.model_id === modelId) ?? null
    );
  }, [activeProvider, modelId]);

  const selectableModels = useMemo<LocalModel[]>(
    () => (activeProvider ? activeProvider.models : []),
    [activeProvider]
  );

  const onProviderChange = (value: string) => {
    setProviderId(value);
    const next = providers.find((p) => p.provider_id === value);
    setModelId(next && next.models.length > 0 ? next.models[0].model_id : "");
  };

  const runTest = useCallback(async () => {
    setTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      const res = await apiPost<AITestResponse>(
        "/api/ai/test",
        { text: TEST_TEXT },
        120000
      );
      setTestResult(res);
    } catch {
      setTestError("KI-Verbindungstest fehlgeschlagen.");
    } finally {
      setTesting(false);
    }
  }, []);

  const save = useCallback(async () => {
    if (!snapshot || !activeProvider || !modelId) {
      setSaveError("Bitte eine Auswahl von Provider und Modell treffen.");
      return;
    }
    if (!activeProvider.models.some((m) => m.model_id === modelId)) {
      setSaveError("Das gewählte Modell ist bei diesem Provider nicht verfügbar.");
      return;
    }
    if (activeProvider.provider_id === "generic-openai" && !activeProvider.endpoint) {
      setSaveError("Für diesen Anbieter ist kein Endpunkt verfügbar.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const res = await apiPut<AISnapshot>("/api/ai/selection", {
        provider_id: activeProvider.provider_id,
        model_id: modelId,
        endpoint: activeProvider.endpoint,
      });
      setSnapshot(res);
      setProviderId(res.selection.provider_id);
      setModelId(res.selection.model_id);
      push("KI-Auswahl gespeichert.", "success");
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "KI-Auswahl konnte nicht gespeichert werden."
      );
    } finally {
      setSaving(false);
    }
  }, [snapshot, activeProvider, modelId, push]);

  return (
    <div className="page">
      <PageHeader
        title="Einstellungen"
        description="Laufzeit- und Systemstatus der lokalen Medflux-Installation."
      />

      <div className="settings-layout">
        <nav
          className="settings-nav"
          aria-label="Einstellungsbereiche"
        >
          <Link className="settings-nav-item" href="/profile">
            Mein Profil
          </Link>
          {SETTINGS_SECTIONS.map((item) => {
            const selected = activeSection === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`settings-nav-item${selected ? " active" : ""}`}
                aria-current={selected ? "page" : undefined}
                onClick={() => setActiveSection(item.id)}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="settings-content">
          {activeSection === "allgemein" && (
            <Section id="allgemein" title="Allgemein">
            <DefinitionList
              rules={[
                {
                  label: "Installation",
                  value: snapshot ? snapshot.application_version : "–",
                  highlight: true,
                },
                {
                  label: "Verarbeitungsprinzip",
                  value:
                    "Fakten extrahiert die lokale KI; Fristen, Kosten und Warnstufen berechnet der Code.",
                },
              ]}
            />
          </Section>
          )}

          {activeSection === "lokale-ki" && (
            <Section id="lokale-ki" title="Lokale KI">
            {loading && <LoadingState>Einstellungen werden geladen…</LoadingState>}

            {error && !loading && (
              <InlineAlert
                tone="critical"
                role="alert"
                action={
                  <Button size="sm" onClick={load}>
                    Erneut laden
                  </Button>
                }
              >
                {error}
              </InlineAlert>
            )}

            {snapshot && !loading && (
              <>
                <InlineAlert tone="info" role="status">
                  Die aktive Auswahl wird serverseitig gespeichert und überlebt
                  Neustarts. Gespeicherte Verträge werden beim Wechsel des
                  Modells nicht automatisch neu analysiert.
                </InlineAlert>

                <div className="form-field">
                  <label htmlFor="ki-provider">
                    KI-Provider
                    {activeProvider && (
                      <StatusBadge
                        tone={activeProvider.reachable ? "success" : "critical"}
                        label={activeProvider.reachable ? "erreichbar" : "nicht erreichbar"}
                      />
                    )}
                  </label>
                  <select
                    id="ki-provider"
                    className="select"
                    value={providerId}
                    disabled={!canManageAi}
                    onChange={(e) => onProviderChange(e.target.value)}
                  >
                    {providers.map((p) => (
                      <option key={`${p.provider_id}:${p.endpoint ?? ""}`} value={p.provider_id}>
                        {p.display_name}
                        {p.reachable ? "" : " (nicht erreichbar)"}
                      </option>
                    ))}
                  </select>
                  {activeProvider?.message_de && !activeProvider.reachable && (
                    <p className="field-note">{activeProvider.message_de}</p>
                  )}
                </div>

                <div className="form-field">
                  <label htmlFor="ki-model">KI-Modell</label>
                  <select
                    id="ki-model"
                    className="select"
                    value={modelId}
                    disabled={!canManageAi || selectableModels.length === 0}
                    onChange={(e) => setModelId(e.target.value)}
                  >
                    {selectableModels.length === 0 && (
                      <option value="">– verfügbare Modelle unbekannt –</option>
                    )}
                    {selectableModels.map((m) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.model_id}
                        {m.loaded === true ? " (geladen)" : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <span className="field-label" id="ki-capabilities-label">
                    Fähigkeiten
                  </span>
                  <div className="capability-chips" aria-labelledby="ki-capabilities-label">
                    {activeModel ? (
                      capabilityChips(activeModel).length > 0 ? (
                        capabilityChips(activeModel).map((label) => (
                          <StatusBadge key={label} tone="neutral" label={label} />
                        ))
                      ) : (
                        <span className="field-note">Unbekannt</span>
                      )
                    ) : (
                      <span className="field-note">–</span>
                    )}
                  </div>
                </div>

                <div className="form-field">
                  <span className="field-label">Aktive Auswahl</span>
                  {selectionBadge(snapshot.selection)}
                  <p className="field-note">{snapshot.selection.message_de}</p>
                </div>

                {!canManageAi && (
                  <InlineAlert tone="info" role="status">
                    Die globale KI-Auswahl und Verbindungstests sind Administratoren bzw. dem Developer vorbehalten.
                  </InlineAlert>
                )}

                {saveError && (
                  <InlineAlert tone="critical" role="alert">
                    {saveError}
                  </InlineAlert>
                )}

                <div className="import-actions">
                  <Button
                    variant="primary"
                    onClick={save}
                    disabled={!canManageAi || saving || selectableModels.length === 0 || !modelId}
                  >
                    {saving ? "Speichern…" : "Auswahl speichern"}
                  </Button>
                  <Button variant="ghost" onClick={runTest} disabled={!canManageAi || testing}>
                    {testing ? "Test läuft…" : "KI-Verbindung testen"}
                  </Button>
                </div>

                {testError && (
                  <InlineAlert tone="critical" role="alert">
                    {testError}
                  </InlineAlert>
                )}

                {testResult && !testError && (
                  <InlineAlert
                    tone={testResult.error ? "warning" : "success"}
                    role="status"
                  >
                    {testResult.error
                      ? `Der Test-Endpunkt meldet: ${testResult.error}`
                      : `Verbindung erfolgreich (${testResult.provider} / ${testResult.model}).`}
                    {testResult.response && (
                      <span className="result-msg">
                        Antwort (gekürzt): {testResult.response.slice(0, 500)}
                      </span>
                    )}
                  </InlineAlert>
                )}

                <details className="advanced-details">
                  <summary>Erweiterte Einstellungen</summary>
                  <DefinitionList
                    rules={[
                      {
                        label: "Auswahl-Quelle",
                        value:
                          snapshot.selection.source === "db"
                            ? "gespeichert (DB)"
                            : "Umgebungskonfiguration",
                      },
                      {
                        label: "Bootstrap-Provider",
                        value: snapshot.configured_default_provider,
                      },
                      {
                        label: "Bootstrap-Modell",
                        value: snapshot.configured_default_model,
                      },
                      ...providers
                        .filter((p) => p.endpoint)
                        .map((p) => ({
                          label: `Endpunkt (${p.display_name})`,
                          value: p.endpoint ?? "–",
                        })),
                    ]}
                  />
                </details>
              </>
            )}
          </Section>
          )}

          {activeSection === "dokumente" && (
            <Section id="dokumente" title="Dokumentenverarbeitung">
            <ul className="side-note">
              <li>
                PDF- und DOCX-Verträge werden vollständig lokal mit PyMuPDF
                und python-docx gelesen.
              </li>
              <li>
                Gescannte Seiten werden nur bei Bedarf lokal per OCR erfasst.
              </li>
              <li>
                Einstellungen zur Verarbeitung greifen für neu importierte
                Dokumente; bestehende Datenstände bleiben unverändert.
              </li>
            </ul>
          </Section>
          )}

          {activeSection === "speicher" && (
            <Section id="speicher" title="Speicher &amp; Daten">
            <ul className="side-note">
              <li>
                Verträge, Extraktionen und Quellennachweise liegen in der
                lokalen Datenbank.
              </li>
              <li>
                Lokale Datensicherungen sind möglich; dafür ist die
                Datenbankeinheit maßgeblich.
              </li>
            </ul>
          </Section>
          )}

          {activeSection === "sicherheit" && (
            <Section id="sicherheit" title="Benutzer &amp; Sicherheit">
            <p className="side-note">
              Benutzer, Rollen und Organisationszuordnungen werden serverseitig verwaltet.
              Änderungen werden an die aktive Sitzung und deren Berechtigungen gebunden.
              Vertragsdaten bleiben lokal; KI-Provider werden ausschließlich über
              konfigurierte lokale Endpunkte angesprochen.
            </p>
          </Section>
          )}

          {activeSection === "diagnose" && (
            <Section id="diagnose" title="System &amp; Diagnose">
            <p className="page-sub">
              Führt einen kurzen Rückkanal-Test gegen das lokal ausgewählte
              Modell aus.
            </p>
            <div className="import-actions">
              <Button variant="primary" onClick={runTest} disabled={!canManageAi || testing}>
                {testing ? "Test läuft…" : "KI-Verbindung testen"}
              </Button>
            </div>

            {testError && (
              <InlineAlert tone="critical" role="alert">
                {testError}
              </InlineAlert>
            )}

            {testResult && !testError && (
              <InlineAlert
                tone={testResult.error ? "warning" : "success"}
                role="status"
              >
                {testResult.error
                  ? `Der Test-Endpunkt meldet: ${testResult.error}`
                  : `Verbindung erfolgreich (${testResult.provider} / ${testResult.model}).`}
                {testResult.response && (
                  <span className="result-msg">
                    Antwort (gekürzt): {testResult.response.slice(0, 500)}
                  </span>
                )}
              </InlineAlert>
            )}
          </Section>
          )}
        </div>
      </div>
    </div>
  );
}
