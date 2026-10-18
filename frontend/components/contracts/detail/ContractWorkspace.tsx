"use client";

import { revealBox } from "@/lib/box-collapse";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type {
  CalcBasis,
  ContractDetailResponse,
  EvidenceRef,
  FactReviewStateDto,
  FieldEvidenceDto,
  FieldTier,
  MoneyValue,
  SourceNavigationTarget,
} from "@/lib/contract-detail-types";
import {
  RISK_LABEL_DETAIL,
} from "@/lib/contract-detail-types";
import { formatCurrency, formatDate } from "@/lib/format";
import { removeWarningsRepresentedByTasks } from "@/lib/action-dedup";
import { archiveContract, getContractDeletionCapabilities, requestContractDeletion, reviewContractFact } from "@/lib/domain-api/contracts";
import { updateContractRegister } from "@/lib/domain-api/register";
import { getOrganizationStructure } from "@/lib/domain-api/organizations";
import { PdfViewer } from "./lazy";
import EvidenceTable from "./EvidenceTable";
import FieldReviewOverview from "./FieldReviewOverview";
import FieldReviewMode from "./FieldReviewMode";
import FieldDecisionDrawer from "./FieldDecisionDrawer";
import FieldReviewButton, { ReviewControl } from "./FieldReviewButton";
import OverridePanel from "./OverridePanel";
import { hasCalculationBasis } from "./CalculationBasisPanel";
import ContractRegisterPanel from "./ContractRegisterPanel";
import ContractRemarksPanel from "./ContractRemarksPanel";
import Tabs from "@/components/ui/Tabs";
import Signal from "@/components/ui/Signal";
import ActionMenu from "@/components/ui/ActionMenu";
import TagChip, { TagIcon } from "@/components/ui/TagChip";
import ReviewQueueNav from "./ReviewQueueNav";
import { coverPdfUrl } from "@/lib/domain-api/registerGrid";

import Dialog from "@/components/ui/Dialog";
import ContractHistoryPanel from "./ContractHistoryPanel";
import ContractDecisionCard, { pendingDecision } from "./ContractDecisionCard";
import { getRenewalBrief, type RenewalBrief } from "@/lib/domain-api/registerGrid";
import ContractTimeline, { type EndCheck } from "./ContractTimeline";
import ContractAttachmentsPanel from "./ContractAttachmentsPanel";
import ContractRelationsPanel from "./ContractRelationsPanel";
import ContractFinancePanel from "./ContractFinancePanel";
import { BUSINESS_STATUS_LABEL, BUSINESS_STATUS_TONE, type BusinessStatus } from "@/lib/domain-api/register";
import StatusBadge from "@/components/ui/StatusBadge";
import { servicesVisible as servicesVisibleFor } from "@/lib/contract-services";
import { CONFLICT_TARGET, FIELD_PARAM, FINANCE_ENTRIES_TARGET, FINANCE_SUGGESTIONS_TARGET, REEXTRACTION_TARGET, SECTION_PARAM, normalizeTarget, contractHref, documentSearchHref, MISSING_SEARCH, sectionAnchor, warningTarget, type FixTarget } from "@/lib/fix-targets";
import { useContractGaps } from "./ContractGaps";
import { setPageCommands } from "@/lib/page-commands";
import ReextractionPanel, { ReextractionBanner, fieldSearchMap, openProposals, useReextraction } from "./Reextraction";
import ProposalReviewMode from "./ProposalReviewMode";
import SourceCapture from "./SourceCapture";
import RiskButton from "./RiskButton";
import ValueOriginBadge from "./ValueOriginBadge";
import { AiReviewContext, type AiOriginTarget } from "@/components/ui/AiOrigin";
import { findReviewFact } from "@/lib/review-facts";
import ContractTermBar from "./ContractTermBar";
import { SECTION_LABELS, sectionVisible } from "@/lib/contract-sections";
import OpenPoints, { EVIDENCE_REVIEW_SECTION, PROPOSAL_REVIEW_SECTION, buildOpenPoints } from "./OpenPoints";
import ContractDeviceTypesPanel from "./ContractDeviceTypesPanel";
import DocumentList, { DOCUMENT_LIST_THRESHOLD } from "./DocumentList";
import { EvidenceFilterPanel, NO_FILTER, filterLabel, isFiltered, matchesFilter, type EvidenceFilter } from "./EvidenceTable";
import Popover from "@/components/ui/Popover";
import { evidenceNumbers, evidenceRows, factsByEvidence, fieldEvidenceStatus, orderEvidence, precisionOf, titleOf } from "@/lib/evidence";
import { decisionFields, fieldByKey, fieldsOf } from "@/lib/field-review";
import { announceRegisterChange } from "@/lib/register-events";
import CapturedSources from "./CapturedSources";
import { SignalIcon } from "@/components/ui/Signal";
import ResponsibilityChips, { ChipRow } from "./ContractHeaderChips";
import ContractAiSummary from "./ContractAiSummary";
import { FactSourceContext, LIST_SEPARATOR, factValue } from "./CardFact";
import { SCOPE_CHOICES, ScopeCard, ScopeListCard, SlaCard } from "./FactCards";
import ConflictCard from "./ConflictCard";

const [SCOPE_INCLUDED, SCOPE_EXCLUDED] = SCOPE_CHOICES;
const REVIEWED_STATES = new Set(["confirmed", "corrected", "auto_accepted"]);

/** Wie `build_review_summary`: vorliegend, nicht verworfen und noch nicht geprüft. */
function factOpen(fact: FactReviewStateDto | undefined): boolean {
  return Boolean(fact?.present) && fact!.state !== "voided" && !REVIEWED_STATES.has(fact!.state);
}

/** Prüf-Wert einer Leistung als Inklusive/Exklusive (ältere Einträge: Enthalten/Ausgeschlossen). */
function scopeLabel(value: unknown): string | null {
  if (value === SCOPE_INCLUDED || value === "Enthalten") return SCOPE_INCLUDED;
  if (value === SCOPE_EXCLUDED || value === "Ausgeschlossen") return SCOPE_EXCLUDED;
  return null;
}
import { useAuth } from "@/components/auth/AuthProvider";

export type WorkspaceSlot = "overview" | "register" | "deadlines";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload?: () => void;
  /** Zusaetzliche Bereiche je Reiter (z. B. Zustaendigkeit, Entscheidungen, Abrechnung). */
  slots?: Partial<Record<WorkspaceSlot, React.ReactNode>>;
}

type TabKey = "overview" | "register" | "services" | "deadlines" | "finance" | "documents" | "relations" | "notes" | "history";
// Fruehere Reiter (Links aus E-Mails, Lesezeichen) zeigen auf den neuen Ort.
const TAB_ALIASES: Record<string, TabKey> = { term: "deadlines", leistungen: "services", equipment: "relations", remarks: "notes", notizen: "notes" };
type DocumentTab = "document" | "attachments" | "evidence" | "review" | "analysis" | "history";
type OriginKind = "extracted" | "reviewed" | "corrected" | "calculated" | "missing" | "system";

// Schlüssel bleiben (Links, Lesezeichen); die Beschriftung folgt dem Plan (U11).
const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "Übersicht" },
  { key: "register", label: "Vertragsdaten" },
  { key: "deadlines", label: "Fristen & Aufgaben" },
  { key: "finance", label: "Finanzen" },
  { key: "services", label: "Leistungen & SLA" },
  { key: "documents", label: "Dokumente" },
  { key: "relations", label: "Verknüpfungen" },
  { key: "notes", label: "Notizen" },
  { key: "history", label: "Verlauf" },
];

