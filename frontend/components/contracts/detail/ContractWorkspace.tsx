"use client";

import { revealBox } from "@/lib/box-collapse";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
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
import { PdfViewer } from "./lazy";
import EvidencePane from "./EvidencePane";
import FactReviewPanel from "./FactReviewPanel";
import OverridePanel from "./OverridePanel";
import CalculationBasisPanel, { hasCalculationBasis } from "./CalculationBasisPanel";
import ContractRegisterPanel from "./ContractRegisterPanel";
import ContractRemarksPanel from "./ContractRemarksPanel";
import Tabs from "@/components/ui/Tabs";
import Signal from "@/components/ui/Signal";
import TagChip, { TagIcon } from "@/components/ui/TagChip";
import ReviewQueueNav from "./ReviewQueueNav";
import { coverPdfUrl } from "@/lib/domain-api/registerGrid";

import Dialog from "@/components/ui/Dialog";
import ContractHistoryPanel from "./ContractHistoryPanel";
import ContractDeadlinesPanel from "./ContractDeadlinesPanel";
import ContractRenewalBrief from "./ContractRenewalBrief";
import ContractAttachmentsPanel from "./ContractAttachmentsPanel";
import ContractRelationsPanel from "./ContractRelationsPanel";
import ContractFinancePanel from "./ContractFinancePanel";
import { BUSINESS_STATUS_LABEL, BUSINESS_STATUS_TONE, type BusinessStatus } from "@/lib/domain-api/register";
import StatusBadge from "@/components/ui/StatusBadge";
import { FIELD_PARAM, FINANCE_ENTRIES_TARGET, SECTION_PARAM, contractHref, documentSearchHref, MISSING_SEARCH, fixLabel, sectionAnchor, warningTarget, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import { useContractGaps } from "./ContractGaps";
import { setPageCommands } from "@/lib/page-commands";
import ReextractionPanel, { ReextractionBanner, fieldSearchMap, useReextraction } from "./Reextraction";
import SourceCapture from "./SourceCapture";
import AiReviewButton from "./AiReviewButton";
import RiskButton from "./RiskButton";
import ValueOriginBadge from "./ValueOriginBadge";
import ContractTermBar from "./ContractTermBar";
import { SECTION_LABELS, sectionVisible } from "@/lib/contract-sections";
import OpenPoints, { buildOpenPoints } from "./OpenPoints";
import ContractDeviceTypesPanel from "./ContractDeviceTypesPanel";
import CapturedSources from "./CapturedSources";
import { SignalIcon } from "@/components/ui/Signal";
import ContractAssignmentCard from "./ContractAssignmentCard";
import { useAuth } from "@/components/auth/AuthProvider";

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

// Schlüssel bleiben (Links, Lesezeichen); die Beschriftung folgt dem Plan (U11).
const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Übersicht" },
  { key: "register", label: "Vertragsdaten" },
  { key: "deadlines", label: "Fristen & Aufgaben" },
  { key: "finance", label: "Finanzen" },
  { key: "documents", label: "Dokumente" },
  { key: "relations", label: "Verknüpfungen" },
  { key: "history", label: "Verlauf" },
];

