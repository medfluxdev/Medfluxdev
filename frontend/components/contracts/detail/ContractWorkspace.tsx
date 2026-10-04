"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type {
  CalcBasis,
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
import { removeWarningsRepresentedByTasks } from "@/lib/action-dedup";
import { archiveContract, getContractDeletionCapabilities, requestContractDeletion } from "@/lib/domain-api/contracts";
import PdfViewer from "./PdfViewer";
import EvidencePane from "./EvidencePane";
import FactReviewPanel from "./FactReviewPanel";
import OverridePanel from "./OverridePanel";
import CalculationBasisPanel, { hasCalculationBasis } from "./CalculationBasisPanel";
import ContractRegisterPanel from "./ContractRegisterPanel";
import ContractRemarksPanel from "./ContractRemarksPanel";
import Tabs from "@/components/ui/Tabs";
import { coverPdfUrl } from "@/lib/domain-api/registerGrid";

const BUSINESS_STATUS_TONE: Record<string, string> = { in_arbeit: "badge--warning", gueltig: "badge--success", gekuendigt: "badge--danger", beendet: "", geloescht: "" };
import Dialog from "@/components/ui/Dialog";
import ContractHistoryPanel from "./ContractHistoryPanel";
import ContractDeadlinesPanel from "./ContractDeadlinesPanel";
import ContractRenewalBrief from "./ContractRenewalBrief";
import ContractAttachmentsPanel from "./ContractAttachmentsPanel";
import ContractRelationsPanel from "./ContractRelationsPanel";
import ContractFinancePanel from "./ContractFinancePanel";
import { BUSINESS_STATUS_LABEL, type BusinessStatus } from "@/lib/domain-api/register";

export type WorkspaceSlot = "overview" | "register" | "deadlines" | "finance";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload?: () => void;
  /** Zusaetzliche Bereiche je Reiter (z. B. Zustaendigkeit, Entscheidungen, Abrechnung). */
  slots?: Partial<Record<WorkspaceSlot, React.ReactNode>>;
}

type TabKey = "overview" | "register" | "deadlines" | "finance" | "documents" | "relations" | "history";
// Fruehere Reiter (Links aus E-Mails, Lesezeichen) zeigen auf den neuen Ort.
const TAB_ALIASES: Record<string, TabKey> = { term: "deadlines", services: "overview", equipment: "relations", remarks: "history" };
type DocumentTab = "document" | "attachments" | "evidence" | "review" | "history";
type OriginKind = "extracted" | "reviewed" | "corrected" | "calculated" | "missing" | "system";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Übersicht" },
  { key: "register", label: "Stammdaten" },
  { key: "deadlines", label: "Fristen & Entscheidung" },
  { key: "finance", label: "Finanzen" },
  { key: "documents", label: "Dokumente & Nachweise" },
  { key: "relations", label: "Beziehungen" },
  { key: "history", label: "Verlauf" },
];

const DOCUMENT_TABS: { key: DocumentTab; label: string }[] = [
  { key: "document", label: "Dokument" },
  { key: "attachments", label: "Anlagen verwalten" },
  { key: "evidence", label: "Nachweise" },
  { key: "review", label: "Prüfung" },
  { key: "history", label: "Historie" },
];

const ORIGIN_LABEL: Record<OriginKind, string> = {
  extracted: "Extrahiert",
  reviewed: "Geprüft",
  corrected: "Korrigiert",
  calculated: "Berechnet",
  missing: "Fehlt",
  system: "Systemwert",
};

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