const REVIEW_ICON = <svg className="dw-review-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5v14l11-7z" /></svg>;
const REANALYSE_ICON = <svg className="dw-reanalyse-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z" /></svg>;
const DOC_INFO_ICON = <svg className="cw-doc-foot-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 11v6M12 7.5v.5" /></svg>;

const DOCUMENT_TABS: { key: DocumentTab; label: string }[] = [
  { key: "document", label: "Dokument" },
  { key: "review", label: "Prüfung" },
  // Erneut aus dem Dokument erfassen: Auswahl, Lauf, Ergebnis und Verlauf an einem festen Ort.
  { key: "analysis", label: "KI-Analyse" },
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


function riskLabel(value: string | null): string {
  if (!value) return "Unbekannt";
  return RISK_LABEL_DETAIL[value] ?? value;
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
    verified: precisionOf(ref) === "exact",
  };
}

function OriginBadge({ origin }: { origin: OriginKind }) {
  return <ValueOriginBadge kind={origin} />;
}

function calculatedOrigin(value: unknown, basis: CalcBasis | null | undefined): OriginKind {
  if (value == null || value === "") return "missing";
  return hasCalculationBasis(basis) ? "calculated" : "system";
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
  // „evidence“ ist kein eigener Unterreiter mehr, aber die Nachweise-Leiste des Arbeitsplatzes (alte Links bleiben gültig).
  return value === "evidence" || DOCUMENT_TABS.some((tab) => tab.key === value);
}

const ARCHIVE_ICON = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 5h18v4H3zM5 9v10h14V9M10 13h4" /></svg>;
const DELETE_ICON = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>;
const COVER_ICON = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6" /></svg>;

