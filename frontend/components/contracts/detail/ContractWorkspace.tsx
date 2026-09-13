"use client";

import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type {
  ContractDetailResponse,
  EvidenceRef,
  MoneyValue,
  SourceNavigationTarget,
} from "@/lib/contract-detail-types";
import {
  RISK_LABEL_DETAIL,
  SEVERITY_LABEL,
  STATUS_LABEL_DETAIL,
} from "@/lib/contract-detail-types";
import { formatCurrency, formatDate } from "@/lib/format";
import PdfViewer from "./PdfViewer";
import EvidencePane from "./EvidencePane";
import FactReviewPanel from "./FactReviewPanel";
import OverridePanel from "./OverridePanel";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload?: () => void;
}

type TabKey = "overview" | "term" | "finance" | "services" | "equipment" | "documents";
type DocumentTab = "document" | "evidence" | "review" | "history";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Übersicht" },
  { key: "term", label: "Laufzeit & Kündigung" },
  { key: "finance", label: "Finanzen" },
  { key: "services", label: "Leistungen & SLA" },
  { key: "equipment", label: "Geräte" },
  { key: "documents", label: "Dokumente & Prüfung" },
];

const DOCUMENT_TABS: { key: DocumentTab; label: string }[] = [
  { key: "document", label: "Dokument" },
  { key: "evidence", label: "Nachweise" },
  { key: "review", label: "Prüfung" },
  { key: "history", label: "Historie" },
];

const SCOPE_FIELDS = [
  ["maintenance", "Wartung", "maintenance"],
  ["inspection", "Inspektion", "inspection"],
  ["repair", "Reparatur", "repair"],
  ["calibration", "Kalibrierung", "calibration"],
  ["software_updates", "Software-Updates", "software_updates"],
  ["remote_support", "Remote-Support", "remote_support"],
  ["technical_support", "Technischer Support", "technical_support"],
  ["spare_parts_included", "Ersatzteile", "spare_parts_included"],
  ["consumables_included", "Verbrauchsmaterial", "consumables_included"],
  ["emergency_service", "Notdienst", "emergency_service"],
] as const;

function money(value: MoneyValue): string {
  if (value.amount == null || !value.currency) return "Nicht verfügbar";
  return formatCurrency(String(value.amount), value.currency);
}

function yesNo(value: boolean | null): string {
  if (value == null) return "Unbekannt";
  return value ? "Ja" : "Nein";
}

function statusLabel(value: string | null): string {
  if (!value) return "Unbekannt";
  return STATUS_LABEL_DETAIL[value] ?? value;
}

function riskLabel(value: string | null): string {
  if (!value) return "Unbekannt";
  return RISK_LABEL_DETAIL[value] ?? value;
}

function severityLabel(value: string): string {
  return SEVERITY_LABEL[value] ?? value;
}

