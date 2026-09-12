"use client";

import { useMemo, useState } from "react";
import ContractDetail from "./ContractDetail";
import type { ContractDetailResponse, MoneyValue } from "@/lib/contract-detail-types";
import { formatCurrency, formatDate } from "@/lib/format";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload?: () => void;
}

type TabKey = "overview" | "term" | "finance" | "services" | "equipment" | "documents";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Übersicht" },
  { key: "term", label: "Laufzeit & Kündigung" },
  { key: "finance", label: "Finanzen" },
  { key: "services", label: "Leistungen & SLA" },
  { key: "equipment", label: "Geräte" },
  { key: "documents", label: "Dokumente & Prüfung" },
];

function money(value: MoneyValue): string {
  if (value.amount == null || !value.currency) return "Nicht verfügbar";
  return formatCurrency(String(value.amount), value.currency);
}

function yesNo(value: boolean | null): string {
  if (value == null) return "Unbekannt";
  return value ? "Ja" : "Nein";
}

function InfoCard({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="cw-info-card">
      <span className="cw-info-label">{label}</span>
      <strong className="cw-info-value">{value}</strong>
      {hint ? <span className="cw-info-hint">{hint}</span> : null}
    </div>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="cw-section">
      <div className="cw-section-head">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

export default function ContractWorkspace({ data, orgSlug, onReload }: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const openTasks = useMemo(() => data.work_items.filter((item) => item.status !== "resolved"), [data.work_items]);
  const actionableWarnings = useMemo(() => data.warnings.filter((warning) => warning.requires_action || warning.requires_review), [data.warnings]);

  const scopeEntries = [
    ["Wartung", data.scope.maintenance],
    ["Inspektion", data.scope.inspection],
    ["Reparatur", data.scope.repair],
    ["Kalibrierung", data.scope.calibration],
    ["Software-Updates", data.scope.software_updates],
    ["Remote-Support", data.scope.remote_support],
    ["Technischer Support", data.scope.technical_support],
    ["Ersatzteile", data.scope.spare_parts_included],
    ["Verbrauchsmaterial", data.scope.consumables_included],
    ["Notdienst", data.scope.emergency_service],
  ] as const;

  return (
    <div className="contract-workspace">
      <header className="cw-header">
        <div>
          <div className="cw-breadcrumb">Verträge / {data.contract_number ?? data.contract_id}</div>
          <h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1>
          <p>{[data.contract_number ? `Nr. ${data.contract_number}` : null, data.supplier].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="cw-header-badges">
          <span className="cw-badge cw-badge-green">{data.status ?? "Unbekannt"}</span>
          <span className={`cw-badge ${data.risk_level === "high" ? "cw-badge-red" : ""}`}>{data.risk_level ? `Risiko: ${data.risk_level}` : "Risiko unbekannt"}</span>
          {data.review.requires_manual_review ? <span className="cw-badge cw-badge-amber">Manuelle Prüfung</span> : null}
        </div>
      </header>

      <nav className="cw-tabs" aria-label="Vertragsbereiche">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? "active" : ""}
            aria-current={activeTab === tab.key ? "page" : undefined}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="cw-content">
        {activeTab === "overview" && (
          <>
            <div className="cw-kpi-grid">
              <InfoCard label="Status" value={data.status ?? "Unbekannt"} />
              <InfoCard label="Vertragsende" value={data.dates.documented_end_date ? formatDate(data.dates.documented_end_date) : data.dates.calculated_end_date ? formatDate(data.dates.calculated_end_date) : "Nicht verfügbar"} />
              <InfoCard label="Jährliche Kosten" value={money(data.costs.annual_recurring)} />
              <InfoCard label="Kündigungsfrist" value={data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"} />
              <InfoCard label="Risiko" value={data.risk_level ?? "Unbekannt"} />
            </div>

            {(openTasks.length > 0 || actionableWarnings.length > 0) && (
              <Section title="Handlungsbedarf" description="Offene Aufgaben und relevante Warnungen">
                <div className="cw-task-list">
                  {openTasks.slice(0, 6).map((item) => (
                    <div className="cw-task" key={item.work_item_id}>
                      <span className={`cw-priority cw-priority-${item.severity}`}>{item.severity}</span>
                      <div>
                        <strong>{item.title_de}</strong>
                        {item.why_de ? <p>{item.why_de}</p> : null}
                      </div>
                      <span>{item.target_date ? formatDate(item.target_date) : "Keine Frist"}</span>
                    </div>
                  ))}
                  {actionableWarnings.slice(0, 4).map((warning, index) => (
                    <div className="cw-task" key={`${warning.warning_type}-${index}`}>
                      <span className={`cw-priority cw-priority-${warning.severity}`}>{warning.severity}</span>
                      <div><strong>{warning.title_de}</strong></div>
                      <span>{warning.target_date ? formatDate(warning.target_date) : "Prüfung erforderlich"}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            <div className="cw-two-col">
              <Section title="Leistungsüberblick" description="Kurzer Überblick über den Vertragsumfang">
                <div className="cw-chip-list">
                  {scopeEntries.filter(([, value]) => value === true).slice(0, 8).map(([label]) => <span className="cw-chip" key={label}>{label}</span>)}
                  {scopeEntries.every(([, value]) => value !== true) ? <span className="cw-muted">Keine eindeutig bestätigten Leistungen.</span> : null}
                </div>
              </Section>
              <Section title="Daten & Prüfung" description="Qualität und Nachvollziehbarkeit">
                <div className="cw-mini-stats">
                  <div><strong>{data.evidence.length}</strong><span>Nachweise</span></div>
                  <div><strong>{data.documents.length}</strong><span>Dokumente</span></div>
                  <div><strong>{data.contract_review.unresolved_count}</strong><span>Offene Prüfungen</span></div>
                </div>
              </Section>
            </div>
          </>
        )}

        {activeTab === "term" && (
          <>
            <div className="cw-kpi-grid cw-kpi-grid-four">
              <InfoCard label="Beginn" value={data.dates.start_date ? formatDate(data.dates.start_date) : "Nicht verfügbar"} />
              <InfoCard label="Dokumentiertes Ende" value={data.dates.documented_end_date ? formatDate(data.dates.documented_end_date) : "Nicht verfügbar"} />
              <InfoCard label="Berechnetes Ende" value={data.dates.calculated_end_date ? formatDate(data.dates.calculated_end_date) : "Nicht verfügbar"} />
              <InfoCard label="Restlaufzeit" value={data.dates.days_until_end != null ? `${data.dates.days_until_end} Tage` : "Nicht verfügbar"} />
            </div>
            <Section title="Kündigung & Verlängerung">
              <dl className="cw-definition-grid">
                <div><dt>Spätester Kündigungstermin</dt><dd>{data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"}</dd></div>
                <div><dt>Automatische Verlängerung</dt><dd>{yesNo(data.dates.automatic_renewal)}</dd></div>
                <div><dt>Nächste Verlängerung</dt><dd>{data.dates.next_renewal_date ? formatDate(data.dates.next_renewal_date) : "Nicht verfügbar"}</dd></div>
                <div><dt>Mindestlaufzeit</dt><dd>{data.dates.minimum_duration_months != null ? `${data.dates.minimum_duration_months} Monate` : "Nicht verfügbar"}</dd></div>
                <div><dt>Zahlungsbeginn</dt><dd>{data.dates.payment_start_rule ?? "Nicht verfügbar"}</dd></div>
                <div><dt>Aktueller Status</dt><dd>{data.dates.current_status ?? "Unbekannt"}</dd></div>
              </dl>
            </Section>
            {(data.dates.calculated_end_basis?.explanation || data.dates.latest_cancellation_basis?.explanation) && (
              <Section title="Berechnungsgrundlage" description="Begründungen direkt bei Laufzeit und Kündigung">
                <div className="cw-note-list">
                  {data.dates.calculated_end_basis?.explanation ? <p>{data.dates.calculated_end_basis.explanation}</p> : null}
                  {data.dates.latest_cancellation_basis?.explanation ? <p>{data.dates.latest_cancellation_basis.explanation}</p> : null}
                </div>
              </Section>
            )}
          </>
        )}

        {activeTab === "finance" && (
          <>
            <div className="cw-kpi-grid cw-kpi-grid-four">
              <InfoCard label="Jährlich wiederkehrend" value={money(data.costs.annual_recurring)} />
              <InfoCard label="Monatlich wiederkehrend" value={money(data.costs.monthly_recurring)} />
              <InfoCard label="Steuersatz" value={data.costs.tax_rate_percent != null ? `${data.costs.tax_rate_percent} %` : "Nicht verfügbar"} />
              <InfoCard label="Bezugsperiode" value={data.costs.source_period ?? "Nicht verfügbar"} />
            </div>
            <div className="cw-two-col">
              <Section title="Kostenstruktur">
                {data.costs.category_totals.length > 0 ? (
                  <div className="cw-list-rows">
                    {data.costs.category_totals.map((item) => (
                      <div key={item.key}><span>{item.label}</span><strong>{item.amount != null && item.currency ? formatCurrency(String(item.amount), item.currency) : "Nicht verfügbar"}</strong></div>
                    ))}
                  </div>
                ) : <p className="cw-muted">Keine verlässlichen Kostenkategorien verfügbar.</p>}
              </Section>
              <Section title="Steuer & Brutto/Netto">
                <dl className="cw-definition-grid cw-definition-single">
                  <div><dt>Steuerbasis</dt><dd>{data.costs.tax_basis ?? "Nicht verfügbar"}</dd></div>
                  <div><dt>Monatlich netto</dt><dd>{data.costs.tax_breakdown?.monthly_net && data.costs.tax_breakdown.currency ? formatCurrency(data.costs.tax_breakdown.monthly_net, data.costs.tax_breakdown.currency) : "Nicht verfügbar"}</dd></div>
                  <div><dt>Monatlich brutto</dt><dd>{data.costs.tax_breakdown?.monthly_gross && data.costs.tax_breakdown.currency ? formatCurrency(data.costs.tax_breakdown.monthly_gross, data.costs.tax_breakdown.currency) : "Nicht verfügbar"}</dd></div>
                  <div><dt>Jährlich brutto</dt><dd>{data.costs.tax_breakdown?.annual_gross && data.costs.tax_breakdown.currency ? formatCurrency(data.costs.tax_breakdown.annual_gross, data.costs.tax_breakdown.currency) : "Nicht verfügbar"}</dd></div>
                </dl>
              </Section>
            </div>
            <Section title="Preisentwicklung">
              {data.costs.price_development.length > 0 ? <div className="cw-list-rows">{data.costs.price_development.map((item) => <div key={item.key}><span>{item.label}</span><strong>{item.text ?? "Nicht verfügbar"}</strong></div>)}</div> : <p className="cw-muted">Keine Preisentwicklung dokumentiert.</p>}
            </Section>
          </>
        )}

        {activeTab === "services" && (
          <>
            <Section title="Leistungsumfang" description="Was ist im Vertrag enthalten?">
              <div className="cw-service-grid">
                {scopeEntries.map(([label, value]) => (
                  <div className="cw-service-item" key={label}>
                    <span>{label}</span>
                    <strong className={value === true ? "yes" : value === false ? "no" : "unknown"}>{yesNo(value)}</strong>
                  </div>
                ))}
              </div>
              {data.scope.note_de ? <p className="cw-note">{data.scope.note_de}</p> : null}
            </Section>
            <div className="cw-two-col">
              <Section title="Enthaltene Leistungen">
                {data.scope.included_services.length > 0 ? <ul className="cw-bullet-list">{data.scope.included_services.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="cw-muted">Keine zusätzlichen enthaltenen Leistungen dokumentiert.</p>}
              </Section>
              <Section title="Ausgeschlossen">
                {data.scope.excluded_services.length > 0 ? <ul className="cw-bullet-list">{data.scope.excluded_services.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="cw-muted">Keine Ausschlüsse dokumentiert.</p>}
              </Section>
            </div>
            <Section title="Service-Level (SLA)">
              <dl className="cw-definition-grid">
                <div><dt>Reaktionszeit</dt><dd>{data.sla.response_time ?? "Nicht verfügbar"}</dd></div>
                <div><dt>Lösungszeit</dt><dd>{data.sla.resolution_time ?? "Nicht verfügbar"}</dd></div>
                <div><dt>Servicezeiten</dt><dd>{data.sla.service_hours ?? "Nicht verfügbar"}</dd></div>
                <div><dt>Notfallverfügbarkeit</dt><dd>{data.sla.emergency_availability ?? "Nicht verfügbar"}</dd></div>
                <div><dt>24/7 verfügbar</dt><dd>{yesNo(data.sla.availability_24_7)}</dd></div>
                <div><dt>Hinweise</dt><dd>{data.sla.sla_notes ?? "Keine Hinweise"}</dd></div>
              </dl>
            </Section>
          </>
        )}

        {activeTab === "equipment" && (
          <Section title="Verknüpfte Geräte" description={`${data.equipment.length} ${data.equipment.length === 1 ? "Gerät" : "Geräte"} diesem Vertrag zugeordnet`}>
            {data.equipment.length > 0 ? (
              <div className="cw-equipment-grid">
                {data.equipment.map((item) => (
                  <article className="cw-equipment-card" key={item.id}>
                    <h3>{item.device_name ?? item.system_name ?? "Gerät"}</h3>
                    <p>{[item.manufacturer, item.model].filter(Boolean).join(" · ") || "Hersteller/Modell nicht verfügbar"}</p>
                    <dl>
                      <div><dt>Seriennummer</dt><dd>{item.serial_number ?? "–"}</dd></div>
                      <div><dt>Inventarnummer</dt><dd>{item.inventory_number ?? "–"}</dd></div>
                      <div><dt>Standort</dt><dd>{item.location ?? "–"}</dd></div>
                      <div><dt>Abteilung</dt><dd>{item.department ?? "–"}</dd></div>
                      <div><dt>Serviceumfang</dt><dd>{item.service_scope ?? "–"}</dd></div>
                    </dl>
                    {item.requires_review ? <span className="cw-badge cw-badge-amber">Prüfung erforderlich</span> : null}
                  </article>
                ))}
              </div>
            ) : <p className="cw-muted">Keine Geräte diesem Vertrag zugeordnet.</p>}
          </Section>
        )}

        {activeTab === "documents" && (
          <>
            <div className="cw-kpi-grid cw-kpi-grid-four">
              <InfoCard label="Dokumente" value={data.documents.length} />
              <InfoCard label="Nachweise" value={data.evidence.length} />
              <InfoCard label="Geprüfte Fakten" value={`${data.contract_review.reviewed_count}/${data.contract_review.relevant_count}`} />
              <InfoCard label="Offene Prüfungen" value={data.contract_review.unresolved_count} />
            </div>
            <Section title="Quelldokumente">
              <div className="cw-list-rows">
                {data.documents.map((doc) => <div key={doc.document_version_id}><span>{doc.original_filename ?? "Dokument"}</span><strong>{doc.role ?? "Quelle"}</strong></div>)}
              </div>
            </Section>
            <Section title="Prüfstatus">
              <dl className="cw-definition-grid">
                <div><dt>Status</dt><dd>{data.contract_review.status_label_de}</dd></div>
                <div><dt>Manuelle Prüfung</dt><dd>{data.review.requires_manual_review ? "Erforderlich" : "Nicht erforderlich"}</dd></div>
                <div><dt>Kritische offene Fakten</dt><dd>{data.contract_review.critical_unreviewed_count}</dd></div>
                <div><dt>Datenstand</dt><dd>{data.review.warning_evaluation_as_of_date ? formatDate(data.review.warning_evaluation_as_of_date) : "Nicht verfügbar"}</dd></div>
              </dl>
            </Section>
            <details className="cw-legacy-details">
              <summary>Vollständige Detail- und Nachweisansicht öffnen</summary>
              <p className="cw-muted">Hier bleiben alle bisherigen Evidence-, PDF-, Review- und Override-Funktionen während der Workspace-Migration erhalten.</p>
              <ContractDetail data={data} orgSlug={orgSlug} onReload={onReload} />
            </details>
          </>
        )}
      </div>
    </div>
  );
}