const DOCUMENT_TABS: { key: DocumentTab; label: string }[] = [
  { key: "document", label: "Dokument" },
  { key: "evidence", label: "Nachweise" },
  { key: "review", label: "Prüfung" },
  { key: "attachments", label: "Anlagen" },
  { key: "history", label: "Korrekturen" },
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
  return <ValueOriginBadge kind={origin} />;
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
  const [showAllSections, setShowAllSections] = useState(false);
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
  const reextraction = useReextraction(data.contract_id, orgSlug);
  const { role, account } = useAuth();
  const canEditData = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  // „Angabe aus dem Text übernehmen“: Stelle auf der angezeigten PDF-Seite markieren.
  const [captureOpen, setCaptureOpen] = useState(false);
  const [aiOpenCount, setAiOpenCount] = useState(0);
  const [pdfPage, setPdfPage] = useState(1);
  const onPdfPage = useCallback((page: number) => setPdfPage(page), []);
  // „Fehlende Angaben im Dokument suchen“: nur mit Recht, ohne laufende Auswertung und wenn etwas fehlt.
  const reextractionBusy = reextraction.state?.run?.status === "queued" || reextraction.state?.run?.status === "running";
  const searchMissingHref = reextraction.state?.can_start && !reextractionBusy && (reextraction.state?.missing.length ?? 0) > 0
    ? documentSearchHref(data.contract_id, MISSING_SEARCH)
    : null;
  // „Was fehlt noch?“: Karte in der Übersicht und – auf jedem Reiter – Befehle in Strg+K.
  const gaps = useContractGaps({
    contractId: data.contract_id,
    orgSlug,
    hasAnnualCost: Boolean(data.register_facts?.annual_cost),
    reviewPending: Boolean(data.review?.requires_manual_review),
    documentCount: data.documents.length,
    version: data,
  });
  useEffect(() => {
    // Gleiche Reihenfolge wie „Offene Punkte“: fristrelevant zuerst, dann KI-Prüfung, dann der Rest.
    const order = (gap: { key: string; blocksDeadline?: boolean }) => gap.blocksDeadline ? 0 : gap.key === "review" ? 1 : 2;
    const commands = [...(gaps ?? [])].sort((x, y) => order(x) - order(y)).map((gap) => ({ id: `gap:${gap.key}`, label: gap.command, hint: gap.reason, href: contractHref(data.contract_id, gap.target) }));
    if (searchMissingHref) commands.push({ id: "reextract:missing", label: "Fehlende Angaben im Dokument suchen", hint: "Die KI liest das Vertragsdokument erneut", href: searchMissingHref });
    setPageCommands(commands);
    return () => setPageCommands([]);
  }, [data.contract_id, gaps, searchMissingHref]);
  // Links auf derselben Seite (z. B. „Kosten erfassen“) ändern nur die Adresse: Reiter danach richten.
  const urlTab = toTab(searchParams.get("tab")) ?? "overview";
  const urlSubtab = searchParams.get("subtab");
  const linkedSection = searchParams.get(SECTION_PARAM);
  useEffect(() => {
    setActiveTab(urlTab);
    if (isDocumentTab(urlSubtab)) setDocumentTab(urlSubtab as DocumentTab);
  }, [urlTab, urlSubtab]);

  // ?abschnitt=…: zum Abschnitt scrollen, sobald er gerendert ist (Reiter laden teils nach).
  useEffect(() => {
    if (!linkedSection) return;
    const anchor = sectionAnchor(linkedSection);
    let tries = 0;
    let timer = 0;
    const seek = () => {
      const element = document.getElementById(anchor);
      if (element) {
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        revealBox(element);
        element.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
        return;
      }
      if (tries++ < 30) timer = window.setTimeout(seek, 100);
    };
    seek();
    return () => window.clearTimeout(timer);
  }, [activeTab, linkedSection]);

  useEffect(() => {
    let active = true;
    setCanRequestDeletion(false);
    getContractDeletionCapabilities(orgSlug)
      .then((result) => { if (active) setCanRequestDeletion(result.can_request ?? result.can_delete); })
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
      router.push("/register");
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
      router.push("/register?ansicht=archive");
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
    // Ein Reiterwechsel von Hand beendet einen Sprung zu Feld oder Abschnitt.
    params.delete(FIELD_PARAM);
    params.delete(SECTION_PARAM);
    setSourceLinkError(false);
    if (tab === "overview") params.delete("tab");
    else params.set("tab", tab);
    if (tab === "documents") params.set("subtab", subtab ?? documentTab);
    else params.delete("subtab");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  // „Direkt zur Stelle“ innerhalb der Vertragsakte: Reiter, Abschnitt oder Feld über die Adresse ansteuern.
  const mainDocumentId = data.documents[0]?.document_version_id ?? null;
  function openCapture() {
    setCaptureOpen(true);
    setRoute("documents", "document");
    window.setTimeout(() => document.getElementById("source-capture-heading")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  // Fundstelle eines von Hand aus dem Dokument übernommenen Werts zeigen.
  function showSource(source: { document_version_id: string; page: number; quote: string }) {
    setRoute("documents", "document");
    setDocumentVersionId(source.document_version_id);
    setNavTarget({ document_version_id: source.document_version_id, page: source.page, bbox: null, bbox_space: "pdf_points", supports_exact_navigation: false, label: source.quote });
  }

  function showDocumentPage(page: number) {
    if (!mainDocumentId) return;
    setDocumentVersionId(mainDocumentId);
    setNavTarget({ document_version_id: mainDocumentId, page, bbox: null, bbox_space: "pdf_points", supports_exact_navigation: false, label: `Fundstelle Seite ${page}` });
    window.setTimeout(() => document.querySelector(".cw-pdf-shell")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function openTarget(target: FixTarget) {
    router.replace(contractHref(data.contract_id, target), { scroll: false });
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
  const contractNumberEvidence = findExactEvidence("identity.contract_number", "contract_number");
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
  // Gepflegter Wert (Finanzposten) vor KI-Wert; der KI-Wert wird nie als gepflegt ausgegeben.
  const maintainedAnnual = data.register_facts?.annual_cost ?? null;
  // Gepflegter Vertragsbeginn vor dem Wert aus dem Dokument.
  const contractStart = data.register_facts?.contract_start ?? data.dates.start_date ?? null;
  const headerEnd = data.register_facts?.contract_end ?? effectiveEnd ?? null;
  const headerCancelBy = data.register_facts?.cancel_by ?? data.dates.latest_cancellation_date ?? null;
  // Feste Laufzeit endet ohne Kündigung: kein „Kündbar bis“, nichts fehlt. Unbefristet: kein Ende.
  const termModel = data.register_facts?.term_model ?? null;
  const fixedTerm = termModel === "fixed_term";
  const openEnded = termModel === "perpetual";
  const aiAnnual = data.costs.annual_recurring.amount != null;
  const cancellationOrigin = calculatedOrigin(data.dates.latest_cancellation_date, data.dates.latest_cancellation_basis);

  // Leistungsumfang: Zustand je Leistung und Zusammenfassung (nur mit analysiertem Dokument).
  const scopeRows = SCOPE_FIELDS.map(([key, label, prop]) => ({ key, label, state: scopeState(key, data.scope[prop]) }));
  const scopeCounts = {
    included: scopeRows.filter((row) => row.state.tone === "yes").length,
    excluded: scopeRows.filter((row) => row.state.tone === "no").length,
    unknown: scopeRows.filter((row) => row.state.tone === "unknown").length,
  };
  // Abschnitte je Vertragstyp: nicht vorgesehene, leere Abschnitte ausblenden (lib/contract-sections.ts).
  const sections = showAllSections ? null : data.sections ?? null;
  const scopeHasData = scopeCounts.included + scopeCounts.excluded > 0;
  const slaHasData = Boolean(data.sla.response_time || data.sla.resolution_time || data.sla.service_hours || data.sla.emergency_availability || data.sla.availability_24_7 != null);
  // Der Vertragstyp entscheidet. Nur von einer Person gepflegte Angaben (Gerätearten, Wartungsdaten) halten
  // einen Abschnitt sichtbar; von der KI gelesene Angaben stehen im Hinweis und sind über „Trotzdem anzeigen“ erreichbar.
  const showScope = hasAi && sectionVisible("scope", sections, false);
  const showSla = hasAi && sectionVisible("sla", sections, false);
  const showEquipment = sectionVisible("equipment", sections, (data.assignment?.device_types?.length ?? 0) > 0);
  const hiddenSections = data.sections ? ([
    ["scope", showScope || !hasAi, scopeHasData],
    ["sla", showSla || !hasAi, slaHasData],
    ["equipment", showEquipment, data.equipment.length > 0],
  ] as const).filter(([, shown]) => !shown).map(([key, , found]) => `${SECTION_LABELS[key]}${found ? " (mit Angaben aus dem Dokument)" : ""}`) : [];
  const slaMissing = showSla ? [data.sla.response_time ? null : "Reaktionszeit", data.sla.resolution_time ? null : "Lösungszeit"].filter((item): item is string => Boolean(item)) : [];
  // Erst mit geladenen Lücken berechnen, sonst stünde kurz ein unvollständiges Bild da.
  const openPoints = gaps === null ? null : buildOpenPoints({
    gaps,
    tasks: openTasks,
    warnings: actionableWarnings,
    scopeToCheck: showScope ? scopeCounts.unknown : 0,
    scopeTotal: scopeRows.length,
    slaMissing,
    cancelByUnknown: !headerCancelBy && !fixedTerm,
  });
  // Reiter zeigen, wo Arbeit wartet (Symbol mit Namen für Screenreader).
  const deadlineCritical = (openPoints ?? []).some((point) => point.tone === "critical" && (point.target?.tab === "deadlines" || point.target?.tab === "register"));
  const tabItems = TABS.map((tab) => ({
    ...tab,
    badge: tab.key === "deadlines" && deadlineCritical
      ? <span className="tab-signal tab-signal--critical" role="img" aria-label="Kritischer offener Punkt"><SignalIcon tone="critical" /></span>
      : tab.key === "register" && aiOpenCount > 0
        ? <span className="tab-signal tab-signal--ai" role="img" aria-label={`${aiOpenCount} KI-Werte nicht bestätigt`}><SignalIcon tone="ai" /></span>
        : tab.key === "documents" && data.documents.length > 0
          ? <span className="tab-count" aria-hidden="true">{data.documents.length}</span>
          : undefined,
  }));

  return (
    <div className="contract-workspace">
      <nav className="object-crumbs" aria-label="Brotkrümelnavigation"><Link href="/register">Vertragsliste</Link><span aria-hidden="true">›</span><span aria-current="page">{data.contract_title ?? data.contract_number ?? "Vertrag"}</span></nav>
      <header className="object-header">
        <div className="object-header-main">
          <p className="object-header-eyebrow">{data.register_number
            ? <button type="button" className="header-link" onClick={() => openTarget({ tab: "register", section: "identity" })} title="In den Vertragsdaten ansehen">Vertrag <span className="mono">{data.register_number}</span></button>
            : "Vertrag ohne Nummer"}{data.contract_number ? <> · {contractNumberEvidence
              ? <button type="button" className="header-link" onClick={() => openEvidence(contractNumberEvidence)} title="Fundstelle im Dokument zeigen">Nr. lt. Dokument <span className="mono">{data.contract_number}</span></button>
              : <>Nr. lt. Dokument <span className="mono">{data.contract_number}</span></>}</> : null}</p>
          <h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1>
          <div className="object-header-meta object-header-who">
            {/* Hauptangaben mit eigener Kennfarbe, Symbol und Wort; jede führt zur Stelle, an der sie gepflegt wird. */}
            {data.assignment?.contract_type
              ? <TagChip kind="type" as="button" srLabel="Vertragstyp" onClick={() => openTarget({ tab: "register", section: "ownership" })} title="Vertragstyp – in der Organisationszuordnung ändern">{data.assignment.contract_type}</TagChip>
              : canEditData ? <button type="button" className="tag-chip tag-chip--missing" onClick={() => openTarget({ tab: "register", section: "ownership" })}><TagIcon kind="type" />Vertragstyp festlegen</button> : null}
            {data.partner
              ? <TagChip kind="partner" as="link" srLabel="Vertragspartner" href={`/stammdaten/vertragspartner?id=${encodeURIComponent(data.partner.id)}`} title="Vertragspartner öffnen und bearbeiten">{data.partner.name}</TagChip>
              : data.supplier
                ? <TagChip kind="partner" as="button" className="tag-chip--unlinked" onClick={() => openTarget({ tab: "register", field: "partner_id" })} title="Noch keinem Vertragspartner aus den Stammdaten zugeordnet">{data.supplier}<span className="partner-chip-hint">zuordnen</span></TagChip>
                : null}
            {data.assignment?.responsible_department ? <TagChip kind="department" as="button" srLabel="Verantwortliche Abteilung" onClick={() => openTarget({ tab: "register", section: "ownership" })} title="Verantwortliche Abteilung – in der Organisationszuordnung ändern">{data.assignment.responsible_department}</TagChip> : null}
            {data.assignment?.cost_center ? <TagChip kind="cost" as="button" onClick={() => openTarget({ tab: "register", section: "ownership" })} title="Kostenstelle – in der Organisationszuordnung ändern">Kostenstelle <span className="mono">{data.assignment.cost_center.code}</span> · {data.assignment.cost_center.name}</TagChip> : null}
          </div>
          <div className="object-header-meta object-header-signals">
            {data.business_status ? <button type="button" className="badge-button status-button" onClick={() => setRoute("register")} title="Status in den Vertragsdaten ändern"><StatusBadge label={BUSINESS_STATUS_LABEL[data.business_status as BusinessStatus] ?? data.business_status} tone={BUSINESS_STATUS_TONE[data.business_status as BusinessStatus] ?? "neutral"} /></button> : null}
            {openPoints?.length ? <Link className="open-points-link" href={contractHref(data.contract_id, { tab: "overview", section: "offene-punkte" })} onClick={(event) => { event.preventDefault(); openTarget({ tab: "overview", section: "offene-punkte" }); }}><Signal tone={openPoints[0].tone === "critical" ? "critical" : "warning"}>Offene Punkte · {openPoints.length}</Signal></Link> : null}
            <AiReviewButton contractId={data.contract_id} orgSlug={orgSlug} reviewPending={data.review.requires_manual_review} canEdit={canEditData} version={data} onCount={setAiOpenCount} />
            <RiskButton contractId={data.contract_id} orgSlug={orgSlug} risk={data.risk ?? (data.risk_level ? { computed: data.risk_level, effective: data.risk_level, override: null, confirmed: null } : null)} warnings={data.warnings} canEdit={canEditData} onChanged={reload} />
          </div>
        </div>
        <dl className={`object-header-facts${fixedTerm ? " object-header-facts--three" : ""}`}>
          <div><dt>Vertragsbeginn</dt><dd>{contractStart ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (data.register_facts?.contract_start || !startEvidence ? openTarget({ tab: "register", field: "term_start_date" }) : openEvidence(startEvidence))} title={data.register_facts?.contract_start || !startEvidence ? "In den Vertragsdaten ansehen" : "Fundstelle im Dokument zeigen"}>{formatDate(contractStart)}</button><ValueOriginBadge kind={data.register_facts?.contract_start ? "system" : "extracted"} /></span> : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", field: "term_start_date" })} aria-label="Vertragsbeginn erfassen">Beginn erfassen</button></span>}</dd></div>
          <div><dt>Vertragsende</dt><dd>{headerEnd ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (data.register_facts?.contract_end || !endEvidence ? openTarget({ tab: "register", section: "term" }) : openEvidence(endEvidence))} title={data.register_facts?.contract_end || !endEvidence ? "Berechnung in den Vertragsdaten (Laufzeit) ansehen" : "Fundstelle im Dokument zeigen"}>{formatDate(headerEnd)}</button><ValueOriginBadge kind={data.register_facts?.contract_end ? "calculated" : endOrigin} /><SourceButton evidence={data.dates.documented_end_date && !data.register_facts?.contract_end ? endEvidence : null} /></span> : (openEnded ? <span className="fact-value">unbefristet</span> : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", section: "term" })}>Laufzeit &amp; Kündigung ergänzen</button></span>)}</dd></div>
          {fixedTerm ? null : <div className={headerCancelBy ? undefined : "fact--alert"}><dt>Kündbar bis</dt><dd>{headerCancelBy ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => setRoute("deadlines")} title="Fristen ansehen">{formatDate(headerCancelBy)}</button><ValueOriginBadge kind="calculated" /><SourceButton evidence={data.register_facts?.cancel_by ? null : cancellationEvidence} /></span> : <span className="fact-value"><Signal tone="critical" size="sm">Nicht berechenbar</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", field: "notice_period_value" })}>Kündigungsfrist erfassen</button></span>}</dd></div>}
          <div><dt>Jährliche Kosten</dt><dd className="num">{maintainedAnnual
            ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => openTarget(FINANCE_ENTRIES_TARGET)} title="Finanzposten ansehen">{moneyLike(maintainedAnnual.amount, maintainedAnnual.currency)}</button><ValueOriginBadge kind="system" detail="Aus den gepflegten Finanzposten" /></span>
            : aiAnnual
              ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (annualCostEvidence ? openEvidence(annualCostEvidence) : setRoute("finance"))} title={annualCostEvidence ? "Fundstelle im Dokument zeigen" : "Finanzen ansehen"}>{money(data.costs.annual_recurring)}</button><ValueOriginBadge kind="extracted" detail="Aus der KI-Analyse, noch nicht in die Finanzen übernommen" /><SourceButton evidence={annualCostEvidence} /><button type="button" className="rg-link" onClick={() => setRoute("finance")}>In Finanzen übernehmen</button></span>
              : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget(FINANCE_ENTRIES_TARGET)} aria-label="Jährliche Kosten erfassen">Kosten erfassen</button></span>}</dd></div>
        </dl>
        <div className="object-header-term"><ContractTermBar start={contractStart} end={headerEnd} cancelBy={headerCancelBy} fixedTerm={fixedTerm} openEnded={openEnded} onOpen={() => setRoute("deadlines")} /></div>
        <div className="object-header-actions">
          <a className="btn" href={coverPdfUrl(orgSlug, data.contract_id)} target="_blank" rel="noopener noreferrer"><svg className="btn-symbol" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6" /></svg>Deckblatt (PDF)</a>
          <button type="button" className="btn" onClick={() => window.dispatchEvent(new Event("medflux:assistant-toggle"))}><svg className="btn-symbol" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></svg>KI-Assistent</button>
          <details className="shell-menu">
            <summary className="btn btn-icon" aria-label="Weitere Aktionen">⋯</summary>
            <div className="shell-menu-panel">
              <button type="button" className="btn btn-ghost" onClick={() => { setArchiveError(null); setArchiveDialogOpen(true); }}>Archivieren</button>
              {canRequestDeletion ? <button type="button" className="btn btn-ghost" onClick={() => { setDeleteAcknowledged(false); setDeleteError(null); setDeleteDialogOpen(true); }}>Löschung beantragen</button> : null}
            </div>
          </details>
        </div>
      </header>
      <ReextractionBanner state={reextraction.state} onOpen={() => openTarget({ tab: "documents", subtab: "document", section: "reextraction" })} />
      <Dialog
        open={deleteDialogOpen}
        title="Vertragslöschung beantragen?"
        description="Der Vertrag wird zur Löschung vorgemerkt und aus den Listen genommen. Die Administration bestätigt oder lehnt ab (Verwaltung → Vertragslöschung). Auch ein gelöschter Vertrag bleibt wiederherstellbar; nichts wird endgültig vernichtet."
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

      <div className="object-tabs"><Tabs label="Vertragsbereiche" idPrefix="contract-tab" items={tabItems} active={activeTab} onChange={(key) => setRoute(key)} /></div>

      <div className="cw-content" id="contract-tab-panel" role="tabpanel" aria-labelledby={`contract-tab-${activeTab}`} tabIndex={0}>
        {activeTab === "overview" && <div className="cw-overview">
          <div className="cw-overview-main">
            <OpenPoints contractId={data.contract_id} points={openPoints} searchHref={searchMissingHref} onOpen={openTarget} />
            {showScope ? <section className="cw-section" aria-labelledby="leistungsumfang-heading">
              <div className="cw-section-head"><div><h2 id="leistungsumfang-heading">Leistungsumfang</h2><p>Was der Vertrag abdeckt – laut Dokument</p></div></div>
              <div className="scope-summary">
                <Signal tone={scopeCounts.included > 0 ? "done" : "neutral"}>{scopeCounts.included} enthalten</Signal>
                <Signal tone="neutral">{scopeCounts.excluded} ausgeschlossen</Signal>
                <Signal tone={scopeCounts.unknown > 0 ? "warning" : "neutral"}>{scopeCounts.unknown} zu prüfen</Signal>
              </div>
              <ul className="scope-list">{scopeRows.map((row) => <li key={row.key}>
                <span className="scope-name">{row.label}</span>
                <Signal tone={row.state.tone === "yes" ? "done" : row.state.tone === "no" ? "neutral" : "warning"} size="sm">{row.state.label}</Signal>
                <span className="scope-source"><SourceButton evidence={row.state.evidence} /></span>
              </li>)}</ul>
            </section> : null}
            {showSla ? <section className="cw-section" aria-labelledby="sla-heading">
              <div className="cw-section-head"><div><h2 id="sla-heading">SLA</h2><p>Zugesagte Reaktions- und Servicezeiten</p></div></div>
              <dl className="sla-grid">
                <div><dt>Reaktionszeit</dt><dd>{data.sla.response_time ?? <Signal tone="warning" size="sm">Nicht im Vertrag gefunden</Signal>}</dd></div>
                <div><dt>Lösungszeit</dt><dd>{data.sla.resolution_time ?? <Signal tone="warning" size="sm">Nicht im Vertrag gefunden</Signal>}</dd></div>
                <div><dt>Servicezeiten</dt><dd>{data.sla.service_hours ?? <Signal tone="neutral" size="sm">Nicht angegeben</Signal>}</dd></div>
                <div><dt>Notfallverfügbarkeit</dt><dd>{data.sla.emergency_availability ?? (data.sla.availability_24_7 == null ? <Signal tone="neutral" size="sm">Unbekannt</Signal> : yesNo(data.sla.availability_24_7))}</dd></div>
              </dl>
            </section> : null}
            {hiddenSections.length ? <p className="sections-hidden-note">Für {data.sections!.type_label} ausgeblendet: {hiddenSections.join(", ")}. <button type="button" className="rg-link" onClick={() => setShowAllSections(true)}>Trotzdem anzeigen</button></p> : null}
            {showAllSections && data.sections ? <p className="sections-hidden-note">Alle Abschnitte werden angezeigt. <button type="button" className="rg-link" onClick={() => setShowAllSections(false)}>Nur passende Abschnitte</button></p> : null}
            {hasAi && !data.sections ? <p className="sections-hidden-note">Mit einem Vertragstyp zeigt die Akte nur die passenden Abschnitte. {canEditData ? <button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", section: "ownership" })}>Vertragstyp festlegen</button> : null}</p> : null}
            {slots.overview}
          </div>
          <aside className="cw-overview-aside" aria-label="Nachschlagen">
            <ContractAssignmentCard contractId={data.contract_id} assignment={data.assignment} canEdit={canEditData} />
            <section className="cw-section" aria-labelledby="data-proof-heading">
              <div className="cw-section-head"><div><h2 id="data-proof-heading">Daten &amp; Nachweise</h2></div></div>
              <ul className="side-nav-list">
                <li><button type="button" onClick={() => setRoute("documents", "evidence")}>Nachweise<b>{data.evidence.length}</b><span aria-hidden="true">›</span></button></li>
                <li><button type="button" onClick={() => setRoute("documents", "document")}>Dokumente<b>{data.documents.length}</b><span aria-hidden="true">›</span></button></li>
                <li><button type="button" onClick={() => setRoute("documents", "review")}>Ungeprüfte Angaben<b>{data.contract_review.unresolved_count}</b><span aria-hidden="true">›</span></button></li>
              </ul>
            </section>
            <section className="cw-section" aria-labelledby="origin-legend-heading">
              <div className="cw-section-head"><div><h2 id="origin-legend-heading">Herkunft der Werte</h2></div></div>
              <dl className="side-dl side-dl--legend">
                <div><dt><ValueOriginBadge kind="system" /></dt><dd>Im System erfasst oder bestätigt</dd></div>
                <div><dt><ValueOriginBadge kind="calculated" /></dt><dd>Aus anderen Werten abgeleitet</dd></div>
                <div><dt><ValueOriginBadge kind="extracted" /></dt><dd>Aus dem Dokument gelesen, noch nicht bestätigt</dd></div>
              </dl>
            </section>
          </aside>
        </div>}

        {activeTab === "register" && <><ContractRegisterPanel
          contractId={data.contract_id}
          orgSlug={orgSlug}
          onChanged={reload}
          searchableKeys={reextraction.state?.can_start ? new Set(fieldSearchMap(reextraction.state).keys()) : undefined}
          onSearchInDocument={(key) => router.replace(documentSearchHref(data.contract_id, key), { scroll: false })}
          onShowSource={showSource}
          hiddenSections={!showAllSections && data.sections && !data.sections.maintenance ? new Set(["maintenance"]) : undefined}
          afterStatus={slots.register}
        /></>}

        {activeTab === "history" && <div className="stack-4"><ContractHistoryPanel contractId={data.contract_id} orgSlug={orgSlug} /><ContractRemarksPanel contractId={data.contract_id} orgSlug={orgSlug} /></div>}

        {activeTab === "deadlines" && <><ContractRenewalBrief contractId={data.contract_id} orgSlug={orgSlug} /><ContractDeadlinesPanel contractId={data.contract_id} orgSlug={orgSlug} />
          <Section title="Aufgaben zu diesem Vertrag" description="Dieselben Aufgaben wie unter Fristen & Aufgaben → Aufgaben, hier nur für diesen Vertrag.">
            {openTasks.length === 0 ? <p className="cw-muted">Keine offenen Aufgaben.</p> : <ul className="cw-task-list">{openTasks.map((item) => <li key={item.work_item_id} className="cw-task"><Signal tone={item.requires_review ? "ai" : item.severity === "critical" ? "critical" : item.severity === "high" || item.severity === "medium" ? "warning" : "neutral"}>{item.requires_review ? "KI-Prüfung" : severityLabel(item.severity)}</Signal><div><strong>{item.title_de}</strong>{item.why_de ? <p>{item.why_de}</p> : null}</div><span>{item.target_date ? formatDate(item.target_date) : "Keine Frist"}</span>{(() => { const target = workItemTarget(item.item_type, item.requires_review); return target && target.tab !== "deadlines" ? <button type="button" className="btn btn-sm" onClick={() => openTarget(target)}>{item.requires_review ? "Prüfen" : fixLabel(target)}</button> : null; })()}</li>)}</ul>}
          </Section></>}

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
          {data.costs.availability && (data.costs.annual_recurring.amount == null || data.costs.availability.manual_input_required) ? <Section title="Warum Kosten noch nicht vollständig berechnet sind" description={data.costs.availability.summary_de}><div className="cw-finance-availability">{data.costs.availability.explanation_de ? <p>{data.costs.availability.explanation_de}</p> : null}{data.costs.availability.found_facts.length > 0 ? <div><strong>Gefundene Angaben</strong><ul>{data.costs.availability.found_facts.map((fact) => <li key={fact.key}>{fact.label_de}: {fact.value}{fact.period_hint ? ` · ${fact.period_hint}` : ""}</li>)}</ul></div> : null}{data.costs.availability.missing_inputs.length > 0 ? <div><strong>Noch benötigte Angaben</strong><ul>{data.costs.availability.missing_inputs.map((item) => <li key={item}>{item}</li>)}</ul><button type="button" className="rg-link" onClick={() => openTarget(FINANCE_ENTRIES_TARGET)}>Finanzeintrag erfassen</button></div> : null}</div></Section> : null}
          <Section title="Abrechnung & Steuer"><dl className="cw-definition-grid"><div><dt>Steuerbasis <SourceButton evidence={taxBasisEvidence} /></dt><dd>{data.costs.tax_basis ?? "Nicht verfügbar"}</dd></div><div><dt>Währung</dt><dd>{data.costs.annual_recurring.currency ?? data.costs.monthly_recurring.currency ?? "Nicht verfügbar"}</dd></div><div><dt>Währungskonflikt</dt><dd>{data.costs.currency_conflict ? "Ja – prüfen" : "Nein"}</dd></div></dl></Section>
          {(data.costs.scheduled_prices ?? []).length > 0 && <Section title="Preisplan (Staffel)" description="Belegte Preisstufen je Vertragsjahr – nie annualisiert"><div className="cw-finance-schedule">{data.costs.scheduled_prices.map((row) => <div className="cw-finance-schedule-row" key={`${row.period_index ?? "x"}-${row.period_label ?? ""}`}><span>{row.period_index ? `${row.period_index}. Vertragsjahr` : row.period_label ?? "Vertragsjahr"}</span><strong>{moneyLike(row.amount, row.currency)}</strong></div>)}</div></Section>}
          {(data.costs.variable_charges ?? []).length > 0 && <Section title="Bedingte Kosten (nicht im Fixwert enthalten)" description="Verbrauchs- oder einsatzabhängige Positionen, getrennt vom wiederkehrenden Jahresbetrag"><div className="cw-finance-variable">{data.costs.variable_charges.map((item, idx) => <dl className="cw-definition-grid" key={`${item.label}-${idx}`}><div><dt>Position</dt><dd>{item.label}</dd></div><div><dt>Betrag</dt><dd>{moneyLike(item.amount, item.currency)}{item.unit_label_de ? ` ${item.unit_label_de}` : ""}</dd></div>{item.condition ? <div><dt>Bedingung</dt><dd>{item.condition}</dd></div> : null}<div><dt>Hinweis</dt><dd className="cw-muted">{item.note_de ?? "Wird nicht zum Fixwert addiert."}</dd></div></dl>)}</div></Section>}
          </>}
        </>}


        {activeTab === "relations" && showEquipment && <Section title="Geräte" description="Gerätearten für Filter und Vergleich unter Analysen; darunter die im Dokument gefundenen Geräte.">
          <ContractDeviceTypesPanel contractId={data.contract_id} orgSlug={orgSlug} canEdit={canEditData} responsibleDepartment={data.assignment?.responsible_department ?? null} onSaved={reload} />
          <h3 className="device-found-heading">Im Dokument gefunden</h3>
          {data.equipment.length === 0 ? <p className="cw-muted">Die Analyse hat keine einzelnen Geräte erkannt.</p> : <div className="cw-equipment-list">{data.equipment.map((item) => <article key={item.id ?? item.equipment_id ?? item.serial_number ?? item.device_name} className="cw-equipment-card"><strong>{item.equipment_id ? <Link href={`/equipment/${item.equipment_id}`}>{item.device_name || item.system_name || item.model || item.equipment_type || item.equipment_category || "Gerät"}</Link> : (item.device_name || item.system_name || item.model || item.equipment_type || item.equipment_category || "Gerät")}</strong><span>{[item.manufacturer, item.model].filter(Boolean).join(" · ") || "Hersteller/Modell nicht verfügbar"}</span><span>{item.serial_number ? `Seriennr. ${item.serial_number}` : "Seriennummer nicht verfügbar"}</span>{item.department ? <span>{item.department}</span> : null}</article>)}</div>}</Section>}

        {activeTab === "deadlines" && slots.deadlines}
        {activeTab === "finance" && slots.finance}
        {activeTab === "documents" && <>
          <div className="cw-document-summary"><InfoCard label="Dokumente" value={String(data.documents.length)} /><InfoCard label="Nachweise" value={String(data.evidence.length)} /><InfoCard label="Prüfstatus" value={data.contract_review.status_label_de} hint={`${data.contract_review.reviewed_count} von ${data.contract_review.relevant_count} geprüft`} /><InfoCard label="Ungeprüfte Angaben" value={String(data.contract_review.unresolved_count)} /></div>
          <nav className="cw-subtabs" aria-label="Dokumente und Prüfung">{DOCUMENT_TABS.map((tab) => <button key={tab.key} type="button" className={documentTab === tab.key ? "active" : ""} onClick={() => setRoute("documents", tab.key)}>{tab.label}</button>)}</nav>
          {documentTab === "document" && <ReextractionPanel
            contractId={data.contract_id}
            orgSlug={orgSlug}
            state={reextraction.state}
            reload={reextraction.reload}
            onApplied={() => { reload(); reextraction.reload(); }}
            onShowPage={showDocumentPage}
            onEditManually={() => setRoute("register")}
            onMarkInDocument={canEditData && mainDocumentId ? openCapture : undefined}
          />}
          {documentTab === "document" && <div className="cw-document-layout"><aside className="cw-document-sidebar"><h2>Quelldokumente</h2>{data.documents.length === 0 ? <p className="cw-muted">Keine Dokumente vorhanden.</p> : data.documents.map((doc) => <button key={doc.document_version_id} type="button" className={documentVersionId === doc.document_version_id ? "active" : ""} onClick={() => { setDocumentVersionId(doc.document_version_id); setNavTarget(null); setActiveEvidenceId(null); }}>{doc.original_filename ?? "Dokument"}<small>{doc.role ?? "Quelle"}</small></button>)}<button type="button" className="cw-evidence-shortcut" onClick={() => setRoute("documents", "evidence")}>{data.evidence.length} Nachweise anzeigen</button></aside><div className="cw-pdf-shell">{canEditData && documentVersionId && !captureOpen ? <div className="source-capture-open"><button type="button" className="btn btn-sm" onClick={openCapture}>Angabe aus dem Text übernehmen</button></div> : null}<PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} onPageChange={onPdfPage} /></div></div>}
          {documentTab === "document" && captureOpen && documentVersionId ? <SourceCapture
            contractId={data.contract_id}
            orgSlug={orgSlug}
            documentVersionId={documentVersionId}
            page={pdfPage}
            onSaved={() => { reload(); reextraction.reload(); }}
            onClose={() => setCaptureOpen(false)}
          /> : null}
          {documentTab === "attachments" && <ContractAttachmentsPanel contractId={data.contract_id} orgSlug={orgSlug} onAnalyzed={reload} />}
          {documentTab === "evidence" && <Section title="Nachweise" description="Quellenangaben aus den Vertragsdokumenten">{sourceLinkError && <p role="alert">Der verlinkte Nachweis ist in diesem Vertrag nicht verfügbar. Bitte wählen Sie einen verfügbaren Nachweis.</p>}<div className="cw-evidence-layout"><div className="cw-evidence-pane"><EvidencePane evidence={data.evidence} activeEvidenceId={activeEvidenceId} onNavigate={(ref) => openEvidence(ref, "evidence")} /><CapturedSources contractId={data.contract_id} orgSlug={orgSlug} version={data} onShow={showSource} /></div><div className="cw-evidence-preview"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} /></div></div></Section>}
          {documentTab === "review" && <ReviewQueueNav contractId={data.contract_id} />}
          {documentTab === "review" && <div className="cw-integrated-panel"><FactReviewPanel data={data} orgSlug={orgSlug} onReload={reload} onNavigate={(ref) => openEvidence(ref, "document")} /><CapturedSources contractId={data.contract_id} orgSlug={orgSlug} version={data} onShow={showSource} compact /></div>}
          {documentTab === "history" && <div className="cw-integrated-panel"><OverridePanel data={data} orgSlug={orgSlug} onReload={reload} /></div>}
        </>}
      </div>
    </div>
  );
}