export default function ContractWorkspace({ data, orgSlug, onReload, slots = {} }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  // Alte Links (?tab=register&feld=reminder_…) führen dorthin, wo das Feld jetzt steht.
  const tabFromUrl = () => {
    const tab = toTab(searchParams.get("tab")) ?? "overview";
    const field = searchParams.get(FIELD_PARAM);
    return tab === "register" && field && normalizeTarget({ tab, field }).tab === "deadlines" ? "deadlines" : tab;
  };
  const initialTab = tabFromUrl();
  const [timelineVersion, setTimelineVersion] = useState(0);
  const initialSubtab = isDocumentTab(searchParams.get("subtab")) ? searchParams.get("subtab") as DocumentTab : "document";
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [documentTab, setDocumentTab] = useState<DocumentTab>(initialSubtab);
  const [showAllSections, setShowAllSections] = useState(false);
  // „Leistungen & SLA hinzufügen“: Reiter auf Wunsch zeigen, auch ohne passenden Vertragstyp oder Angaben.
  const [servicesRevealed, setServicesRevealed] = useState(false);
  const [documentVersionId, setDocumentVersionId] = useState<string | null>(data.documents[0]?.document_version_id ?? null);
  const [navTarget, setNavTarget] = useState<SourceNavigationTarget | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  // Angabe, die die Prüfung nach einem Klick auf eine KI-Plakette zeigt (n: auch wiederholte Klicks).
  const [reviewFocus, setReviewFocus] = useState<{ key: string; n: number } | null>(null);
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
  // Krankenhaus im Kopf nur, wenn die Organisation mehrere hat; unbekannt (lädt/Fehler) = zeigen.
  const [hospitalCount, setHospitalCount] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    getOrganizationStructure(orgSlug)
      .then((value) => { if (active) setHospitalCount(Array.isArray(value?.hospitals) ? value.hospitals.filter((item) => item.is_active).length : null); })
      .catch(() => { if (active) setHospitalCount(null); });
    return () => { active = false; };
  }, [orgSlug]);
  // Entscheidungsvorlage (Backend) für „Offene Punkte: Entscheidung treffen“; neu laden nach jeder Entscheidung.
  const [decisionBrief, setDecisionBrief] = useState<RenewalBrief | null>(null);
  const [decisionVersion, setDecisionVersion] = useState(0);
  useEffect(() => {
    let active = true;
    getRenewalBrief(orgSlug, data.contract_id)
      .then((value) => { if (active) setDecisionBrief(value && Array.isArray(value.hints) ? value : null); })
      .catch(() => { if (active) setDecisionBrief(null); });
    return () => { active = false; };
  }, [orgSlug, data.contract_id, decisionVersion]);
  const [pdfPage, setPdfPage] = useState(1);
  const onPdfPage = useCallback((page: number) => setPdfPage(page), []);
  // „Fehlende Angaben im Dokument suchen“: nur mit Recht, ohne laufende Auswertung und wenn etwas fehlt.
  const reextractionBusy = reextraction.state?.run?.status === "queued" || reextraction.state?.run?.status === "running";
  // Stand der KI-Analyse für Unterreiter und Knopf: offene Vorschläge einer fertigen Analyse bzw. „läuft“.
  const analysisOpen = reextraction.state?.run?.status === "ready" && !reextraction.state.run.stale ? openProposals(reextraction.state.rows).length : 0;
  const analysisBadge = reextractionBusy ? "läuft" : analysisOpen ? String(analysisOpen) : null;
  const searchMissingHref = reextraction.state?.can_start && !reextractionBusy && (reextraction.state?.missing.length ?? 0) > 0
    ? documentSearchHref(data.contract_id, MISSING_SEARCH)
    : null;
  // „Was fehlt noch?“: Karte in der Übersicht und – auf jedem Reiter – Befehle in Strg+K.
  const gaps = useContractGaps({
    contractId: data.contract_id,
    orgSlug,
    hasAnnualCost: Boolean(data.register_facts?.annual_cost),
    // Offen = Angaben der Faktprüfung, die noch niemand geprüft hat (gleiche Zahl wie „Ungeprüfte Angaben“).
    reviewPending: (data.field_review?.essential_open ?? 0) > 0,
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
  const urlTab = tabFromUrl();
  const urlSubtab = searchParams.get("subtab");
  const linkedSection = searchParams.get(SECTION_PARAM);
  useEffect(() => {
    setActiveTab(urlTab);
    if (isDocumentTab(urlSubtab)) setDocumentTab(urlSubtab as DocumentTab);
  }, [urlTab, urlSubtab]);

  // ?abschnitt=…: zum Abschnitt scrollen, sobald er gerendert ist (Reiter laden teils nach).
  useEffect(() => {
    if (!linkedSection) return;
    // „Nachweise prüfen“ (Offene Punkte): geführten Modus öffnen statt zu scrollen.
    if (linkedSection === EVIDENCE_REVIEW_SECTION) { setReviewMode((mode) => mode ?? { startKey: null, tier: null }); return; }
    // „Vorschläge prüfen“ (Offene Punkte): geführten Modus der letzten Analyse öffnen.
    if (linkedSection === PROPOSAL_REVIEW_SECTION) { setProposalMode((mode) => mode ?? { startKey: null }); return; }
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
  // Ein offener Widerspruch steht als eigener Punkt (führt zu „Widerspruch klären“), nicht als Prüf-Aufgabe.
  const openConflicts = useMemo(() => data.warnings.filter((warning) => warning.conflict && warning.requires_review), [data.warnings]);
  const openTasks = useMemo(() => removeWarningsRepresentedByTasks(
    openConflicts,
    data.work_items.filter((item) => item.status !== "resolved"),
  ), [data.work_items, openConflicts]);
  const actionableWarnings = useMemo(() => removeWarningsRepresentedByTasks(
    openTasks,
    data.warnings.filter((warning) => warning.requires_action || warning.requires_review),
  ).map((warning) => (warning.conflict ? { ...warning, title_de: warning.conflict.title_de } : warning)), [data.warnings, openTasks]);

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
  const manyDocuments = data.documents.length > DOCUMENT_LIST_THRESHOLD;
  // „Dokument“ und „Nachweise“ sind ein Arbeitsplatz (Seitenleiste wechselt, das Original bleibt).
  const inDocumentWorkspace = documentTab === "document" || documentTab === "evidence";
  const evidenceFacts = useMemo(() => factsByEvidence(data.fact_review_states ?? []), [data.fact_review_states]);
  const documentIds = useMemo(() => data.documents.map((doc) => doc.document_version_id), [data.documents]);
  const orderedEvidence = useMemo(() => orderEvidence(data.evidence, documentIds), [data.evidence, documentIds]);
  const evidenceNumber = useMemo(() => evidenceNumbers(orderedEvidence), [orderedEvidence]);
  // „Nachweise prüfen“: geführter Modus, ein Nachweis nach dem anderen (startet beim gewählten oder ersten offenen).
  const [reviewMode, setReviewMode] = useState<{ startKey: string | null; tier: FieldTier | null } | null>(null);
  // Entscheidung zu einem Feld direkt aus der Karte (Schublade) – gleiche Ansicht wie in der geführten Prüfung.
  const [fieldDrawer, setFieldDrawer] = useState<string | null>(null);
  // Ein Filter für die Nachweise-Liste und die geführte Prüfung („Nachweise prüfen“ geht nur die Auswahl durch).
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>(NO_FILTER);
  // Klick auf „Nachweise“ (von „Dateien“ aus): Liste zeigen und gleich den Filter aufklappen.
  const [filterOnOpen, setFilterOnOpen] = useState(false);
  useEffect(() => { if (documentTab !== "evidence") setFilterOnOpen(false); }, [documentTab]);
  // „Vorschläge prüfen“: offene Vorschläge der letzten Analyse einzeln (gleicher Arbeitsplatz).
  const [proposalMode, setProposalMode] = useState<{ startKey: string | null } | null>(null);
  // Prüfstand eines Nachweises = Stand seines Felds (ein Feld, eine Entscheidung); ausgeschlossene Nachweise sind kenntlich.
  const fieldReview = data.field_review ?? null;
  const evidenceTableRows = useMemo(() => evidenceRows(orderedEvidence, evidenceNumber, evidenceFacts,
    (ref) => fieldEvidenceStatus(ref.evidence_id, fieldReview)),
  [orderedEvidence, evidenceNumber, evidenceFacts, fieldReview]);
  // Aktiver Filter der Nachweise-Liste: „Nachweise prüfen“ wird „Auswahl prüfen · N“.
  const filteredEvidence = isFiltered(evidenceFilter) ? evidenceTableRows.filter((row) => matchesFilter(row, evidenceFilter)).length : null;
  // Marken auf der Seite: nur Nachweise mit Lage auf dem geöffneten Dokument, gleiche Nummern wie die Liste.
  const pageMarkers = useMemo(() => data.evidence
    .filter((ref) => ref.document_version_id === documentVersionId && ref.page != null && ref.bbox)
    .map((ref) => ({ id: ref.evidence_id, number: evidenceNumber.get(ref.evidence_id) ?? 0, label: titleOf(ref, evidenceFacts), page: ref.page!, bbox: ref.bbox!, bbox_space: ref.bbox_space, active: ref.evidence_id === activeEvidenceId, approx: precisionOf(ref) !== "exact" })),
  [data.evidence, documentVersionId, evidenceNumber, evidenceFacts, activeEvidenceId]);
  // Eine Entscheidung kann ein Feld der Vertragsdaten ändern: Akte und Vertragsdaten laden neu.
  function reloadAfterDecision() {
    reload();
    announceRegisterChange();
  }
  // Geführte Prüfung der Felder (wesentliche zuerst); `key` startet bei einem bestimmten Feld.
  function startFieldReview(tier: FieldTier | null = null, key: string | null = null) {
    if (!inDocumentWorkspace) setRoute("documents", "document");
    setProposalMode(null);
    setReviewMode({ startKey: key, tier });
  }
  // Klick auf einen Nachweis (Liste, Marke): die Prüfung des Felds, zu dem er gehört – sonst nur im Original zeigen.
  function reviewEvidence(ref: EvidenceRef) {
    const field = fieldsOf(fieldReview).find((item) => item.evidence.some((entry) => entry.evidence_id === ref.evidence_id));
    if (field) startFieldReview(field.tier, field.fact_key);
    else openEvidence(ref, "evidence");
  }
  function showFieldEvidence(entry: FieldEvidenceDto) {
    const ref = evidenceById(entry.evidence_id);
    if (ref) openEvidence(ref, "evidence");
    else if (entry.page != null) showDocumentPage(entry.page);
  }
  function showPageQuote(page: number | null, quote: string | null) {
    if (page == null) return;
    setRoute("documents", "document");
    showDocumentPage(page);
    void quote;
  }
  function startProposalReview(startKey: string | null = null) {
    if (!inDocumentWorkspace) setRoute("documents", "document");
    setReviewMode(null);
    setProposalMode({ startKey });
  }
  function showProposalEvidence(evidence: { page: number | null; quote: string | null }) {
    if (!mainDocumentId || evidence.page == null) return;
    setDocumentVersionId(mainDocumentId);
    setNavTarget({ document_version_id: mainDocumentId, page: evidence.page, bbox: null, bbox_space: "pdf_points", supports_exact_navigation: false, label: evidence.quote ?? `Fundstelle Seite ${evidence.page}` });
  }
  function selectDocument(doc: { document_version_id: string }) {
    setDocumentVersionId(doc.document_version_id);
    setNavTarget(null);
    setActiveEvidenceId(null);
  }

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

  // Fundstelle einer Angabe der Faktprüfung (für die KI-Plakette in den Faktkarten).
  const factSource = (fact: FactReviewStateDto | undefined) => {
    const ref = evidenceById(fact?.evidence_ref);
    return ref ? () => openEvidence(ref) : null;
  };

  function SourceButton({ evidence }: { evidence: EvidenceRef | null }) {
    if (!evidence) return null;
    return <button type="button" className="cw-source-button" onClick={() => openEvidence(evidence)}>Quelle</button>;
  }

  const startEvidence = evidenceById(data.dates.start_date_evidence) ?? findExactEvidence("dates.start_date", "start_date");
  const endEvidence = evidenceById(data.dates.documented_end_evidence) ?? findExactEvidence("dates.documented_end_date", "dates.calculated_end_date", "termination.end_date");
  const cancellationEvidence = findExactEvidence("dates.latest_cancellation_date", "termination.latest_cancellation_date", "termination.notice_period");
  const contractNumberEvidence = findExactEvidence("identity.contract_number", "contract_number");
  const annualCostEvidence = findExactEvidence("costs.annual_recurring", "cost.annual_recurring", "payment.annual_cost", "annual_cost");

  const factByKey = new Map((data.fact_review_states ?? []).map((fact) => [fact.fact_key, fact]));
  const canReviewFacts = role === "admin" || role === "contract_manager" || role === "reviewer";
  // Vorschlag aus der KI-Analyse: Verdikt aus dem Text, sonst das Ja/Nein der KI.
  function scopeSuggestion(key: string, legacy: boolean | null): string | null {
    const state = data.scope.scope_status?.[key];
    const verdict = state?.status === "included" ? true : state?.status === "excluded" ? false : state ? state.ai_suggestion ?? null : legacy;
    return verdict === true ? SCOPE_INCLUDED : verdict === false ? SCOPE_EXCLUDED : null;
  }
  // Angezeigter Wert je Leistung: von einer Person geprüft (bestätigt, korrigiert, automatisch übernommen)
  // vor dem KI-Vorschlag. Offen („zu prüfen“) ist eine Leistung genau dann, wenn die Faktprüfung sie als
  // vorliegend und ungeprüft führt – dieselbe Zählung wie „Ungeprüfte Angaben“.
  function scopeState(key: string, legacy: boolean | null) {
    const evidence = evidenceById(data.scope.scope_status?.[key]?.evidence_ref) ?? findExactEvidence(`services.${key}`, `scope.${key}`);
    const fact = factByKey.get(`scope.${key}`);
    const reviewed = fact && REVIEWED_STATES.has(fact.state) ? scopeLabel(fact.effective_value ?? fact.original_value) : null;
    const open = fact ? factOpen(fact) : Boolean(scopeSuggestion(key, legacy));
    const label = reviewed ?? scopeSuggestion(key, legacy) ?? (open ? "Erwähnt – bitte festlegen" : null);
    if (!label) return { label: "Nicht angegeben", tone: "none", evidence, open: false };
    return { label, tone: label === SCOPE_INCLUDED ? "yes" : label === SCOPE_EXCLUDED ? "no" : "unknown", evidence, open: open && !reviewed };
  }

  const effectiveEnd = data.dates.documented_end_date ?? data.dates.calculated_end_date;
  // KI-Auswertungen nur zeigen, wenn es ein analysiertes Dokument gibt (sonst nur "Fehlt"-Kacheln).
  const hasAi = data.documents.length > 0;
  const maintenanceHidden = !showAllSections && data.sections && !data.sections.maintenance ? new Set(["maintenance"]) : undefined;
  const endOrigin: OriginKind = data.dates.documented_end_date ? (endEvidence ? "extracted" : "system") : calculatedOrigin(data.dates.calculated_end_date, data.dates.calculated_end_basis);
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

  // KI-Prüfung „Abweichung beim Vertragsende“: Dokument und Vertragsdaten widersprechen sich, und noch hat
  // niemand die Angabe geprüft. „Beibehalten“ hält die Prüfung fest, „Übernehmen“ setzt das feste Vertragsende.
  const endFact = (data.fact_review_states ?? []).find((fact) => fact.fact_key === "dates.end_date");
  const endUnreviewed = !endFact || endFact.state === "unreviewed" || endFact.state === "needs_review";
  const maintainedEnd = data.register_facts?.contract_end ?? null;
  const documentedEnd = data.dates.documented_end_date ?? null;
  const endDiffers = documentedEnd ? documentedEnd !== maintainedEnd : fixedTerm;
  const endCheck: EndCheck | null = hasAi && maintainedEnd && endUnreviewed && endDiffers ? {
    documented: documentedEnd,
    maintained: maintainedEnd,
    fixedTerm,
    onShowSource: endEvidence ? () => openEvidence(endEvidence) : undefined,
    onAdopt: async () => {
      await updateContractRegister(orgSlug, data.contract_id, { changes: { term_fixed_end_date: documentedEnd } });
      await reviewContractFact(data.contract_id, orgSlug, { fact_key: "dates.end_date", action: "confirmed", system_value: endFact?.original_value ?? documentedEnd, note: "Vertragsende aus dem Dokument übernommen." });
      reload();
    },
    onKeep: async () => {
      await reviewContractFact(data.contract_id, orgSlug, { fact_key: "dates.end_date", action: "corrected", corrected_value: maintainedEnd, system_value: endFact?.original_value ?? documentedEnd, note: "Vertragsende aus den Vertragsdaten beibehalten." });
      reload();
    },
  } : null;

  // Leistungsumfang: Zustand je Leistung und Zusammenfassung (nur mit analysiertem Dokument).
  const scopeRows = SCOPE_FIELDS.map(([key, label, prop]) => ({ key, label, state: scopeState(key, data.scope[prop]), suggestion: scopeSuggestion(key, data.scope[prop]), fact: factByKey.get(`scope.${key}`) }));
  // Weitere Leistungen: Listen der KI-Analyse, von Hand ergänzbar (Faktprüfung `scope.other_*`).
  const scopeLists = ([
    ["other_included", "Weitere inklusive Leistungen", data.scope.included_services],
    ["other_excluded", "Exklusive Leistungen", data.scope.excluded_services],
  ] as const).map(([key, label, items]) => {
    const fact = factByKey.get(`scope.${key}`);
    const suggestion = items.map((item) => item.trim()).filter(Boolean).join(LIST_SEPARATOR) || null;
    return { key, label, fact, suggestion, value: factValue(fact, suggestion) };
  });
  const scopeCounts = {
    included: scopeRows.filter((row) => row.state.tone === "yes").length,
    excluded: scopeRows.filter((row) => row.state.tone === "no").length,
    unknown: scopeRows.filter((row) => row.state.open).length,
  };
  // SLA: von Hand eingetragene Werte (Faktprüfung) vor den Werten aus dem Dokument.
  const slaEmergencyDocument = data.sla.emergency_availability ?? (data.sla.availability_24_7 == null ? null : data.sla.availability_24_7 ? "24/7 erreichbar" : "Nicht 24/7");
  const slaRows = ([
    ["response_time", "Reaktionszeit", data.sla.response_time, "Nicht im Vertrag gefunden"],
    ["resolution_time", "Lösungszeit", data.sla.resolution_time, "Nicht im Vertrag gefunden"],
    ["service_hours", "Servicezeiten", data.sla.service_hours, "Nicht angegeben"],
    ["emergency_availability", "Notfallverfügbarkeit", slaEmergencyDocument, "Unbekannt"],
    ["sla_notes", "Weitere SLA-Angaben", data.sla.sla_notes, "Keine"],
  ] as const).map(([key, label, documentValue, empty]) => {
    const fact = factByKey.get(`sla.${key}`);
    return { key, label, fact, empty, wide: key === "sla_notes", suggestion: documentValue ?? null, value: factValue(fact, documentValue) };
  });
  // Abschnitte je Vertragstyp: nicht vorgesehene, leere Abschnitte ausblenden (lib/contract-sections.ts).
  const sections = showAllSections ? null : data.sections ?? null;
  const scopeHasData = scopeCounts.included + scopeCounts.excluded > 0;
  const slaHasData = Boolean(data.sla.response_time || data.sla.resolution_time || data.sla.service_hours || data.sla.emergency_availability || data.sla.availability_24_7 != null);
  // Reiter „Leistungen & SLA“: bei Vertragstypen mit Leistungsumfang/SLA (Wartung, Service, Dienstleistung …)
  // oder sobald Angaben vorliegen; sonst ausgeblendet und über „Leistungen & SLA hinzufügen“ erreichbar.
  const service = data.register_facts?.service;
  const servicesVisible = activeTab === "services" || servicesVisibleFor({ sections: data.sections, service, scopeHasData, slaHasData, revealed: servicesRevealed });
  // Angaben unter „Details aus dem Dokument“ (nur vorhandene zählen).
  const showScope = hasAi && servicesVisible;
  const showSla = hasAi && servicesVisible;
  // Der Vertragstyp entscheidet. Nur von einer Person gepflegte Angaben (Gerätearten) halten einen Abschnitt sichtbar;
  // von der KI gelesene Angaben stehen im Hinweis und sind über „Trotzdem anzeigen“ erreichbar.
  const showEquipment = sectionVisible("equipment", sections, (data.assignment?.device_types?.length ?? 0) > 0);
  const hiddenSections = data.sections ? ([
    ["equipment", showEquipment, data.equipment.length > 0],
  ] as const).filter(([, shown]) => !shown).map(([key, , found]) => `${SECTION_LABELS[key]}${found ? " (mit Angaben aus dem Dokument)" : ""}`) : [];
  // Erst mit geladenen Lücken berechnen, sonst stünde kurz ein unvollständiges Bild da.
  const openPoints = gaps === null ? null : buildOpenPoints({
    gaps,
    tasks: openTasks,
    warnings: actionableWarnings,
    fieldReview: fieldReview ? {
      essentialOpen: fieldReview.essential_open,
      conflicts: fieldReview.stages[0]?.conflicts ?? 0,
      missing: fieldReview.stages[0]?.missing ?? 0,
      deferred: fieldReview.stages[0]?.deferred ?? 0,
    } : null,
    analysis: reextraction.state ? {
      number: reextraction.state.run?.status === "ready" && !reextraction.state.run.stale ? reextraction.state.run.number : null,
      open: reextraction.state.run?.status === "ready" && !reextraction.state.run.stale ? openProposals(reextraction.state.rows).length : 0,
      newDocument: reextraction.state.new_document?.filename ?? (reextraction.state.new_document ? "" : null),
    } : null,
    cancelByUnknown: !headerCancelBy && !fixedTerm,
    decision: pendingDecision(decisionBrief),
    decisionStep: decisionBrief?.decision?.next_step ? {
      label: decisionBrief.decision.label,
      title: decisionBrief.decision.next_step.title,
      detail: decisionBrief.decision.next_step.detail,
      due: decisionBrief.decision.next_step.due,
      target: decisionBrief.decision.next_step.target,
      done: decisionBrief.decision.steps_done ?? 0,
      total: decisionBrief.decision.steps_total ?? 0,
      today: decisionBrief.as_of,
    } : null,
  });
  // Reiter zeigen, wo Arbeit wartet (Symbol mit Namen für Screenreader).
  const deadlineCritical = (openPoints ?? []).some((point) => point.tone === "critical" && (point.target?.tab === "deadlines" || point.target?.tab === "register"));
  // Vertragsdaten: Entscheidungen zu Feldern, die dort stehen (Vertragsdaten und Fristen).
  const aiOpenCount = decisionFields(fieldReview).filter((item) => item.card === "partner" || item.card === "term").length;
  const tabItems = TABS.filter((tab) => tab.key !== "services" || servicesVisible).map((tab) => ({
    ...tab,
    badge: tab.key === "deadlines" && deadlineCritical
      ? <span className="tab-signal tab-signal--critical" role="img" aria-label="Kritischer offener Punkt"><SignalIcon tone="critical" /></span>
      : tab.key === "register" && aiOpenCount > 0
        ? <span className="tab-signal tab-signal--ai" role="img" aria-label={`${aiOpenCount} ${aiOpenCount === 1 ? "Entscheidung" : "Entscheidungen"} offen`}><SignalIcon tone="ai" /></span>
        : tab.key === "documents" && data.documents.length > 0
          ? <span className="tab-count" aria-hidden="true">{data.documents.length}</span>
          : undefined,
  }));

  // KI-Plakette: zur Prüfung der Angabe, aus der der Wert stammt; ohne passende Angabe zur Fundstelle,
  // sonst zur Prüfung insgesamt. Nichts wird geraten außer über Schlüssel bzw. gleiche Bezeichnung.
  function openAiReview({ factKeys, subject, openSource }: AiOriginTarget) {
    const fact = findReviewFact(data, factKeys, subject);
    // Die Karte öffnet die Entscheidung zum Feld in einer Schublade; dort und in der geführten Prüfung gilt derselbe Stand.
    if (fact && fieldByKey(fieldReview, fact.fact_key)) { setFieldDrawer(fact.fact_key); return; }
    if (fact) {
      setReviewFocus((current) => ({ key: fact.fact_key, n: (current?.n ?? 0) + 1 }));
      setRoute("documents", "review");
      return;
    }
    if (openSource) { openSource(); return; }
    setRoute("documents", "review");
  }

  return (
    <AiReviewContext.Provider value={openAiReview}>
    <div className="contract-workspace">
      <nav className="object-crumbs" aria-label="Brotkrümelnavigation"><Link href="/register">Vertragsliste</Link><span aria-hidden="true">›</span><span aria-current="page">{data.contract_title ?? data.contract_number ?? "Vertrag"}</span></nav>
      <header className="object-header">
        <div className="object-header-main">
          <p className="object-header-eyebrow">{data.register_number
            ? <button type="button" className="header-link" onClick={() => openTarget({ tab: "register", section: "identity" })} title="In den Vertragsdaten ansehen">Vertrag <span className="mono">{data.register_number}</span></button>
            : "Vertrag ohne Nummer"}{data.contract_number ? <> · {contractNumberEvidence
              ? <button type="button" className="header-link" onClick={() => openEvidence(contractNumberEvidence)} title="Fundstelle im Dokument zeigen">Nr. lt. Dokument <span className="mono">{data.contract_number}</span></button>
              : <button type="button" className="header-link" onClick={() => openTarget({ tab: "register", section: "identity" })} title="In den Vertragsdaten ansehen">Nr. lt. Dokument <span className="mono">{data.contract_number}</span></button>}</> : null}</p>
          <div className="object-header-title">
            <h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1>
            {data.business_status ? <button type="button" className="badge-button status-button" onClick={() => openTarget({ tab: "overview", section: "status" })} title="Vertragsstatus ansehen oder ändern"><StatusBadge label={BUSINESS_STATUS_LABEL[data.business_status as BusinessStatus] ?? data.business_status} tone={BUSINESS_STATUS_TONE[data.business_status as BusinessStatus] ?? "neutral"} /></button> : null}
          </div>
          {/* Zeile 1 „was und mit wem“, Zeile 2 „wer und wo“: jede Angabe genau einmal, hier im Kopf (sichtbar in allen Reitern). */}
          <ChipRow label="Vertrag" families={[[
            data.assignment?.contract_type
              ? { key: "type", node: <TagChip kind="type" as="button" srLabel="Vertragstyp" onClick={() => openTarget({ tab: "register", section: "ownership" })} title="Vertragstyp – in der Organisationszuordnung ändern">{data.assignment.contract_type}</TagChip> }
              : canEditData ? { key: "type", node: <button type="button" className="tag-chip tag-chip--missing" onClick={() => openTarget({ tab: "register", section: "ownership" })}><TagIcon kind="type" />Vertragstyp festlegen</button> } : null,
            data.assignment?.contract_category ? { key: "category", node: <TagChip kind="category" as="button" srLabel="Kategorie" onClick={() => openTarget({ tab: "register", section: "ownership" })} title="Kategorie – in der Organisationszuordnung ändern">{data.assignment.contract_category}</TagChip> } : null,
            data.partner
              ? { key: "partner", node: <TagChip kind="partner" as="link" srLabel="Vertragspartner" href={`/stammdaten/vertragspartner?id=${encodeURIComponent(data.partner.id)}`} title="Vertragspartner öffnen und bearbeiten">{data.partner.name}</TagChip> }
              : data.supplier
                ? { key: "partner", node: <TagChip kind="partner" as="button" className="tag-chip--unlinked" onClick={() => openTarget({ tab: "register", field: "partner_id" })} title="Noch keinem Vertragspartner aus den Stammdaten zugeordnet">{data.supplier}<span className="partner-chip-hint">zuordnen</span></TagChip> }
                : null,
          ]]} />
          <ResponsibilityChips assignment={data.assignment} canEdit={canEditData} hospitalCount={hospitalCount} onOpen={() => openTarget({ tab: "register", section: "ownership" })} />
          <div className="object-header-meta object-header-signals">
            {openPoints?.length ? <Link className="open-points-link" href={contractHref(data.contract_id, { tab: "overview", section: "offene-punkte" })} onClick={(event) => { event.preventDefault(); openTarget({ tab: "overview", section: "offene-punkte" }); }}><Signal tone={openPoints[0].tone === "critical" ? "critical" : "warning"}>Offene Punkte · {openPoints.length}</Signal></Link> : null}
            <FieldReviewButton review={fieldReview} onOpenField={(field) => setFieldDrawer(field.fact_key)} onStartGuided={(tier) => startFieldReview(tier)} />
            <RiskButton contractId={data.contract_id} orgSlug={orgSlug} risk={data.risk ?? (data.risk_level ? { computed: data.risk_level, effective: data.risk_level, override: null, confirmed: null } : null)} warnings={data.warnings.filter((warning) => !warning.review_resolved).map((warning) => (warning.conflict ? { ...warning, title_de: warning.conflict.title_de } : warning))} canEdit={canEditData} onChanged={reload} />
          </div>
        </div>
        <dl className={`object-header-facts${fixedTerm ? " object-header-facts--three" : ""}`}>
          <div><dt>Vertragsbeginn</dt><dd>{contractStart ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (data.register_facts?.contract_start || !startEvidence ? openTarget({ tab: "register", field: "term_start_date" }) : openEvidence(startEvidence))} title={data.register_facts?.contract_start || !startEvidence ? "In den Vertragsdaten ansehen" : "Fundstelle im Dokument zeigen"}>{formatDate(contractStart)}</button><ValueOriginBadge kind={data.register_facts?.contract_start ? "system" : "extracted"} onOpenSource={!data.register_facts?.contract_start && startEvidence ? () => openEvidence(startEvidence) : null} factKey="dates.start_date" /></span> : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", field: "term_start_date" })} aria-label="Vertragsbeginn erfassen">Beginn erfassen</button></span>}</dd></div>
          <div><dt>Vertragsende</dt><dd>{headerEnd ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (data.register_facts?.contract_end || !endEvidence ? openTarget({ tab: "register", section: "term" }) : openEvidence(endEvidence))} title={data.register_facts?.contract_end || !endEvidence ? "Berechnung in den Vertragsdaten (Laufzeit) ansehen" : "Fundstelle im Dokument zeigen"}>{formatDate(headerEnd)}</button>{(() => { const aiEnd = !data.register_facts?.contract_end && endOrigin === "extracted" && endEvidence ? () => openEvidence(endEvidence) : null; return <><ValueOriginBadge kind={data.register_facts?.contract_end ? "calculated" : endOrigin} onOpenSource={aiEnd} factKey="dates.end_date" />{aiEnd ? null : <SourceButton evidence={data.dates.documented_end_date && !data.register_facts?.contract_end ? endEvidence : null} />}</>; })()}</span> : (openEnded ? <span className="fact-value">unbefristet</span> : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", section: "term" })}>Laufzeit &amp; Kündigung ergänzen</button></span>)}</dd></div>
          {fixedTerm ? null : <div className={headerCancelBy ? undefined : "fact--alert"}><dt>Kündbar bis</dt><dd>{headerCancelBy ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => setRoute("deadlines")} title="Fristen ansehen">{formatDate(headerCancelBy)}</button><ValueOriginBadge kind="calculated" /><SourceButton evidence={data.register_facts?.cancel_by ? null : cancellationEvidence} /></span> : <span className="fact-value"><Signal tone="critical" size="sm">Nicht berechenbar</Signal><button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", field: "notice_period_value" })}>Kündigungsfrist erfassen</button></span>}</dd></div>}
          <div><dt>Jährliche Kosten</dt><dd className="num">{maintainedAnnual
            ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => openTarget(FINANCE_ENTRIES_TARGET)} title="Finanzposten ansehen">{moneyLike(maintainedAnnual.amount, maintainedAnnual.currency)}</button><ValueOriginBadge kind="system" detail="Aus den gepflegten Finanzposten" /></span>
            : aiAnnual
              ? <span className="fact-value"><button type="button" className="fact-link" onClick={() => (annualCostEvidence ? openEvidence(annualCostEvidence) : setRoute("finance"))} title={annualCostEvidence ? "Fundstelle im Dokument zeigen" : "Finanzen ansehen"}>{money(data.costs.annual_recurring)}</button><ValueOriginBadge kind="extracted" detail="noch nicht in die Finanzen übernommen" onOpenSource={annualCostEvidence ? () => openEvidence(annualCostEvidence) : null} factKey="costs.annual" /><button type="button" className="rg-link" onClick={() => openTarget(FINANCE_SUGGESTIONS_TARGET)}>In Finanzen übernehmen</button></span>
              : <span className="fact-value"><Signal tone="critical" size="sm">Fehlt</Signal><button type="button" className="rg-link" onClick={() => openTarget(FINANCE_ENTRIES_TARGET)} aria-label="Jährliche Kosten erfassen">Kosten erfassen</button></span>}</dd></div>
        </dl>
        <div className="object-header-term"><ContractTermBar start={contractStart} end={headerEnd} cancelBy={headerCancelBy} fixedTerm={fixedTerm} openEnded={openEnded} onOpen={() => setRoute("deadlines")} /></div>
        <div className="object-header-actions">
          {canEditData ? <button type="button" className="btn" onClick={() => setRoute("register")} title="Vertragsdaten bearbeiten"><svg className="btn-symbol" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" /></svg>Bearbeiten</button> : null}
          <button type="button" className="btn btn-ai" onClick={() => window.dispatchEvent(new Event("medflux:assistant-toggle"))}><svg className="btn-symbol" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></svg>KI-Assistent</button>
          <ActionMenu items={[
            { label: "Archivieren", icon: ARCHIVE_ICON, onSelect: () => { setArchiveError(null); setArchiveDialogOpen(true); } },
            ...(canRequestDeletion ? [{ label: "Löschung beantragen", icon: DELETE_ICON, danger: true, onSelect: () => { setDeleteAcknowledged(false); setDeleteError(null); setDeleteDialogOpen(true); } }] : []),
            "separator",
            { label: "Deckblatt (PDF)", icon: COVER_ICON, onSelect: () => { window.open(coverPdfUrl(orgSlug, data.contract_id), "_blank", "noopener,noreferrer"); } },
          ]} />
        </div>
      </header>
      <ReextractionBanner state={reextraction.state} onOpen={() => openTarget(REEXTRACTION_TARGET)} />
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
          {/* Erste Karte: Vertragsstatus (Statusweg, nächster Schritt, Statuswechsel). */}
          <ContractRegisterPanel view="status" contractId={data.contract_id} orgSlug={orgSlug} onChanged={reload}
            onOpenField={(key, view) => openTarget({ tab: view === "deadlines" ? "deadlines" : "register", field: key })} />
          <ConflictCard contractId={data.contract_id} orgSlug={orgSlug} warnings={openConflicts} facts={factByKey} evidence={data.evidence} canDecide={canReviewFacts} onOpenEvidence={(ref) => openEvidence(ref, "document")} onOpenTarget={() => openTarget({ tab: "register", section: "term" })} onSaved={reload} />
          {/* Entwurf: links KI-Zusammenfassung und Vertragsanalyse, rechts Offene Punkte. */}
          <div className="cw-overview-cols">
          <div className="cw-overview-main">
            <ContractAiSummary contractId={data.contract_id} orgSlug={orgSlug} />
            {!servicesVisible && canEditData ? <p className="sections-hidden-note">Kein Leistungsumfang und keine SLA erfasst. <button type="button" className="rg-link" onClick={() => { setServicesRevealed(true); setRoute("services"); }}>Leistungen &amp; SLA hinzufügen</button></p> : null}
            {hiddenSections.length ? <p className="sections-hidden-note">Für {data.sections!.type_label} ausgeblendet: {hiddenSections.join(", ")}. <button type="button" className="rg-link" onClick={() => setShowAllSections(true)}>Trotzdem anzeigen</button></p> : null}
            {showAllSections && data.sections ? <p className="sections-hidden-note">Alle Abschnitte werden angezeigt. <button type="button" className="rg-link" onClick={() => setShowAllSections(false)}>Nur passende Abschnitte</button></p> : null}
            {hasAi && !data.sections ? <p className="sections-hidden-note">Mit einem Vertragstyp zeigt die Akte nur die passenden Abschnitte. {canEditData ? <button type="button" className="rg-link" onClick={() => openTarget({ tab: "register", section: "ownership" })}>Vertragstyp festlegen</button> : null}</p> : null}
            {slots.overview}
          </div>
          <div className="cw-overview-side">
            <OpenPoints contractId={data.contract_id} points={openPoints} searchHref={searchMissingHref} onOpen={openTarget} />
          </div>
          </div>
        </div>}

        {activeTab === "register" && <><ContractRegisterPanel
          contractId={data.contract_id}
          orgSlug={orgSlug}
          onChanged={reload}
          searchableKeys={reextraction.state?.can_start ? new Set(fieldSearchMap(reextraction.state).keys()) : undefined}
          onSearchInDocument={(key) => router.replace(documentSearchHref(data.contract_id, key), { scroll: false })}
          onShowSource={showSource}
          hiddenSections={maintenanceHidden}
          afterStatus={slots.register}
          onOpenField={(key, view) => openTarget({ tab: view === "deadlines" ? "deadlines" : "register", field: key })}
          onOpenStatus={() => openTarget({ tab: "overview", section: "status" })}
        /></>}

        {activeTab === "services" && <FactSourceContext.Provider value={factSource}><div className="stack-4">
          {/* Entwurf „Leistungsumfang & SLA“: links Leistungen, rechts SLA; darunter weitere und exklusive Leistungen. */}
          {showScope || showSla ? <div className="svc-grid">
            {/* Entwurf: links Leistungsumfang + weitere inklusive Leistungen, rechts SLA + exklusive Leistungen. */}
            <div className="svc-col">
              {showScope ? <ScopeCard contractId={data.contract_id} orgSlug={orgSlug} canEdit={canReviewFacts} onSaved={reload} rows={scopeRows} historyHref={contractHref(data.contract_id, { tab: "documents", subtab: "history" })} /> : null}
              {showScope ? scopeLists.filter((list) => list.key === "other_included").map((list) => <ScopeListCard key={list.key} contractId={data.contract_id} orgSlug={orgSlug} canEdit={canReviewFacts} onSaved={reload} list={list} />) : null}
            </div>
            <div className="svc-col">
              {showSla ? <SlaCard contractId={data.contract_id} orgSlug={orgSlug} canEdit={canReviewFacts} onSaved={reload} rows={slaRows} /> : null}
              {showScope ? scopeLists.filter((list) => list.key === "other_excluded").map((list) => <ScopeListCard key={list.key} contractId={data.contract_id} orgSlug={orgSlug} canEdit={canReviewFacts} onSaved={reload} list={list} />) : null}
            </div>
          </div> : null}
          {!hasAi ? <p className="sections-hidden-note">Ohne KI-Analyse gibt es keine Leistungsliste und keine SLA-Werte aus dem Dokument.</p> : null}
        </div></FactSourceContext.Provider>}

        {activeTab === "notes" && <ContractRemarksPanel contractId={data.contract_id} orgSlug={orgSlug} />}

        {activeTab === "history" && <ContractHistoryPanel contractId={data.contract_id} orgSlug={orgSlug} />}

        {activeTab === "deadlines" && <div className="stack-4">
          <ContractDecisionCard contractId={data.contract_id} orgSlug={orgSlug} onReminderCreated={() => setTimelineVersion((value) => value + 1)} onDecisionChanged={() => setDecisionVersion((value) => value + 1)} />
          <ContractTimeline contractId={data.contract_id} orgSlug={orgSlug} workItems={data.work_items} endCheck={endCheck} onOpenTarget={openTarget} version={timelineVersion} />
        </div>}

        {activeTab === "relations" && <ContractRelationsPanel contractId={data.contract_id} orgSlug={orgSlug} />}
        {activeTab === "finance" && <ContractFinancePanel
          contractId={data.contract_id}
          orgSlug={orgSlug}
          documentCosts={hasAi ? data.costs : null}
          contractStart={data.register_facts?.contract_start ?? null}
          findSource={(field) => { const ref = findExactEvidence(field); return ref ? () => openEvidence(ref) : null; }}
          documentBasis={hasAi ? { tax_basis: data.costs.tax_basis, tax_rate_percent: data.costs.tax_rate_percent, currency: data.costs.annual_recurring.currency ?? data.costs.monthly_recurring.currency ?? null, source_period: data.costs.source_period } : null}
        />}


        {activeTab === "relations" && showEquipment && <>
          <ContractDeviceTypesPanel contractId={data.contract_id} orgSlug={orgSlug} canEdit={canEditData} responsibleDepartment={data.assignment?.responsible_department ?? null} onSaved={reload} /></>}

        {activeTab === "deadlines" && slots.deadlines}
        {activeTab === "documents" && <>
          {/* Kopf: Unterreiter links; rechts Stand der Prüfung mit dem nächsten Schritt. */}
          <div className="cw-doc-head">
            <nav className="cw-subtabs" aria-label="Dokumente und Prüfung">{DOCUMENT_TABS.map((tab) => <button key={tab.key} type="button" className={(tab.key === "document" ? inDocumentWorkspace : documentTab === tab.key) ? "active" : ""} aria-current={(tab.key === "document" ? inDocumentWorkspace : documentTab === tab.key) ? "page" : undefined} onClick={() => setRoute("documents", tab.key)}>{tab.label}{tab.key === "analysis" && analysisBadge ? <span className="dw-count">{analysisBadge}</span> : null}</button>)}</nav>
            <div className="dw-status" aria-label="Stand der Dokumente">
              <span className="dw-status-counts">{data.documents.length} {data.documents.length === 1 ? "Datei" : "Dateien"} · {data.evidence.length} Nachweise</span>
              {documentTab !== "analysis" && (reextraction.state?.can_start || analysisBadge) ? <button type="button" className="btn btn-sm dw-reanalyse" onClick={() => openTarget(REEXTRACTION_TARGET)}>
                {REANALYSE_ICON}{reextractionBusy ? "KI-Analyse läuft" : analysisOpen ? `${analysisOpen} ${analysisOpen === 1 ? "Vorschlag" : "Vorschläge"} prüfen` : "Erneut erfassen"}
              </button> : null}
              {/* Eine Prüfung: ein Fortschritt (Felder, nicht Nachweise), eine Handlung. */}
              {!reviewMode && documentTab !== "review" ? <ReviewControl review={fieldReview} onStart={(tier) => startFieldReview(tier)} onOpenOverview={() => setRoute("documents", "review")} /> : null}
            </div>
          </div>
          {documentTab === "analysis" && <ReextractionPanel
            loadError={reextraction.error}
            contractId={data.contract_id}
            orgSlug={orgSlug}
            state={reextraction.state}
            reload={reextraction.reload}
            onApplied={() => { reload(); reextraction.reload(); }}
            onShowPage={(page) => { setRoute("documents", "document"); showDocumentPage(page); }}
            onEditManually={(key) => (key ? openTarget({ tab: "register", field: key }) : setRoute("register"))}
            onMarkInDocument={canEditData && mainDocumentId ? openCapture : undefined}
            onReviewProposals={startProposalReview}
            onReviewEvidence={() => startFieldReview()}
          />}
          {inDocumentWorkspace && proposalMode && reextraction.state?.run ? <ProposalReviewMode
            contractId={data.contract_id}
            orgSlug={orgSlug}
            contractTitle={data.contract_title}
            run={reextraction.state.run}
            proposals={reextraction.state.rows}
            startKey={proposalMode.startKey}
            canDecide={Boolean(reextraction.state.can_start)}
            onShow={showProposalEvidence}
            onExit={() => { setProposalMode(null); reextraction.reload(); openTarget(REEXTRACTION_TARGET); }}
            onChanged={() => { reload(); reextraction.reload(); }}
            onEditManually={(key) => { setProposalMode(null); if (key) openTarget({ tab: "register", field: key }); else setRoute("register"); }}
            viewer={<PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} onPageChange={onPdfPage} variant="review" />}
          /> : null}
          {inDocumentWorkspace && sourceLinkError ? <p role="alert" className="rg-error">Der verlinkte Nachweis ist in diesem Vertrag nicht verfügbar. Bitte wählen Sie einen verfügbaren Nachweis.</p> : null}
          {/* Ein Arbeitsplatz: links Dateien oder Nachweise, rechts immer dasselbe Original (bleibt beim Umschalten offen). */}
          {inDocumentWorkspace && reviewMode && !proposalMode && fieldReview ? <FieldReviewMode
            contractId={data.contract_id}
            orgSlug={orgSlug}
            contractTitle={data.contract_title}
            data={data}
            review={fieldReview}
            startKey={reviewMode.startKey}
            startTier={reviewMode.tier}
            canReview={canReviewFacts}
            onShow={(ref) => openEvidence(ref, "evidence")}
            onShowPage={showPageQuote}
            onExit={() => setReviewMode(null)}
            onReload={reloadAfterDecision}
            onOpenAnalysis={() => { setReviewMode(null); openTarget(REEXTRACTION_TARGET); }}
            onOpenFindings={() => { setReviewMode(null); setRoute("documents", "review"); }}
            viewer={<PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} onPageChange={onPdfPage} markers={pageMarkers} variant="review" />}
          /> : null}
          {inDocumentWorkspace && !reviewMode && !proposalMode && <div className="dw">
            <aside className="dw-side" aria-label="Dateien und Nachweise">
              <div className="dw-switch" role="group" aria-label="Seitenleiste">
                <button type="button" aria-pressed={documentTab === "document"} onClick={() => setRoute("documents", "document")}>Dateien<span className="dw-count" aria-hidden="true">{data.documents.length}</span></button>
                {documentTab === "evidence"
                  ? <Popover
                    label={<>Nachweise<span className="dw-count" aria-hidden="true">{filteredEvidence ?? data.evidence.length}</span></>}
                    triggerLabel={filteredEvidence != null ? `Nachweise filtern (${filteredEvidence} von ${data.evidence.length})` : "Nachweise filtern"}
                    panelLabel="Nachweise filtern"
                    triggerClassName="dw-switch-trigger"
                    className="dw-switch-popover"
                    active={filteredEvidence != null}
                    defaultOpen={filterOnOpen}
                    wide
                  >
                    {(close) => <EvidenceFilterPanel rows={evidenceTableRows} filter={evidenceFilter} onApply={(next) => { setEvidenceFilter(next); close(); }} />}
                  </Popover>
                  : <button type="button" aria-pressed={false} onClick={() => { setFilterOnOpen(true); setRoute("documents", "evidence"); }}>Nachweise<span className="dw-count" aria-hidden="true">{data.evidence.length}</span></button>}
              </div>
              {documentTab === "evidence"
                ? <div className="dw-panel">{filteredEvidence != null ? <p className="dw-filter-line" role="status">
                  <span>{`Nur ${filterLabel(evidenceFilter, evidenceTableRows)} · ${filteredEvidence}`}</span>
                  <button type="button" onClick={() => setEvidenceFilter(NO_FILTER)} aria-label="Filter aufheben">×</button>
                </p> : null}{data.evidence.length
                  ? <EvidenceTable rows={evidenceTableRows} currentId={activeEvidenceId} caption="Nachweise dieses Vertrags" onPick={reviewEvidence}
                    filter={evidenceFilter} onFilter={setEvidenceFilter} />
                  : <p className="cw-muted dw-empty">Keine Nachweise vorhanden.</p>}<CapturedSources contractId={data.contract_id} orgSlug={orgSlug} version={data} onShow={showSource} /></div>
                : data.documents.length === 0 ? <p className="cw-muted dw-empty">Keine Dokumente vorhanden.</p>
                  : <DocumentList documents={data.documents} selectedId={documentVersionId} mainId={mainDocumentId} onSelect={selectDocument} compact={!manyDocuments} />}
            </aside>
            <div className="dw-main">
              <div className="cw-pdf-shell"><PdfViewer contractId={data.contract_id} orgSlug={orgSlug} documentVersionId={documentVersionId} active={Boolean(documentVersionId)} navTarget={navTarget} onPageChange={onPdfPage} pagesOpen={false}
                markers={documentTab === "evidence" ? pageMarkers : []}
                onMarker={(id) => { const ref = evidenceById(id); if (ref) reviewEvidence(ref); }} /></div>
              <div className="cw-doc-foot">
                <span>{DOC_INFO_ICON}{canEditData ? "Eine Stelle im Text markieren, um daraus eine Angabe zu übernehmen." : "Nachweise zeigen, wo jede Angabe im Dokument steht."}</span>
                {canEditData && documentVersionId ? <button type="button" className="btn btn-sm" disabled={captureOpen} onClick={openCapture}>Angabe übernehmen</button> : null}
              </div>
            </div>
          </div>}
          {inDocumentWorkspace && captureOpen && documentVersionId ? <SourceCapture
            contractId={data.contract_id}
            orgSlug={orgSlug}
            documentVersionId={documentVersionId}
            page={pdfPage}
            onSaved={() => { reload(); reextraction.reload(); }}
            onClose={() => setCaptureOpen(false)}
          /> : null}
          {documentTab === "attachments" && <ContractAttachmentsPanel contractId={data.contract_id} orgSlug={orgSlug} onAnalyzed={reload} />}
          {documentTab === "review" && <ReviewQueueNav contractId={data.contract_id} />}
          {documentTab === "review" && <div className="cw-integrated-panel"><FieldReviewOverview data={data} orgSlug={orgSlug} canReview={canReviewFacts} focusKey={reviewFocus} onReload={reloadAfterDecision}
            onStartGuided={(tier, key) => startFieldReview(tier, key ?? null)} onShowEvidence={showFieldEvidence} onShowPage={showPageQuote} onOpenAnalysis={() => openTarget(REEXTRACTION_TARGET)} />
            <CapturedSources contractId={data.contract_id} orgSlug={orgSlug} version={data} onShow={showSource} compact /></div>}
          {documentTab === "history" && <div className="cw-integrated-panel"><OverridePanel data={data} orgSlug={orgSlug} onReload={reload} /></div>}
        </>}
      </div>
    </div>
      <FieldDecisionDrawer contractId={data.contract_id} orgSlug={orgSlug} review={fieldReview} factKey={fieldDrawer} canReview={canReviewFacts} onClose={() => setFieldDrawer(null)}
        onReload={reloadAfterDecision} onShowEvidence={showFieldEvidence} onShowPage={showPageQuote} onOpenAnalysis={() => { setFieldDrawer(null); openTarget(REEXTRACTION_TARGET); }}
        onStartGuided={(key) => startFieldReview(fieldByKey(fieldReview, key)?.tier ?? null, key)} />
    </AiReviewContext.Provider>
  );
}