function evidenceTarget(ref: EvidenceRef): SourceNavigationTarget {
  return {
    document_version_id: ref.document_version_id,
    page: ref.page,
    bbox: ref.bbox,
    bbox_space: ref.bbox_space,
    supports_exact_navigation: ref.supports_exact_navigation,
    label: ref.snippet || ref.field_ref || "Quelle",
    field_ref: ref.field_ref,
    evidence_id: ref.evidence_id,
  };
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

function isTab(value: string | null): value is TabKey {
  return TABS.some((tab) => tab.key === value);
}

function isDocumentTab(value: string | null): value is DocumentTab {
  return DOCUMENT_TABS.some((tab) => tab.key === value);
}

export default function ContractWorkspace({ data, orgSlug, onReload }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = isTab(searchParams.get("tab")) ? searchParams.get("tab") as TabKey : "overview";
  const initialSubtab = isDocumentTab(searchParams.get("subtab")) ? searchParams.get("subtab") as DocumentTab : "document";
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [documentTab, setDocumentTab] = useState<DocumentTab>(initialSubtab);
  const [documentVersionId, setDocumentVersionId] = useState<string | null>(data.documents[0]?.document_version_id ?? null);
  const [navTarget, setNavTarget] = useState<SourceNavigationTarget | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);

  const reload = onReload ?? (() => undefined);
  const openTasks = useMemo(() => data.work_items.filter((item) => item.status !== "resolved"), [data.work_items]);
  const actionableWarnings = useMemo(() => data.warnings.filter((warning) => warning.requires_action || warning.requires_review), [data.warnings]);

  function setRoute(tab: TabKey, subtab?: DocumentTab) {
    setActiveTab(tab);
    if (subtab) setDocumentTab(subtab);
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "overview") params.delete("tab");
    else params.set("tab", tab);
    if (tab === "documents") {
      params.set("subtab", subtab ?? documentTab);
    } else {
      params.delete("subtab");
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function evidenceById(id: string | null | undefined): EvidenceRef | null {
    if (!id) return null;
    return data.evidence.find((ref) => ref.evidence_id === id || ref.field_ref === id) ?? null;
  }

  function findExactEvidence(...fields: (string | null | undefined)[]): EvidenceRef | null {
    const wanted = fields.filter(Boolean) as string[];
    for (const field of wanted) {
      const exact = data.evidence.find((ref) => ref.field_ref === field);
      if (exact) return exact;
    }
    for (const field of wanted) {
      const recovered = data.evidence.find((ref) => (ref.evidence_id ?? "").startsWith("recovered:") && ref.field_ref?.startsWith(`${field}.`));
      if (recovered) return recovered;
    }
    for (const field of wanted) {
      const prefixed = data.evidence.find((ref) => ref.field_ref?.startsWith(`${field}.`));
      if (prefixed) return prefixed;
    }
    return null;
  }

  function openEvidence(ref: EvidenceRef, targetTab: DocumentTab = "document") {
    setActiveEvidenceId(ref.evidence_id);
    setNavTarget(evidenceTarget(ref));
    if (ref.document_version_id) setDocumentVersionId(ref.document_version_id);
    setRoute("documents", targetTab);
  }

  function SourceButton({ evidence }: { evidence: EvidenceRef | null }) {
    if (!evidence) return null;
    return <button type="button" className="cw-source-button" onClick={() => openEvidence(evidence)}>Quelle</button>;
  }

  const startEvidence = evidenceById(data.dates.start_date_evidence) ?? findExactEvidence("dates.start_date", "start_date");
  const endEvidence = evidenceById(data.dates.documented_end_evidence) ?? findExactEvidence("dates.documented_end_date", "dates.calculated_end_date", "termination.end_date");
  const durationEvidence = evidenceById(data.dates.duration_evidence) ?? findExactEvidence("dates.duration_years", "duration");
  const renewalEvidence = evidenceById(data.dates.auto_renewal_evidence) ?? findExactEvidence("dates.automatic_renewal", "termination.automatic_renewal");
  const paymentStartEvidence = evidenceById(data.dates.payment_start_evidence) ?? findExactEvidence("dates.payment_start_rule", "payment.start");
  const minimumDurationEvidence = evidenceById(data.dates.minimum_duration_evidence) ?? findExactEvidence("dates.minimum_duration_months", "duration.minimum");
  const cancellationEvidence = findExactEvidence("dates.latest_cancellation_date", "termination.latest_cancellation_date", "termination.notice_period");
  const annualCostEvidence = findExactEvidence("costs.annual_recurring", "cost.annual_recurring", "payment.annual_cost", "annual_cost");
  const monthlyCostEvidence = findExactEvidence("costs.monthly_recurring", "cost.monthly_recurring", "payment.monthly_cost", "monthly_cost");
  const taxRateEvidence = evidenceById(data.costs.tax_breakdown?.evidence_field_refs?.vat_rate) ?? findExactEvidence("costs.tax_rate_percent", "cost.tax_rate_percent", "vat_rate");
  const taxBasisEvidence = findExactEvidence("costs.tax_basis", "cost.tax_basis");

  function scopeState(key: string, legacy: boolean | null) {
    const state = data.scope.scope_status?.[key];
    if (state) {
      if (state.status === "included") return { label: "Enthalten", tone: "yes", evidence: evidenceById(state.evidence_ref) ?? findExactEvidence(`services.${key}`, `scope.${key}`) };
      if (state.status === "excluded") return { label: "Ausgeschlossen", tone: "no", evidence: evidenceById(state.evidence_ref) ?? findExactEvidence(`services.${key}`, `scope.${key}`) };
      return { label: "Zu prüfen", tone: "unknown", evidence: evidenceById(state.evidence_ref) ?? findExactEvidence(`services.${key}`, `scope.${key}`) };
    }
    return { label: legacy === true ? "Enthalten" : legacy === false ? "Ausgeschlossen" : "Zu prüfen", tone: legacy === true ? "yes" : legacy === false ? "no" : "unknown", evidence: findExactEvidence(`services.${key}`, `scope.${key}`) };
  }

  return (
    <div className="contract-workspace">
      <header className="cw-header">
        <div><div className="cw-breadcrumb">Verträge / {data.contract_number ?? data.contract_id}</div><h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1><p>{[data.contract_number ? `Nr. ${data.contract_number}` : null, data.supplier].filter(Boolean).join(" · ")}</p></div>
        <div className="cw-header-badges"><span className="cw-badge cw-badge-green">{statusLabel(data.status)}</span><span className={`cw-badge ${data.risk_level === "high" ? "cw-badge-red" : ""}`}>Risiko: {riskLabel(data.risk_level)}</span>{data.review.requires_manual_review ? <button type="button" className="cw-badge cw-badge-amber cw-badge-button" onClick={() => setRoute("documents", "review")}>Manuelle Prüfung</button> : null}</div>
      </header>

      <nav className="cw-tabs" aria-label="Vertragsbereiche">{TABS.map((tab) => <button key={tab.key} type="button" className={activeTab === tab.key ? "active" : ""} onClick={() => setRoute(tab.key)}>{tab.label}</button>)}</nav>

      <div className="cw-content">
        {activeTab === "overview" && <>
          <div className="cw-kpi-grid"><InfoCard label="Status" value={statusLabel(data.status)} /><InfoCard label="Vertragsende" value={data.dates.documented_end_date ? formatDate(data.dates.documented_end_date) : data.dates.calculated_end_date ? formatDate(data.dates.calculated_end_date) : "Nicht verfügbar"} hint={<SourceButton evidence={endEvidence} />} /><InfoCard label="Jährliche Kosten" value={money(data.costs.annual_recurring)} hint={<SourceButton evidence={annualCostEvidence} />} /><InfoCard label="Kündigungsfrist" value={data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"} hint={<SourceButton evidence={cancellationEvidence} />} /><InfoCard label="Risiko" value={riskLabel(data.risk_level)} /></div>
          {(openTasks.length > 0 || actionableWarnings.length > 0) && <Section title="Handlungsbedarf" description="Offene Aufgaben und relevante Warnungen"><div className="cw-task-list">{openTasks.slice(0, 6).map((item) => <button type="button" className="cw-task cw-task-button" key={item.work_item_id} onClick={() => item.requires_review ? setRoute("documents", "review") : setRoute("overview")}><span className={`cw-priority cw-priority-${item.severity}`}>{severityLabel(item.severity)}</span><div><strong>{item.title_de}</strong>{item.why_de ? <p>{item.why_de}</p> : null}</div><span>{item.target_date ? formatDate(item.target_date) : item.requires_review ? "Prüfung erforderlich" : "Keine Frist"}</span></button>)}{actionableWarnings.slice(0, 4).map((warning, index) => <button type="button" className="cw-task cw-task-button" key={`${warning.warning_type}-${index}`} onClick={() => warning.requires_review ? setRoute("documents", "review") : setRoute("term")}><span className={`cw-priority cw-priority-${warning.severity}`}>{severityLabel(warning.severity)}</span><div><strong>{warning.title_de}</strong></div><span>{warning.target_date ? formatDate(warning.target_date) : "Prüfung erforderlich"}</span></button>)}</div></Section>}
          <div className="cw-two-col"><Section title="Leistungsüberblick" description="Kurzer Überblick über den Vertragsumfang"><div className="cw-chip-list">{SCOPE_FIELDS.map(([key, label, prop]) => [label, scopeState(key, data.scope[prop])] as const).filter(([, state]) => state.label === "Enthalten").slice(0, 8).map(([label]) => <span className="cw-chip" key={label}>{label}</span>)}{SCOPE_FIELDS.every(([key, , prop]) => scopeState(key, data.scope[prop]).label !== "Enthalten") ? <span className="cw-muted">Keine eindeutig bestätigten Leistungen.</span> : null}</div></Section><Section title="Daten & Prüfung" description="Qualität und Nachvollziehbarkeit"><div className="cw-mini-stats"><button type="button" onClick={() => setRoute("documents", "evidence")}><strong>{data.evidence.length}</strong><span>Nachweise</span></button><button type="button" onClick={() => setRoute("documents", "document")}><strong>{data.documents.length}</strong><span>Dokumente</span></button><button type="button" onClick={() => setRoute("documents", "review")}><strong>{data.contract_review.unresolved_count}</strong><span>Offene Prüfungen</span></button></div></Section></div>
        </>}

        {activeTab === "term" && <><div className="cw-kpi-grid cw-kpi-grid-four"><InfoCard label="Beginn" value={data.dates.start_date ? formatDate(data.dates.start_date) : "Nicht verfügbar"} hint={<SourceButton evidence={startEvidence} />} /><InfoCard label="Dokumentiertes Ende" value={data.dates.documented_end_date ? formatDate(data.dates.documented_end_date) : "Nicht verfügbar"} hint={<SourceButton evidence={endEvidence} />} /><InfoCard label="Berechnetes Ende" value={data.dates.calculated_end_date ? formatDate(data.dates.calculated_end_date) : "Nicht verfügbar"} /><InfoCard label="Restlaufzeit" value={data.dates.days_until_end != null ? `${data.dates.days_until_end} Tage` : "Nicht verfügbar"} /></div><Section title="Kündigung & Verlängerung"><dl className="cw-definition-grid"><div><dt>Spätester Kündigungstermin <SourceButton evidence={cancellationEvidence} /></dt><dd>{data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"}</dd></div><div><dt>Automatische Verlängerung <SourceButton evidence={renewalEvidence} /></dt><dd>{yesNo(data.dates.automatic_renewal)}</dd></div><div><dt>Nächste Verlängerung</dt><dd>{data.dates.next_renewal_date ? formatDate(data.dates.next_renewal_date) : "Nicht verfügbar"}</dd></div><div><dt>Mindestlaufzeit <SourceButton evidence={minimumDurationEvidence ?? durationEvidence} /></dt><dd>{data.dates.minimum_duration_months != null ? `${data.dates.minimum_duration_months} Monate` : "Nicht verfügbar"}</dd></div><div><dt>Zahlungsbeginn <SourceButton evidence={paymentStartEvidence} /></dt><dd>{data.dates.payment_start_rule ?? "Nicht verfügbar"}</dd></div><div><dt>Aktueller Status</dt><dd>{statusLabel(data.dates.current_status)}</dd></div></dl></Section>{(data.dates.calculated_end_basis?.explanation || data.dates.latest_cancellation_basis?.explanation) && <Section title="Berechnungsgrundlage" description="Begründungen direkt bei Laufzeit und Kündigung"><div className="cw-note-list">{data.dates.calculated_end_basis?.explanation ? <p>{data.dates.calculated_end_basis.explanation}</p> : null}{data.dates.latest_cancellation_basis?.explanation ? <p>{data.dates.latest_cancellation_basis.explanation}</p> : null}</div></Section>}</>}

        {activeTab === "finance" && <><div className="cw-kpi-grid cw-kpi-grid-four"><InfoCard label="Jährlich wiederkehrend" value={money(data.costs.annual_recurring)} hint={<SourceButton evidence={annualCostEvidence} />} /><InfoCard label="Monatlich wiederkehrend" value={money(data.costs.monthly_recurring)} hint={<SourceButton evidence={monthlyCostEvidence} />} /><InfoCard label="Steuersatz" value={data.costs.tax_rate_percent != null ? `${data.costs.tax_rate_percent} %` : "Nicht verfügbar"} hint={<SourceButton evidence={taxRateEvidence} />} /><InfoCard label="Bezugsperiode" value={data.costs.source_period ?? "Nicht verfügbar"} /></div>{data.costs.availability && (data.costs.annual_recurring.amount == null || data.costs.availability.manual_input_required) ? <Section title="Warum Kosten noch nicht vollständig berechnet sind" description={data.costs.availability.summary_de}><div className="cw-finance-availability">{data.costs.availability.explanation_de ? <p>{data.costs.availability.explanation_de}</p> : null}{data.costs.availability.found_facts.length > 0 ? <div><strong>Gefundene Angaben</strong><ul>{data.costs.availability.found_facts.map((fact) => <li key={fact.key}>{fact.label_de}: {fact.value}{fact.period_hint ? ` · ${fact.period_hint}` : ""}</li>)}</ul></div> : null}{data.costs.availability.missing_inputs.length > 0 ? <div><strong>Noch benötigte Angaben</strong><ul>{data.costs.availability.missing_inputs.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}</div></Section> : null}<Section title="Abrechnung & Steuer"><dl className="cw-definition-grid"><div><dt>Steuerbasis <SourceButton evidence={taxBasisEvidence} /></dt><dd>{data.costs.tax_basis ?? "Nicht verfügbar"}</dd></div><div><dt>Währung</dt><dd>{data.costs.annual_recurring.currency ?? data.costs.monthly_recurring.currency ?? "Nicht verfügbar"}</dd></div><div><dt>Währungskonflikt</dt><dd>{data.costs.currency_conflict ? "Ja – prüfen" : "Nein"}</dd></div></dl></Section></>}

        {activeTab === "services" && <><Section title="Leistungsumfang" description="Enthaltene, ausgeschlossene und ungeklärte Leistungen"><div className="cw-service-grid">{SCOPE_FIELDS.map(([key, label, prop]) => { const state = scopeState(key, data.scope[prop]); return <div className="cw-service-row" key={key}><span>{label}</span><strong className={`cw-service-state cw-service-${state.tone}`}>{state.label}</strong><SourceButton evidence={state.evidence} /></div>; })}</div></Section><Section title="SLA"><dl className="cw-definition-grid"><div><dt>Reaktionszeit</dt><dd>{data.sla.response_time ?? "Nicht verfügbar"}</dd></div><div><dt>Lösungszeit</dt><dd>{data.sla.resolution_time ?? "Nicht verfügbar"}</dd></div><div><dt>Servicezeiten</dt><dd>{data.sla.service_hours ?? "Nicht verfügbar"}</dd></div><div><dt>Notfallverfügbarkeit</dt><dd>{data.sla.emergency_availability ?? yesNo(data.sla.availability_24_7)}</dd></div></dl></Section></>}

        {activeTab === "equipment" && <Section title="Geräte" description="Dem Vertrag zugeordnete Geräte">{data.equipment.length === 0 ? <p className="cw-muted">Keine Geräte zugeordnet.</p> : <div className="cw-equipment-list">{data.equipment.map((item) => <article key={item.id ?? item.equipment_id ?? item.serial_number ?? item.device_name} className="cw-equipment-card"><strong>{item.device_name ?? item.equipment_type ?? "Gerät"}</strong><span>{[item.manufacturer, item.model].filter(Boolean).join(" · ") || "Hersteller/Modell nicht verfügbar"}</span><span>{item.serial_number ? `Seriennr. ${item.serial_number}` : "Seriennummer nicht verfügbar"}</span>{item.department ? <span>{item.department}</span> : null}</article>)}</div>}</Section>}

        {activeTab === "documents" && <>
          <div className="cw-document-summary"><InfoCard label="Dokumente" value={String(data.documents.length)} /><InfoCard label="Nachweise" value={String(data.evidence.length)} /><InfoCard label="Prüfstatus" value={data.contract_review.status_label_de} hint={`${data.contract_review.reviewed_count} von ${data.contract_review.relevant_count} geprüft`} /><InfoCard label="Offene Prüfungen" value={String(data.contract_review.unresolved_count)} /></div>
          <nav className="cw-subtabs" aria-label="Dokumente und Prüfung">{DOCUMENT_TABS.map((tab) => <button key={tab.key} type="button" className={documentTab === tab.key ? "active" : ""} onClick={() => setRoute("documents", tab.key)}>{tab.label}</button>)}</nav>
          {documentTab === "document" && <div className="cw-document-layout"><aside className="cw-document-sidebar"><h2>Quelldokumente</h2>{data.documents.length === 0 ? <p className="cw-muted">Keine Dokumente vorhanden.</p> : data.documents.map((doc) => <button key={doc.document_version_id} type="button" className={documentVersionId === doc.document_version_id ? "active" : ""} onClick={() => { setDocumentVersionId(doc.document_version_id); setNavTarget(null); setActiveEvidenceId(null); }}>{doc.original_filename ?? "Dokument"}<small>{doc.role ?? "Quelle"}</small></button>)}<button type="button" className="cw-evidence-shortcut" onClick={() => setRoute("documents", "evidence")}>{data.evidence.length} Nachweise anzeigen</button></aside><div className="cw-pdf-shell"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} /></div></div>}
          {documentTab === "evidence" && <Section title="Nachweise" description="Quellenangaben aus den Vertragsdokumenten"><div className="cw-evidence-layout"><div className="cw-evidence-pane"><EvidencePane evidence={data.evidence} activeEvidenceId={activeEvidenceId} onNavigate={(ref) => openEvidence(ref, "evidence")} /></div><div className="cw-evidence-preview"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} /></div></div></Section>}
          {documentTab === "review" && <div className="cw-integrated-panel"><FactReviewPanel data={data} orgSlug={orgSlug} onReload={reload} onNavigate={(ref) => openEvidence(ref, "document")} /></div>}
          {documentTab === "history" && <div className="cw-integrated-panel"><OverridePanel data={data} orgSlug={orgSlug} onReload={reload} /></div>}
        </>}
      </div>
    </div>
  );
}