function moneyLike(amount: string | number | null, currency: string | null): string {
  if (amount == null || !currency) return "Nicht verfügbar";
  return formatCurrency(String(amount), currency);
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

function OriginBadge({ origin }: { origin: OriginKind }) {
  return <span className={`cw-origin-badge cw-origin-${origin}`}>{ORIGIN_LABEL[origin]}</span>;
}

function calculatedOrigin(value: unknown, basis: CalcBasis | null | undefined): OriginKind {
  if (value == null || value === "") return "missing";
  return hasCalculationBasis(basis) ? "calculated" : "system";
}

function InfoCard({ label, value, hint, origin }: { label: string; value: React.ReactNode; hint?: React.ReactNode; origin?: OriginKind }) {
  return (
    <div className="cw-info-card">
      <span className="cw-info-label">{label}</span>
      <strong className="cw-info-value">{value}</strong>
      {origin ? <OriginBadge origin={origin} /> : null}
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

function toTab(value: string | null): TabKey | null {
  if (!value) return null;
  if (TAB_ALIASES[value]) return TAB_ALIASES[value];
  return TABS.some((tab) => tab.key === value) ? (value as TabKey) : null;
}

function isDocumentTab(value: string | null): value is DocumentTab {
  return DOCUMENT_TABS.some((tab) => tab.key === value);
}

export default function ContractWorkspace({ data, orgSlug, onReload, slots = {} }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = toTab(searchParams.get("tab")) ?? "overview";
  const initialSubtab = isDocumentTab(searchParams.get("subtab")) ? searchParams.get("subtab") as DocumentTab : "document";
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [documentTab, setDocumentTab] = useState<DocumentTab>(initialSubtab);
  const [documentVersionId, setDocumentVersionId] = useState<string | null>(data.documents[0]?.document_version_id ?? null);
  const [navTarget, setNavTarget] = useState<SourceNavigationTarget | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [sourceLinkError, setSourceLinkError] = useState(false);
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const [archivePending, setArchivePending] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [canRequestDeletion, setCanRequestDeletion] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteAcknowledged, setDeleteAcknowledged] = useState(false);

  useEffect(() => {
    let active = true;
    setCanRequestDeletion(false);
    getContractDeletionCapabilities(orgSlug)
      .then((result) => { if (active) setCanRequestDeletion(result.can_delete); })
      .catch(() => { if (active) setCanRequestDeletion(false); });
    return () => { active = false; };
  }, [orgSlug]);

  async function submitDeletionRequest() {
    if (!canRequestDeletion || !deleteAcknowledged || deletePending) return;
    setDeletePending(true);
    setDeleteError(null);
    try {
      await requestContractDeletion(data.contract_id, orgSlug);
      setDeleteDialogOpen(false);
      router.push("/contracts");
      router.refresh();
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Löschanfrage fehlgeschlagen.");
    } finally {
      setDeletePending(false);
    }
  }

  const reload = onReload ?? (() => undefined);

  async function confirmArchive() {
    if (archivePending) return;
    setArchivePending(true);
    setArchiveError(null);
    try {
      await archiveContract(data.contract_id, orgSlug);
      setArchiveDialogOpen(false);
      router.push("/archiv");
      router.refresh();
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Archivierung fehlgeschlagen.");
    } finally {
      setArchivePending(false);
    }
  }
  const openTasks = useMemo(() => data.work_items.filter((item) => item.status !== "resolved"), [data.work_items]);
  const actionableWarnings = useMemo(() => removeWarningsRepresentedByTasks(
    openTasks,
    data.warnings.filter((warning) => warning.requires_action || warning.requires_review),
  ), [data.warnings, openTasks]);

  function setRoute(requested: TabKey, subtab?: DocumentTab) {
    const tab = toTab(requested) ?? "overview";
    setActiveTab(tab);
    if (subtab) setDocumentTab(subtab);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("source_evidence_id");
    params.delete("source_document");
    params.delete("source_page");
    setSourceLinkError(false);
    if (tab === "overview") params.delete("tab");
    else params.set("tab", tab);
    if (tab === "documents") params.set("subtab", subtab ?? documentTab);
    else params.delete("subtab");
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

  // Accept only an evidence ID that belongs to the currently loaded contract.
  // Never trust a deep link to supply document IDs or PDF geometry.
  const linkedEvidenceId = searchParams.get("source_evidence_id");
  useEffect(() => {
    if (!linkedEvidenceId) return;
    const match = data.evidence.find(ref => ref.evidence_id === linkedEvidenceId || ref.merged_evidence_ids?.includes(linkedEvidenceId));
    const document = data.documents.find(doc => doc.document_version_id === match?.document_version_id);
    if (!match || !document) {
      setSourceLinkError(true);
      setActiveTab("documents");
      setDocumentTab("evidence");
      return;
    }
    setSourceLinkError(false);
    setActiveEvidenceId(match.evidence_id);
    setNavTarget(evidenceTarget(match));
    if (match.document_version_id) setDocumentVersionId(match.document_version_id);
    setActiveTab("documents");
    setDocumentTab("evidence");
  }, [linkedEvidenceId, data.evidence]);

  // Sprung aus der Inhaltssuche: nur ein Dokument dieses Vertrags und eine
  // Seitenzahl werden uebernommen, nie Geometrie aus der URL.
  const linkedDocumentId = searchParams.get("source_document");
  const linkedPage = Number(searchParams.get("source_page"));
  useEffect(() => {
    if (!linkedDocumentId) return;
    const document = data.documents.find(doc => doc.document_version_id === linkedDocumentId);
    if (!document || !Number.isInteger(linkedPage) || linkedPage < 1) {
      setSourceLinkError(true);
      return;
    }
    setSourceLinkError(false);
    setDocumentVersionId(document.document_version_id);
    setNavTarget({
      document_version_id: document.document_version_id,
      page: linkedPage,
      bbox: null,
      bbox_space: "pdf_points",
      supports_exact_navigation: false,
      label: `Suchtreffer Seite ${linkedPage}`,
    });
    setActiveTab("documents");
    setDocumentTab("document");
  }, [linkedDocumentId, linkedPage, data.documents]);

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

  const effectiveEnd = data.dates.documented_end_date ?? data.dates.calculated_end_date;
  // KI-Auswertungen nur zeigen, wenn es ein analysiertes Dokument gibt (sonst nur "Fehlt"-Kacheln).
  const hasAi = data.documents.length > 0;
  const endOrigin: OriginKind = data.dates.documented_end_date ? (endEvidence ? "extracted" : "system") : calculatedOrigin(data.dates.calculated_end_date, data.dates.calculated_end_basis);
  const annualOrigin: OriginKind = data.costs.annual_recurring.amount == null ? "missing" : hasCalculationBasis(data.costs.annual_recurring_basis) ? "calculated" : annualCostEvidence ? "extracted" : "system";
  const cancellationOrigin = calculatedOrigin(data.dates.latest_cancellation_date, data.dates.latest_cancellation_basis);

  return (
    <div className="contract-workspace">
      <header className="object-header">
        <div className="object-header-main">
          <p className="object-header-eyebrow">{[data.register_number ? `Vertrag ${data.register_number}` : "Vertrag ohne Nummer", data.contract_number ? `Nr. lt. Dokument ${data.contract_number}` : null].filter(Boolean).join(" · ")}</p>
          <h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1>
          <div className="object-header-meta">
            {data.business_status ? <button type="button" className={`badge badge-button ${BUSINESS_STATUS_TONE[data.business_status as BusinessStatus] ?? ""}`} onClick={() => setRoute("register")} title="Status in den Stammdaten ändern">{BUSINESS_STATUS_LABEL[data.business_status as BusinessStatus] ?? data.business_status}</button> : null}
            {data.supplier ? <span className="object-header-partner">{data.supplier}</span> : null}
            {data.review.requires_manual_review ? <button type="button" className="badge badge--warning badge-button" onClick={() => setRoute("documents", "review")}>KI-Werte prüfen</button> : null}
            {data.risk_level === "high" || data.risk_level === "medium" ? <span className={`badge ${data.risk_level === "high" ? "badge--danger" : "badge--warning"}`}>Risiko {riskLabel(data.risk_level).toLowerCase()}</span> : null}
          </div>
        </div>
        <dl className="object-header-facts">
          <div><dt>Vertragsende</dt><dd>{formatDate(data.register_facts?.contract_end ?? effectiveEnd) ?? "–"}</dd></div>
          <div><dt>Kündbar bis</dt><dd>{formatDate(data.register_facts?.cancel_by ?? data.dates.latest_cancellation_date) ?? "–"}</dd></div>
          <div><dt>Jährliche Kosten</dt><dd className="num">{data.register_facts?.annual_cost ? moneyLike(data.register_facts.annual_cost.amount, data.register_facts.annual_cost.currency) : money(data.costs.annual_recurring)}</dd></div>
        </dl>
        <div className="object-header-actions">
          <a className="btn" href={coverPdfUrl(orgSlug, data.contract_id)} target="_blank" rel="noopener noreferrer">Deckblatt (PDF)</a>
          <button type="button" className="btn" onClick={() => window.dispatchEvent(new Event("medflux:assistant-toggle"))}>KI-Assistent</button>
          <details className="shell-menu">
            <summary className="btn btn-icon" aria-label="Weitere Aktionen">⋯</summary>
            <div className="shell-menu-panel">
              <button type="button" className="btn btn-ghost" onClick={() => { setArchiveError(null); setArchiveDialogOpen(true); }}>Archivieren</button>
              {canRequestDeletion ? <button type="button" className="btn btn-ghost" onClick={() => { setDeleteAcknowledged(false); setDeleteError(null); setDeleteDialogOpen(true); }}>Löschung beantragen</button> : null}
            </div>
          </details>
        </div>
      </header>
      <Dialog
        open={deleteDialogOpen}
        title="Vertragslöschung beantragen?"
        description="Dieser Schritt markiert den Vertrag als zur Löschung vorgemerkt. Er löscht keine Daten endgültig. Eine separate Bestätigung ist erforderlich."
        onClose={() => { if (!deletePending) setDeleteDialogOpen(false); }}
        actions={<>
          <button type="button" className="btn" disabled={deletePending} onClick={() => setDeleteDialogOpen(false)}>Abbrechen</button>
          <button type="button" className="btn btn-danger" disabled={deletePending || !deleteAcknowledged} onClick={submitDeletionRequest}>{deletePending ? "Wird gesendet…" : "Löschung beantragen"}</button>
        </>}
      >
        <label className="rg-check"><input type="checkbox" checked={deleteAcknowledged} disabled={deletePending} onChange={(event) => setDeleteAcknowledged(event.target.checked)} /> Ich verstehe, dass der Vertrag danach aus aktiven Ansichten verschwindet.</label>
        {deleteError && <p role="alert" className="field-error">{deleteError}</p>}
      </Dialog>
      <Dialog
        open={archiveDialogOpen}
        title="Vertrag archivieren?"
        description="Der Vertrag bleibt erhalten und kann über das Archiv wiederhergestellt werden."
        onClose={() => { if (!archivePending) setArchiveDialogOpen(false); }}
        actions={<>
          <button type="button" className="btn" disabled={archivePending} onClick={() => setArchiveDialogOpen(false)}>Abbrechen</button>
          <button type="button" className="btn btn-primary" disabled={archivePending} onClick={confirmArchive}>{archivePending ? "Wird archiviert…" : "Archivierung bestätigen"}</button>
        </>}
      >
        {archiveError && <p role="alert" className="field-error">{archiveError}</p>}
      </Dialog>

      <div className="object-tabs"><Tabs label="Vertragsbereiche" idPrefix="contract-tab" items={TABS} active={activeTab} onChange={(key) => setRoute(key)} /></div>

      <div className="cw-content" id="contract-tab-panel" role="tabpanel" aria-labelledby={`contract-tab-${activeTab}`} tabIndex={0}>
        {activeTab === "overview" && <>
          <div className="cw-kpi-grid"><InfoCard label="Status" value={statusLabel(data.status)} origin="system" /><InfoCard label="Vertragsende" value={effectiveEnd ? formatDate(effectiveEnd) : "Nicht verfügbar"} origin={endOrigin} hint={<SourceButton evidence={data.dates.documented_end_date ? endEvidence : null} />} /><InfoCard label="Jährliche Kosten" value={money(data.costs.annual_recurring)} origin={annualOrigin} hint={<SourceButton evidence={annualCostEvidence} />} /><InfoCard label="Kündigungsfrist" value={data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"} origin={cancellationOrigin} hint={<SourceButton evidence={cancellationEvidence} />} /><InfoCard label="Risiko" value={riskLabel(data.risk_level)} origin="system" /></div>
          {(openTasks.length > 0 || actionableWarnings.length > 0) && <Section title="Handlungsbedarf" description="Offene Aufgaben und relevante Warnungen"><div className="cw-task-list cw-action-list">{openTasks.slice(0, 6).map((item) => <button type="button" className="cw-task cw-task-button cw-action-card" key={item.work_item_id} onClick={() => item.requires_review ? setRoute("documents", "review") : setRoute("overview")}><span className={`cw-priority cw-priority-${item.severity}`}>{severityLabel(item.severity)}</span><div><strong>{item.title_de}</strong>{item.why_de ? <p>{item.why_de}</p> : null}</div><span>{item.target_date ? formatDate(item.target_date) : item.requires_review ? "Prüfung erforderlich" : "Keine Frist"}</span></button>)}{actionableWarnings.slice(0, 4).map((warning, index) => <button type="button" className="cw-task cw-task-button cw-action-card" key={`${warning.warning_type}-${index}`} onClick={() => warning.requires_review ? setRoute("documents", "review") : setRoute("deadlines")}><span className={`cw-priority cw-priority-${warning.severity}`}>{severityLabel(warning.severity)}</span><div><strong>{warning.title_de}</strong></div><span>{warning.target_date ? formatDate(warning.target_date) : "Prüfung erforderlich"}</span></button>)}</div></Section>}
          <div className="cw-two-col"><Section title="Leistungsüberblick" description="Kurzer Überblick über den Vertragsumfang"><div className="cw-chip-list">{SCOPE_FIELDS.map(([key, label, prop]) => [label, scopeState(key, data.scope[prop])] as const).filter(([, state]) => state.label === "Enthalten").slice(0, 8).map(([label]) => <span className="cw-chip" key={label}>{label}</span>)}{SCOPE_FIELDS.every(([key, , prop]) => scopeState(key, data.scope[prop]).label !== "Enthalten") ? <span className="cw-muted">Keine eindeutig bestätigten Leistungen.</span> : null}</div></Section><Section title="Daten & Prüfung" description="Qualität und Nachvollziehbarkeit"><div className="cw-mini-stats"><button type="button" onClick={() => setRoute("documents", "evidence")}><strong>{data.evidence.length}</strong><span>Nachweise</span></button><button type="button" onClick={() => setRoute("documents", "document")}><strong>{data.documents.length}</strong><span>Dokumente</span></button><button type="button" onClick={() => setRoute("documents", "review")}><strong>{data.contract_review.unresolved_count}</strong><span>Offene Prüfungen</span></button></div></Section></div>
        </>}

        {activeTab === "register" && <><ContractRegisterPanel contractId={data.contract_id} orgSlug={orgSlug} onChanged={reload} />{slots.register}</>}

        {activeTab === "history" && <div className="stack-4"><ContractHistoryPanel contractId={data.contract_id} orgSlug={orgSlug} /><ContractRemarksPanel contractId={data.contract_id} orgSlug={orgSlug} /></div>}

        {activeTab === "deadlines" && <><ContractRenewalBrief contractId={data.contract_id} orgSlug={orgSlug} /><ContractDeadlinesPanel contractId={data.contract_id} orgSlug={orgSlug} /></>}

        {activeTab === "relations" && <ContractRelationsPanel contractId={data.contract_id} orgSlug={orgSlug} />}

        {activeTab === "deadlines" && hasAi && <>
          <h2 className="cw-subheading">Aus dem Vertragsdokument (KI-Analyse)</h2>
          <div className="cw-kpi-grid cw-kpi-grid-four"><InfoCard label="Beginn" value={data.dates.start_date ? formatDate(data.dates.start_date) : "Nicht verfügbar"} origin={data.dates.start_date ? (startEvidence ? "extracted" : "system") : "missing"} hint={<SourceButton evidence={startEvidence} />} /><InfoCard label="Dokumentiertes Ende" value={data.dates.documented_end_date ? formatDate(data.dates.documented_end_date) : "Nicht verfügbar"} origin={data.dates.documented_end_date ? (endEvidence ? "extracted" : "system") : "missing"} hint={<SourceButton evidence={endEvidence} />} /><InfoCard label="Berechnetes Ende" value={data.dates.calculated_end_date ? formatDate(data.dates.calculated_end_date) : "Nicht verfügbar"} origin={calculatedOrigin(data.dates.calculated_end_date, data.dates.calculated_end_basis)} /><InfoCard label="Restlaufzeit" value={data.dates.days_until_end != null ? `${data.dates.days_until_end} Tage` : "Nicht verfügbar"} origin={data.dates.days_until_end != null ? "calculated" : "missing"} /></div>
          <Section title="Kündigung & Verlängerung"><dl className="cw-definition-grid"><div><dt>Spätester Kündigungstermin <SourceButton evidence={cancellationEvidence} /></dt><dd><span className="cw-value-origin">{data.dates.latest_cancellation_date ? formatDate(data.dates.latest_cancellation_date) : "Nicht verfügbar"}<OriginBadge origin={cancellationOrigin} /></span></dd></div><div><dt>Automatische Verlängerung <SourceButton evidence={renewalEvidence} /></dt><dd>{yesNo(data.dates.automatic_renewal)}</dd></div><div><dt>Nächste Verlängerung</dt><dd><span className="cw-value-origin">{data.dates.next_renewal_date ? formatDate(data.dates.next_renewal_date) : "Nicht verfügbar"}<OriginBadge origin={calculatedOrigin(data.dates.next_renewal_date, data.dates.next_renewal_basis)} /></span></dd></div><div><dt>Mindestlaufzeit <SourceButton evidence={minimumDurationEvidence ?? durationEvidence} /></dt><dd>{data.dates.minimum_duration_months != null ? `${data.dates.minimum_duration_months} Monate` : "Nicht verfügbar"}</dd></div><div><dt>Zahlungsbeginn <SourceButton evidence={paymentStartEvidence} /></dt><dd>{data.dates.payment_start_rule ?? "Nicht verfügbar"}</dd></div><div><dt>Aktueller Status</dt><dd>{statusLabel(data.dates.current_status)}</dd></div></dl></Section>
          {(hasCalculationBasis(data.dates.calculated_end_basis) || hasCalculationBasis(data.dates.latest_cancellation_basis) || hasCalculationBasis(data.dates.next_renewal_basis)) && <Section title="Berechnungsgrundlage" description="Rechenweg der Termine"><div className="cw-calc-grid"><CalculationBasisPanel title="Berechnetes Vertragsende" basis={data.dates.calculated_end_basis} /><CalculationBasisPanel title="Spätester Kündigungstermin" basis={data.dates.latest_cancellation_basis} /><CalculationBasisPanel title="Nächste Verlängerung" basis={data.dates.next_renewal_basis} /></div></Section>}
        </>}

        {activeTab === "finance" && <>
          <ContractFinancePanel contractId={data.contract_id} orgSlug={orgSlug} />
          {hasAi && <>
          <h2 className="cw-subheading">KI-Analyse der Vertragskosten</h2>
          <div className="cw-kpi-grid cw-kpi-grid-four"><InfoCard label="Jährlich wiederkehrend" value={money(data.costs.annual_recurring)} origin={annualOrigin} hint={<SourceButton evidence={annualCostEvidence} />} /><InfoCard label="Monatlich wiederkehrend" value={money(data.costs.monthly_recurring)} origin={data.costs.monthly_recurring.amount == null ? "missing" : monthlyCostEvidence ? "extracted" : "system"} hint={<SourceButton evidence={monthlyCostEvidence} />} /><InfoCard label="Steuersatz" value={data.costs.tax_rate_percent != null ? `${data.costs.tax_rate_percent} %` : "Nicht verfügbar"} origin={data.costs.tax_rate_percent != null ? (taxRateEvidence ? "extracted" : "system") : "missing"} hint={<SourceButton evidence={taxRateEvidence} />} /><InfoCard label="Bezugsperiode" value={data.costs.source_period ?? "Nicht verfügbar"} origin={data.costs.source_period ? "system" : "missing"} /></div>
          {hasCalculationBasis(data.costs.annual_recurring_basis) ? <Section title="Kostenberechnung" description="Nachvollziehbare Grundlage des jährlichen Betrags"><CalculationBasisPanel title="Jährlich wiederkehrende Kosten" basis={data.costs.annual_recurring_basis} /></Section> : null}
          {data.costs.availability && (data.costs.annual_recurring.amount == null || data.costs.availability.manual_input_required) ? <Section title="Warum Kosten noch nicht vollständig berechnet sind" description={data.costs.availability.summary_de}><div className="cw-finance-availability">{data.costs.availability.explanation_de ? <p>{data.costs.availability.explanation_de}</p> : null}{data.costs.availability.found_facts.length > 0 ? <div><strong>Gefundene Angaben</strong><ul>{data.costs.availability.found_facts.map((fact) => <li key={fact.key}>{fact.label_de}: {fact.value}{fact.period_hint ? ` · ${fact.period_hint}` : ""}</li>)}</ul></div> : null}{data.costs.availability.missing_inputs.length > 0 ? <div><strong>Noch benötigte Angaben</strong><ul>{data.costs.availability.missing_inputs.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}</div></Section> : null}
          <Section title="Abrechnung & Steuer"><dl className="cw-definition-grid"><div><dt>Steuerbasis <SourceButton evidence={taxBasisEvidence} /></dt><dd>{data.costs.tax_basis ?? "Nicht verfügbar"}</dd></div><div><dt>Währung</dt><dd>{data.costs.annual_recurring.currency ?? data.costs.monthly_recurring.currency ?? "Nicht verfügbar"}</dd></div><div><dt>Währungskonflikt</dt><dd>{data.costs.currency_conflict ? "Ja – prüfen" : "Nein"}</dd></div></dl></Section>
          {(data.costs.scheduled_prices ?? []).length > 0 && <Section title="Preisplan (Staffel)" description="Belegte Preisstufen je Vertragsjahr – nie annualisiert"><div className="cw-finance-schedule">{data.costs.scheduled_prices.map((row) => <div className="cw-finance-schedule-row" key={`${row.period_index ?? "x"}-${row.period_label ?? ""}`}><span>{row.period_index ? `${row.period_index}. Vertragsjahr` : row.period_label ?? "Vertragsjahr"}</span><strong>{moneyLike(row.amount, row.currency)}</strong></div>)}</div></Section>}
          {(data.costs.variable_charges ?? []).length > 0 && <Section title="Bedingte Kosten (nicht im Fixwert enthalten)" description="Verbrauchs- oder einsatzabhängige Positionen, getrennt vom wiederkehrenden Jahresbetrag"><div className="cw-finance-variable">{data.costs.variable_charges.map((item, idx) => <dl className="cw-definition-grid" key={`${item.label}-${idx}`}><div><dt>Position</dt><dd>{item.label}</dd></div><div><dt>Betrag</dt><dd>{moneyLike(item.amount, item.currency)}{item.unit_label_de ? ` ${item.unit_label_de}` : ""}</dd></div>{item.condition ? <div><dt>Bedingung</dt><dd>{item.condition}</dd></div> : null}<div><dt>Hinweis</dt><dd className="cw-muted">{item.note_de ?? "Wird nicht zum Fixwert addiert."}</dd></div></dl>)}</div></Section>}
          </>}
        </>}

        {activeTab === "overview" && hasAi && <><Section title="Leistungsumfang" description="Enthaltene, ausgeschlossene und ungeklärte Leistungen"><div className="cw-service-grid">{SCOPE_FIELDS.map(([key, label, prop]) => { const state = scopeState(key, data.scope[prop]); return <div className="cw-service-row" key={key}><span>{label}</span><strong className={`cw-service-state cw-service-${state.tone}`}>{state.label}</strong><SourceButton evidence={state.evidence} /></div>; })}</div></Section><Section title="SLA"><dl className="cw-definition-grid"><div><dt>Reaktionszeit</dt><dd>{data.sla.response_time ?? "Nicht verfügbar"}</dd></div><div><dt>Lösungszeit</dt><dd>{data.sla.resolution_time ?? "Nicht verfügbar"}</dd></div><div><dt>Servicezeiten</dt><dd>{data.sla.service_hours ?? "Nicht verfügbar"}</dd></div><div><dt>Notfallverfügbarkeit</dt><dd>{data.sla.emergency_availability ?? yesNo(data.sla.availability_24_7)}</dd></div></dl></Section></>}

        {activeTab === "relations" && <Section title="Geräte" description="Dem Vertrag zugeordnete Geräte">{data.equipment.length === 0 ? <p className="cw-muted">Keine Geräte zugeordnet.</p> : <div className="cw-equipment-list">{data.equipment.map((item) => <article key={item.id ?? item.equipment_id ?? item.serial_number ?? item.device_name} className="cw-equipment-card"><strong>{item.device_name || item.system_name || item.model || item.equipment_type || item.equipment_category || "Gerät"}</strong><span>{[item.manufacturer, item.model].filter(Boolean).join(" · ") || "Hersteller/Modell nicht verfügbar"}</span><span>{item.serial_number ? `Seriennr. ${item.serial_number}` : "Seriennummer nicht verfügbar"}</span>{item.department ? <span>{item.department}</span> : null}</article>)}</div>}</Section>}

        {activeTab === "overview" && slots.overview}
        {activeTab === "deadlines" && slots.deadlines}
        {activeTab === "finance" && slots.finance}
        {activeTab === "documents" && <>
          <div className="cw-document-summary"><InfoCard label="Dokumente" value={String(data.documents.length)} /><InfoCard label="Nachweise" value={String(data.evidence.length)} /><InfoCard label="Prüfstatus" value={data.contract_review.status_label_de} hint={`${data.contract_review.reviewed_count} von ${data.contract_review.relevant_count} geprüft`} /><InfoCard label="Offene Prüfungen" value={String(data.contract_review.unresolved_count)} /></div>
          <nav className="cw-subtabs" aria-label="Dokumente und Prüfung">{DOCUMENT_TABS.map((tab) => <button key={tab.key} type="button" className={documentTab === tab.key ? "active" : ""} onClick={() => setRoute("documents", tab.key)}>{tab.label}</button>)}</nav>
          {documentTab === "document" && <div className="cw-document-layout"><aside className="cw-document-sidebar"><h2>Quelldokumente</h2>{data.documents.length === 0 ? <p className="cw-muted">Keine Dokumente vorhanden.</p> : data.documents.map((doc) => <button key={doc.document_version_id} type="button" className={documentVersionId === doc.document_version_id ? "active" : ""} onClick={() => { setDocumentVersionId(doc.document_version_id); setNavTarget(null); setActiveEvidenceId(null); }}>{doc.original_filename ?? "Dokument"}<small>{doc.role ?? "Quelle"}</small></button>)}<button type="button" className="cw-evidence-shortcut" onClick={() => setRoute("documents", "evidence")}>{data.evidence.length} Nachweise anzeigen</button></aside><div className="cw-pdf-shell"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} /></div></div>}
          {documentTab === "attachments" && <ContractAttachmentsPanel contractId={data.contract_id} orgSlug={orgSlug} onAnalyzed={reload} />}
          {documentTab === "evidence" && <Section title="Nachweise" description="Quellenangaben aus den Vertragsdokumenten">{sourceLinkError && <p role="alert">Der verlinkte Nachweis ist in diesem Vertrag nicht verfügbar. Bitte wählen Sie einen verfügbaren Nachweis.</p>}<div className="cw-evidence-layout"><div className="cw-evidence-pane"><EvidencePane evidence={data.evidence} activeEvidenceId={activeEvidenceId} onNavigate={(ref) => openEvidence(ref, "evidence")} /></div><div className="cw-evidence-preview"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} /></div></div></Section>}
          {documentTab === "review" && <div className="cw-integrated-panel"><FactReviewPanel data={data} orgSlug={orgSlug} onReload={reload} onNavigate={(ref) => openEvidence(ref, "document")} /></div>}
          {documentTab === "history" && <div className="cw-integrated-panel"><OverridePanel data={data} orgSlug={orgSlug} onReload={reload} /></div>}
        </>}
      </div>
    </div>
  );
}
