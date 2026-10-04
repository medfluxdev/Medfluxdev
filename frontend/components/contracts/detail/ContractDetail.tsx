"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  ContractDetailResponse,
  DetailDocument,
  EvidenceRef,
  ImportStateDto,
  SourceNavigationTarget,
  TaxBreakdownDto,
} from "@/lib/contract-detail-types";
import {
  RISK_LABEL_DETAIL,
  SEVERITY_LABEL,
  STATUS_LABEL_DETAIL,
} from "@/lib/contract-detail-types";
import {
  identificationQualityLabel,
  relationshipQualityLabel,
  workItemStatusLabel,
  workItemTypeLabel,
} from "@/lib/pr4-types";
import {
  formatCurrency,
  formatDate,
  formatDaysRemaining,
} from "@/lib/format";
import { apiPost } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { evidencePrecision } from "@/lib/source-geometry";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import SourceLink from "./SourceLink";
import EvidencePane from "./EvidencePane";
import PdfViewer from "./PdfViewer";
import OverridePanel from "./OverridePanel";
import FactReviewPanel from "./FactReviewPanel";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload?: () => void;
}

// ─────────────────────────────────────────────────────────────────────────
// Evidence-Nachweis-Findung
// Ein ausgewiesener Fakt ist mit einer Quelle verknuepft, wenn eine Evidence
// deren field_ref exakt (=Feld) ODER ueber den Gruppen-Praefix (=Sektion,
// z. B. "termination.evidence") matcht. Nichts wird erfunden: ohne Treffer
// ist der Wert schlicht nicht belegt (-> "Unbekannt", nicht klickbar).
// ─────────────────────────────────────────────────────────────────────────
function evidenceFor(
  evidence: EvidenceRef[],
  candidates: string[]
): EvidenceRef | null {
  const exact = (e: EvidenceRef) => {
    const fr = e.field_ref ?? "";
    return candidates.some((c) => fr === c);
  };
  const prefix = (e: EvidenceRef) => {
    const fr = e.field_ref ?? "";
    return candidates.some((c) => fr.startsWith(c + "."));
  };
  const isRecovered = (e: EvidenceRef) =>
    (e.evidence_id ?? "").startsWith("recovered:");
  // UAT Re-Test (Defect 1): eine wiederhergestellte, wörtlich belegte Quelle
  // (evidence_id "recovered:...") hat Vorrang vor dekorativen Sammel-/
  // Extraktions-Refs – so zeigt z. B. der Vertragsbeginn dieselbe kanonische
  // Seite (p5) wie Review/Evidence; ohne Treffer bleibt es ehrlich unbelegt.
  return (
    evidence.find((e) => isRecovered(e) && exact(e)) ??
    evidence.find((e) => isRecovered(e) && prefix(e)) ??
    evidence.find(exact) ??
    evidence.find(prefix) ??
    null
  );
}

function precisionHint(ev: EvidenceRef | null): string | null {
  if (!ev) return null;
  if (!ev.page) return "ohne Position";
  if (ev.supports_exact_navigation && ev.bbox) {
    // UAT Defect D: eine seitenfuellende Region ist keine exakte Position.
    return evidencePrecision(ev.bbox, ev.bbox_space) === "coarse"
      ? `ungefähre Lage · Seite ${ev.page}`
      : `Seite ${ev.page} (Seitenbereich)`;
  }
  return `Seite ${ev.page} (ohne exakte Position)`;
}

// ─────────────────────────────────────────────────────────────────────────
// Bausteine
// ─────────────────────────────────────────────────────────────────────────

function Rule({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="detail-rule">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

// Deutsche Bezeichnungen für die Identitäts-Karte (keine rohen englischen Keys).
const IDENTITY_LABELS: Record<string, string> = {
  contract_number: "Vertragsnummer",
  contract_type: "Vertragstyp",
  contractor: "Auftragnehmer",
  customer: "Auftraggeber (Kunde)",
  contact_person: "Ansprechpartner",
  customer_number: "Kundennummer",
  department: "Abteilung",
  location: "Standort",
  system_identity: "System (aus Vertrag)",
  title: "Vertragsbezeichnung",
  contract_title: "Vertragsbezeichnung",
  supplier: "Lieferant",
};

// UAT Re-Test (Defect 2): deutsche Bezeichnungen der Leistungs-Sachverhalte.
const SCOPE_STATUS_LABELS: Record<string, string> = {
  maintenance: "Wartung",
  inspection: "Inspektion / Sichtprüfung",
  repair: "Reparatur",
  calibration: "Kalibrierung",
  software_updates: "Software-Updates",
  remote_support: "Remote-Support",
  technical_support: "Technischer Support",
  spare_parts_included: "Ersatzteile im Wartungsumfang",
  consumables_included: "Verbrauchsmaterial im Wartungsumfang",
  emergency_service: "Notdienst / Einsatz außerhalb der Arbeitszeit",
};

const SCOPE_STATUS_ORDER = [
  "maintenance",
  "inspection",
  "repair",
  "calibration",
  "software_updates",
  "remote_support",
  "technical_support",
  "spare_parts_included",
  "consumables_included",
  "emergency_service",
];

const SCOPE_STATUS_TEXT: Record<string, string> = {
  included: "Ja – Inklusive Leistung",
  excluded: "Ausgeschlossen",
  not_established: "Erwähnt – zu prüfen",
};

function ScopeStatusValue({
  status,
  evidenceRef,
  evidence,
  onFocusEvidence,
}: {
  status: string;
  evidenceRef: string | null;
  evidence: EvidenceRef[];
  onFocusEvidence: (ev: EvidenceRef) => void;
}) {
  const cls =
    status === "included" ? "scope-ok" : status === "excluded" ? "scope-no" : "scope-review";
  const label = SCOPE_STATUS_TEXT[status] ?? status;
  const ref = evidenceRef ? evidence.find((e) => e.field_ref === evidenceRef) : undefined;
  if (ref) {
    return (
      <button
        type="button"
        className={`scope-status ${cls}`}
        onClick={() => onFocusEvidence(ref)}
        title={ref.snippet ?? ""}
      >
        {label}
        <span className="fact-cite" aria-hidden="true">Quelle</span>
      </button>
    );
  }
  return <span className={`scope-status ${cls}`}>{label}</span>;
}

// Vertragsbeginn-Status in verständlichem Deutsch (UAT Defect Batch A).
const START_STATUS_LABELS: Record<string, string> = {
  documented: "Im Vertrag dokumentiert",
  explicit: "Aus der Extraktion übernommen",
  provisional: "Extraktion nicht eindeutig – zu prüfen",
  event_based: "Ereignisbasiert (kein Termin dokumentiert)",
  needs_review: "Widersprüchliche Angaben – bitte prüfen",
  overridden: "Manuell übernommen",
};

function startStatusLabel(status: string | null | undefined): string | null {
  if (!status) return null;
  if (status === "explicit") return null; // Standardfall: kein Hinweis nötig
  return START_STATUS_LABELS[status] ?? status;
}

// Defensiver Fallback: Teildaten (z. B. Test-Fixtures) ohne tax_breakdown
// dürfen die Detailseite nicht crashen lassen – die Inhalte bleiben ehrlich
// "Unbekannt"/leer statt erfundener Werte.
const EMPTY_TAX_BREAKDOWN: TaxBreakdownDto = {
  computed: false,
  base_tax_basis: null,
  rate_percent: null,
  currency: null,
  monthly_net: null,
  monthly_gross: null,
  annual_net: null,
  annual_gross: null,
  monthly_tax: null,
  annual_tax: null,
  explanation: null,
  source: null,
  evidence_field_refs: {},
};

function money(m: { amount: string | number | null; currency: string | null; status?: string | null }) {
  if (m.amount == null || !m.currency)
    return <span className="muted">Nicht verfügbar</span>;
  return <>{formatCurrency(String(m.amount), m.currency)}</>;
}

// Netto/Brutto/MwSt-Zelle mit Quellen-Navigation: ist der Wert im Vertrag
// direkt belegt (Recovery), ist er klickbar und springt zur Fundstelle.
function moneyCellWithEvidence({
  amount,
  currency,
  evidence,
  activeEvidenceId,
  onFocusEvidence,
}: {
  amount: string | null;
  currency: string | null;
  evidence: EvidenceRef | null;
  activeEvidenceId: string | null;
  onFocusEvidence: (ev: EvidenceRef) => void;
}) {
  if (amount == null || !currency) {
    return <span className="needs-review">Zu prüfen</span>;
  }
  if (!evidence) {
    return <>{formatCurrency(amount, currency)}</>;
  }
  const active = evidence.evidence_id === activeEvidenceId;
  return (
    <>
      <button
        type="button"
        className={`fact-value-btn${active ? " active" : ""}`}
        aria-pressed={active}
        aria-label={`${formatCurrency(amount, currency)} — Quelle öffnen`}
        title="Quelle im Original öffnen"
        onClick={() => onFocusEvidence(evidence)}
      >
        <span className="fact-value">{formatCurrency(amount, currency)}</span>
        <span className="fact-cite" aria-hidden="true">
          Quellenangabe
        </span>
      </button>
      {precisionHint(evidence) && (
        <span className="fact-precision">{precisionHint(evidence)}</span>
      )}
    </>
  );
}

function YesNo({ v }: { v: boolean | null }) {
  if (v == null) return <span className="muted">Unbekannt</span>;
  return <>{v ? "Ja" : "Nein"}</>;
}

// Berechnungsgrundlage (autoritativ aus dem akzeptierten STEP-9-Snapshot).
// Reine Anzeige – das Frontend rechnet NICHTS neu. Ohne Erläuterung keine Zeile.
function BasisNote({ basis, hint }: { basis: { explanation?: string | null; inputs?: Record<string, string> }; hint?: string | null }) {
  if (!basis?.explanation) {
    if (!hint) return null;
    return <p className="fact-basis-note">{hint}</p>;
  }
  return (
    <p className="fact-basis-note">
      <span className="fact-basis-label">Berechnungsgrundlage:</span> {basis.explanation}
      {hint ? ` ${hint}` : ""}
    </p>
  );
}

function DaysBadge({ value }: { value: number | null }) {
  if (value == null) return null;
  const past = value < 0;
  const today = value === 0;
  const cls = past ? " days-past" : today ? " days-today" : "";
  const label = past
    ? `vor ${Math.abs(value)} Tagen`
    : today
      ? "heute"
      : `in ${value} Tagen`;
  return <span className={`days-badge${cls}`}>{label}</span>;
}

// Bezugsperiode der wiederkehrenden Kosten – normalisiert alte (Feld-Key) und
// neue (Perioden-Wert) Werte zu einer deutschen Bezeichnung.
const SOURCE_PERIOD_LABEL: Record<string, string> = {
  monthly: "monatlich",
  quarterly: "quartalsweise",
  semi_annual: "halbjährlich",
  annual: "jährlich",
  weekly: "wöchentlich",
  monthly_cost: "monatlich",
  quarterly_cost: "quartalsweise",
  semi_annual_cost: "halbjährlich",
  annual_cost: "jährlich",
  weekly_cost: "wöchentlich",
  maintenance_fee: "Wartungsgebühr",
};
function sourcePeriodLabel(p: string | null | undefined): string | null {
  if (!p) return null;
  return SOURCE_PERIOD_LABEL[p] ?? p;
}

// Wertebelegte Regel: Wenn Quellen-Nachweis existiert, ist der Wert klickbar
// (Evidence-First). Ohne Nachweis bleibt der Wert passiv (ggf. "Unbekannt").
interface EvidenceRuleProps {
  label: string;
  value: React.ReactNode;
  evidence: EvidenceRef | null;
  activeEvidenceId: string | null;
  onFocusEvidence: (ev: EvidenceRef) => void;
  review: boolean;
}

function EvidenceRule({
  label,
  value,
  evidence,
  activeEvidenceId,
  onFocusEvidence,
  review,
}: EvidenceRuleProps) {
  if (!evidence) {
    return (
      <div className="detail-rule fact-row">
        <dt>{label}</dt>
        {review && <span className="fact-review" title="Manuelle Prüfung erforderlich">Prüfen</span>}
        <dd className="fact-value-plain">{value}</dd>
      </div>
    );
  }

  const active = evidence.evidence_id === activeEvidenceId;
  const labelText = `${label} — Quelle öffnen`;

  return (
    <div className="detail-rule fact-row">
      <dt>{label}</dt>
      <dd>
        <button
          type="button"
          className={`fact-value-btn${active ? " active" : ""}`}
          aria-pressed={active}
          aria-label={labelText}
          title="Quelle im Original öffnen"
          onClick={() => onFocusEvidence(evidence)}
        >
          <span className="fact-value">{value}</span>
          <span className="fact-cite" aria-hidden="true">
            Quellenangabe
          </span>
        </button>
        {precisionHint(evidence) && (
          <span className="fact-precision">{precisionHint(evidence)}</span>
        )}
      </dd>
    </div>
  );
}

// Kompaktes Quellen-Link-Element (z. B. für Kosten-Bausteine der UAT-Re-Test-
// Kosten-Erklärung). Navigiert zu dem evidence-getragenen Beleg im Viewer.
function EvidenceLink({
  label,
  evidenceRef,
  evidence,
  onFocusEvidence,
}: {
  label: string;
  evidenceRef: string | null;
  evidence: EvidenceRef[];
  onFocusEvidence: (ev: EvidenceRef) => void;
}) {
  const ref = evidenceRef
    ? evidence.find((e) => e.field_ref === evidenceRef)
    : undefined;
  if (!ref) {
    return <span className="fact-cite">{label}</span>;
  }
  return (
    <button
      type="button"
      className="fact-cite-link"
      onClick={() => onFocusEvidence(ref)}
      title={ref.snippet || ""}
    >
      {label}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Importzustand (failure-safe): fehlgeschlagene Analysen bleiben sichtbar;
// der Vertrag bleibt als Platzhalter erhalten und kann erneut verarbeitet
// werden. Die Meldung kommt ausschließlich vom Backend (nie erfunden).
// ─────────────────────────────────────────────────────────────────────────
function ImportStateBanner({
  state,
  orgSlug,
  onReload,
}: {
  state: ImportStateDto;
  orgSlug: string;
  onReload?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<"ok" | "err" | null>(null);

  if (!state) return null;

  async function retry() {
    if (!state.document_version_id) return;
    setBusy(true);
    setMsg(null);
    try {
      await apiPost(
        `/api/documents/${encodeURIComponent(
          state.document_version_id
        )}/retry?organization_slug=${encodeURIComponent(orgSlug)}`,
        {}
      );
      setMsg("ok");
      onReload?.();
    } catch {
      setMsg("err");
    } finally {
      setBusy(false);
    }
  }

  if (state.import_state === "analysis_ok") return null;

  if (state.import_state === "analysis_failed" || state.import_state === "analysis_partial") {
    return (
      <section className="notice warning" role="alert">
        <strong>{state.state_label_de}.</strong>{" "}
        {state.message ?? "Die Analyse konnte nicht abgeschlossen werden."}
        {state.can_retry && (
          <button
            type="button"
            className="btn btn-sm retry"
            onClick={() => void retry()}
            disabled={busy}
          >
            {busy ? "Wird verarbeitet…" : "Erneut verarbeiten"}
          </button>
        )}
        {msg === "ok" && <span className="muted"> – erneuter Lauf gestartet.</span>}
        {msg === "err" && (
          <span className="muted"> – erneuter Lauf fehlgeschlagen.</span>
        )}
      </section>
    );
  }

  return (
    <section className="notice info" role="status">
      <strong>{state.state_label_de}:</strong> {state.message ?? "Wird verarbeitet."}
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Contract 360 – Workbench
// ─────────────────────────────────────────────────────────────────────────

export default function ContractDetail({ data, orgSlug, onReload }: Props) {
  const docs = useMemo(() => data.documents, [data.documents]);
  const evidence = useMemo(() => data.evidence, [data.evidence]);
  const viewerSectionRef = useRef<HTMLElement | null>(null);
  const archiveModalRef = useRef<HTMLDivElement | null>(null);

  const [activeVersionId, setActiveVersionId] = useState<string | null>(() => {
    const first = docs.find((d) => d.viewer_supported);
    return first?.document_version_id ?? null;
  });
  const [navTarget, setNavTarget] = useState<SourceNavigationTarget | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [archiveConfirm, setArchiveConfirm] = useState(false);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [archiveResult, setArchiveResult] = useState<"archive" | "unarchive" | null>(null);
  const archiveNavTimer = useRef<number | null>(null);
  const toast = useToast();
  const router = useRouter();

  useEffect(() => {
    return () => {
      if (archiveNavTimer.current != null) window.clearTimeout(archiveNavTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!archiveConfirm) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const selector =
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

    function focusFirstControl() {
      archiveModalRef.current?.querySelector<HTMLElement>(selector)?.focus();
    }

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setArchiveConfirm(false);
        return;
      }
      if (e.key !== "Tab") return;

      const controls = Array.from(
        archiveModalRef.current?.querySelectorAll<HTMLElement>(selector) ?? []
      );
      if (controls.length === 0) return;

      const first = controls[0];
      const last = controls[controls.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    focusFirstControl();
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus({ preventScroll: true });
    };
  }, [archiveConfirm]);

  const openArchiveDialog = () => {
    setArchiveError(null);
    setArchiveResult(null);
    setArchiveConfirm(true);
  };

  const runArchiveAction = async () => {
    if (archiveBusy || !data.contract_id) return;
    setArchiveBusy(true);
    setArchiveError(null);
    setArchiveResult(null);
    try {
      const action = data.is_archived ? "unarchive" : "archive";
      await apiPost(
        `/api/contracts/${data.contract_id}/${action}?organization_slug=${orgSlug}`,
        {}
      );
      setArchiveConfirm(false);
      setArchiveResult(data.is_archived ? "unarchive" : "archive");
      toast(
        data.is_archived
          ? "Vertrag wiederhergestellt."
          : "Vertrag archiviert.", "success"
      );
      if (data.is_archived) {
        // Wiederherstellen: auf der Seite bleiben und frisch laden.
        onReload?.();
      } else {
        // Archiviert: Erfolgsfeedback zeigen, dann ins Archiv navigieren.
        archiveNavTimer.current = window.setTimeout(() => {
          router.push("/archiv");
        }, 900);
      }
    } catch {
      // Fehler: Vertrag bleibt unveraendert, Fehler sichtbar, Retry ueber Dialog.
      setArchiveConfirm(false);
      setArchiveError(
        data.is_archived
          ? "Wiederherstellen fehlgeschlagen – der Vertrag bleibt archiviert."
          : "Archivieren fehlgeschlagen – der Vertrag bleibt im aktiven Portfolio."
      );
      toast(
        data.is_archived
          ? "Wiederherstellen fehlgeschlagen."
          : "Archivieren fehlgeschlagen.", "error"
      );
    } finally {
      setArchiveBusy(false);
    }
  };

  const activeDoc: DetailDocument | null =
    docs.find((d) => d.document_version_id === activeVersionId) ?? null;

  const handleSelectDoc = (doc: DetailDocument) => {
    setActiveVersionId(doc.document_version_id);
    setNavTarget(null);
    setActiveEvidenceId(null);
  };

  // Fakt fokussieren: Evidence in der Datenquelle auswaehlen + (wenn Seite
  // vorhanden) den Viewer zur Quelle navigieren. Ohne Seite KEIN Seiten-Sprung
  // und KEINE erfundene Hervorhebung – nur die Quelle auswaehlen.
  const handleFocusEvidence = (ev: EvidenceRef) => {
    setActiveEvidenceId(ev.evidence_id);
    if (ev.page == null) {
      // kein Seitenziel: Quelle im Panel markieren, Viewer unveraendert
      return;
    }
    const target: SourceNavigationTarget = {
      document_version_id: ev.document_version_id,
      page: ev.page,
      bbox: ev.bbox,
      bbox_space: ev.bbox_space,
      supports_exact_navigation: ev.supports_exact_navigation,
      label: `${ev.field_ref ?? "Quelle"} ${precisionHint(ev) ?? ""}`.trim(),
      field_ref: ev.field_ref,
      evidence_id: ev.evidence_id,
    };
    setNavTarget(target);
    if (ev.document_version_id) {
      const d = docs.find((x) => x.document_version_id === ev.document_version_id);
      if (d && d.viewer_supported) setActiveVersionId(d.document_version_id);
    }
    // Den PDF-Viewer ins Blickfeld bringen. Ohne Scroll bleibt der Nutzer bei
    // seinem aktuellen Seitenausschnitt und sieht die Quell-Navigation nicht.
    const viewerEl = viewerSectionRef.current;
    if (viewerEl && typeof viewerEl.scrollIntoView === "function") {
      viewerEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  const statusLabel = STATUS_LABEL_DETAIL[data.status ?? ""] ?? data.status ?? "Unbekannt";
  const riskLabel = RISK_LABEL_DETAIL[data.risk_level ?? ""] ?? data.risk_level ?? "Unbekannt";
  const needsReview = data.review.requires_manual_review;

  const identityEv = evidenceFor(evidence, ["identity", "dates"]);
  const datesEv = evidenceFor(evidence, ["dates", "termination"]);
  const financialEv = evidenceFor(evidence, ["costs", "payment"]);
  const scopeEv = evidenceFor(evidence, ["services", "identity"]);
  const slaEv = evidenceFor(evidence, ["sla"]);
  // UAT Re-Test (Defect 1): jeder Laufzeit-Fakt verlinkt seinen eigenen
  // kanonischen Beleg (z. B. dates.start_date auf p5), statt pauschal auf
  // dekorative Sammel-Refs (z. B. termination.evidence auf p3) zu zeigen.
  const startDateEv = evidenceFor(evidence, [
    data.dates.start_date_evidence ?? "dates.start_date",
  ]);
  const endDateEv = evidenceFor(evidence, [
    data.dates.documented_end_evidence ?? "dates.end_date",
  ]);
  const durationEv = evidenceFor(evidence, [
    data.dates.duration_evidence ?? "dates.duration",
  ]);
  const autoRenewalEv = evidenceFor(evidence, [
    data.dates.auto_renewal_evidence ?? "termination.auto_renewal",
  ]);
  const paymentStartEv = evidenceFor(evidence, [
    data.dates.payment_start_evidence ?? "payment.payment_start",
  ]);
  const minDurationEv = evidenceFor(evidence, [
    data.dates.minimum_duration_evidence ?? "dates.minimum_duration",
  ]);
  const tax = data.costs.tax_breakdown ?? EMPTY_TAX_BREAKDOWN;
  const taxEv = (key: string): EvidenceRef | null => {
    const ref = (tax.evidence_field_refs ?? {})[key];
    return ref ? evidenceFor(evidence, [ref]) : null;
  };
  const systemIdentity =
    typeof data.identity.system_identity === "string" &&
    data.identity.system_identity.trim() !== ""
      ? data.identity.system_identity
      : null;
  const systemIdentityEv = evidenceFor(evidence, ["identity.system_identity"]);

  const [reviewNavError, setReviewNavError] = useState<string | null>(null);

  // Öffnet die bestehende, vertragsbezogene Fakt-Prüfung (FactReviewPanel)
  // für DIESEN Vertrag: zum Panel scrollen und es auf Keyboard-Fokus setzen.
  const openReviewPanel = () => {
    setReviewNavError(null);
    const panel = document.getElementById("fact-review-panel");
    if (!panel) {
      // Nicht stillschweigend scheitern: ehrliche, sichtbare Meldung.
      setReviewNavError(
        "Prüfbereich konnte nicht geöffnet werden – bitte Seite neu laden und erneut versuchen."
      );
      return;
    }
    if (typeof panel.scrollIntoView === "function") {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    panel.focus({ preventScroll: true });
  };

  return (
    <div className="contract-360">
      <nav className="breadcrumb" aria-label="Brotkrumen">
        <Link href="/contracts">Verträge</Link>
        <span aria-hidden="true">/</span>
        <span>{data.contract_number ?? "Vertrag"}</span>
      </nav>

      {/* Kopf: Lieferant, Vertragsnummer, Status/Risiko/Review */}
      <header className="contract-detail-header">
        <div>
          <h1>{data.contract_title ?? data.contract_number ?? "Vertrag"}</h1>
          <p className="page-sub">
            {data.contract_number && <span>Nr. {data.contract_number}</span>}
            {data.contract_number && data.supplier && <span className="sep">·</span>}
            {data.supplier && <span>{data.supplier}</span>}
            {data.is_archived && data.archived_at && (
              <>
                <span className="sep">·</span>
                <span>Archiviert am {formatDate(data.archived_at)}</span>
              </>
            )}
          </p>
        </div>
        <div className="detail-badges">
          <span className={`badge badge-${data.status ?? "unknown"}`}>{statusLabel}</span>
          {data.risk_level && (
            <span className={`risk-badge risk-${data.risk_level}`}>{riskLabel}</span>
          )}
          {data.is_archived ? (
            <span className="badge badge-archived">Archiviert</span>
          ) : needsReview ? (
            <button
              type="button"
              className="review-badge review-badge--link"
              onClick={openReviewPanel}
              title="Manuelle Prüfung für diesen Vertrag öffnen"
            >
              Manuelle Prüfung
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-sm"
            onClick={openArchiveDialog}
            disabled={archiveBusy}
          >
            {archiveBusy
              ? "Wird…"
              : data.is_archived
                ? "Wiederherstellen"
                : "Archivieren"}
          </button>
        </div>
      </header>

      {archiveResult === "archive" && (
        <InlineAlert tone="success" role="status">
          Vertrag archiviert – wird ins Archiv verschoben…
        </InlineAlert>
      )}
      {archiveResult === "unarchive" && (
        <InlineAlert tone="success" role="status">
          Vertrag wiederhergestellt.
        </InlineAlert>
      )}

      {archiveError && (
        <InlineAlert
          tone="critical"
          role="alert"
          action={
            <button type="button" className="btn btn-sm" onClick={openArchiveDialog}>
              Erneut versuchen
            </button>
          }
        >
          {archiveError}
        </InlineAlert>
      )}

      {reviewNavError && (
        <InlineAlert
          tone="critical"
          role="alert"
          action={
            <button type="button" className="btn btn-sm" onClick={openReviewPanel}>
              Erneut versuchen
            </button>
          }
        >
          {reviewNavError}
        </InlineAlert>
      )}

      {archiveConfirm && (
        <div
          className="modal-overlay"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setArchiveConfirm(false);
          }}
        >
          <div
            ref={archiveModalRef}
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="archive-dialog-title"
          >
            <h3 id="archive-dialog-title">
              {data.is_archived ? "Vertrag wiederherstellen?" : "Vertrag archivieren?"}
            </h3>
            <p>
              <strong>Nr. {data.contract_number ?? "–"}</strong>
              {data.contract_title && <span> · {data.contract_title}</span>}
              {data.supplier && <span> · {data.supplier}</span>}
            </p>
            {!data.is_archived && (
              <p>
                Archivierung ist nicht-destruktiv: Vertrag, Belege,
                Review-Geschichte und Audit-Historie werden <strong>nicht</strong>{" "}
                gelöscht. Der Vertrag kann jederzeit aus dem Archiv
                wiederhergestellt werden.
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={() => setArchiveConfirm(false)}
                disabled={archiveBusy}
              >
                Abbrechen
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void runArchiveAction()}
                disabled={archiveBusy}
              >
                {archiveBusy
                  ? "Wird verarbeitet…"
                  : data.is_archived
                    ? "Wiederherstellen"
                    : "Vertrag archivieren"}
              </button>
            </div>
          </div>
        </div>
      )}

      {needsReview && (
        <section className="notice warning" role="alert">
          <strong>Manuelle Prüfung erforderlich.</strong>{" "}
          {data.review.review_reasons.length
            ? data.review.review_reasons.join(", ")
            : "Nicht alle Angaben sind eindeutig – bitte vor einer Entscheidung prüfen."}
        </section>
      )}

      <ImportStateBanner state={data.import_state} orgSlug={orgSlug} onReload={onReload} />

      {/* Kennzahlen-Überblick */}
      <section className="kpi-strip" aria-label="Wichtige Eckdaten">
        <div className="kpi">
          <span className="kpi-label">Status</span>
          <span className="kpi-value">{statusLabel}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Vertragsende</span>
          <span className="kpi-value">{formatDate(data.dates.calculated_end_date)}</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">
            Jährliche Kosten
            {tax.base_tax_basis === "net"
              ? " (Netto)"
              : tax.base_tax_basis === "gross"
                ? " (Brutto)"
                : ""}
          </span>
          <span className="kpi-value">
            {money(data.costs.annual_recurring)}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Kündigungsfrist</span>
          <span className="kpi-value">
            {formatDate(data.dates.latest_cancellation_date)}
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Risiko</span>
          <span className="kpi-value">{riskLabel}</span>
        </div>
      </section>

      <section className="detail-columns">
        <div className="detail-main">
          {/* Laufzeit & Kündigung */}
          <section className="detail-card" aria-label="Laufzeit und Kündigung">
            <h2>Laufzeit &amp; Kündigung</h2>
            <dl className="detail-rules">
              <EvidenceRule
                label="Beginn"
                value={
                  data.dates.overridden_start_date
                    ? formatDate(data.dates.overridden_start_date)
                    : data.dates.start_date_status === "event_based"
                      ? `nach Ereignis: ${data.dates.start_condition ?? "unbekannt"}`
                      : formatDate(data.dates.start_date)
                }
                evidence={datesEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={data.dates.review_required}
              />
              {startStatusLabel(data.dates.start_date_status) && (
                <Rule label="Beginn-Status">
                  {startStatusLabel(data.dates.start_date_status)}
                </Rule>
              )}
              {data.dates.start_condition && (
                <Rule label="Beginn-Bedingung">
                  <span className="muted">
                    Ereignisbasiert: {data.dates.start_condition}
                    {data.dates.overridden_start_date
                      ? " (tatsächliches Datum manuell übernommen)"
                      : " – tatsächliches Datum nach dem Ereignis eintragen"}
                  </span>
                </Rule>
              )}
{data.dates.documented_end_date && (
                <EvidenceRule
                  label="Vertragsende"
                  value={formatDate(data.dates.documented_end_date)}
                  evidence={endDateEv}
                  activeEvidenceId={activeEvidenceId}
                  onFocusEvidence={handleFocusEvidence}
                  review={false}
                />
              )}
              {data.dates.duration_years != null && (
                <EvidenceRule
                  label="Laufzeit"
                  value={`${data.dates.duration_years} Jahre`}
                  evidence={durationEv}
                  activeEvidenceId={activeEvidenceId}
                  onFocusEvidence={handleFocusEvidence}
                  review={false}
                />
              )}
              {data.dates.payment_start_rule && (
                <EvidenceRule
                  label="Zahlungsbeginn"
                  value={
                    <>
                      {data.dates.payment_start_rule}
                      {data.dates.payment_start_status === "condition_based" && (
                        <span className="muted">
                          {" "}
                          – tatsächliches Datum nach dem Ereignis eintragen
                        </span>
                      )}
                    </>
                  }
                  evidence={paymentStartEv}
                  activeEvidenceId={activeEvidenceId}
                  onFocusEvidence={handleFocusEvidence}
                  review={false}
                />
              )}
              {data.dates.minimum_duration_months != null && (
                <EvidenceRule
                  label="Mindestvertragslaufzeit"
                  value={`${data.dates.minimum_duration_months} Monate`}
                  evidence={minDurationEv}
                  activeEvidenceId={activeEvidenceId}
                  onFocusEvidence={handleFocusEvidence}
                  review={false}
                />
              )}
              <EvidenceRule
                label="Berechnetes Ende"
                value={formatDate(data.dates.calculated_end_date)}
                evidence={datesEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={data.dates.review_required}
              />
              <Rule label="Restlaufzeit bis Ende">
                <DaysBadge value={data.dates.days_until_end} />
              </Rule>
              <EvidenceRule
                label="Automatische Verlängerung"
                value={<YesNo v={data.dates.automatic_renewal} />}
                evidence={autoRenewalEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={data.dates.review_required}
              />
              <EvidenceRule
                label="Kündigungsfrist bis"
                value={formatDate(data.dates.latest_cancellation_date)}
                evidence={datesEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={data.dates.review_required}
              />
              <Rule label="Fristablauf in">
                <DaysBadge value={data.dates.days_until_latest_cancellation} />
              </Rule>
              <EvidenceRule
                label="Nächste Verlängerung"
                value={formatDate(data.dates.next_renewal_date)}
                evidence={datesEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={data.dates.review_required}
              />
              {!!data.dates.renewal_boundaries && data.dates.renewal_boundaries.length > 0 && (
                <Rule label="Verlängerungsperioden">
                  <span className="renewal-boundaries">
                    {data.dates.renewal_boundaries.map((b) => (
                      <span key={b.period_index} className="renewal-boundary">
                        <strong>P{b.period_index}</strong>
                        {formatDate(b.start_date)} – {formatDate(b.end_date)}
                        {b.review_required ? " (prüfen)" : ""}
                      </span>
                    ))}
                  </span>
                </Rule>
              )}
              <Rule label="Aktueller Status">
                {data.dates.current_status ?? <span className="muted">Unbekannt</span>}
              </Rule>
              {data.dates.current_status_explanation && (
                <Rule label="Erläuterung">{data.dates.current_status_explanation}</Rule>
              )}
            </dl>
            {(data.dates.calculated_end_basis?.explanation ||
              data.dates.latest_cancellation_basis?.explanation ||
              data.dates.next_renewal_basis?.explanation) && (
              <div className="detail-basis">
                <h3>Berechnungsgrundlage</h3>
                <BasisNote basis={data.dates.calculated_end_basis} />
                <BasisNote basis={data.dates.latest_cancellation_basis} />
                <BasisNote basis={data.dates.next_renewal_basis} />
              </div>
            )}
          </section>

          {/* Finanzielle Konditionen */}
          <section className="detail-card" aria-label="Finanzielle Konditionen">
            <h2>Finanzielle Konditionen</h2>
            <dl className="detail-rules">
              <EvidenceRule
                label="Jährlich wiederkehrend"
                value={money(data.costs.annual_recurring)}
                evidence={financialEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={false}
              />
              <EvidenceRule
                label="Monatlich wiederkehrend"
                value={money(data.costs.monthly_recurring)}
                evidence={financialEv}
                activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence}
                review={false}
              />
              {data.costs.source_period && (
                <Rule label="Bezugsperiode">{sourcePeriodLabel(data.costs.source_period)}</Rule>
              )}
              {data.costs.currency_conflict && (
                <Rule label="Währungskonflikt">
                  <span className="warn-text">Mehrere Währungen erkannt – prüfen</span>
                </Rule>
              )}
              {data.costs.tax_basis && (
                <Rule label="Steuerbasis">
                  {data.costs.tax_basis === "net"
                    ? "Netto (zzgl. USt.)"
                    : data.costs.tax_basis === "gross"
                      ? "Brutto (inkl. USt.)"
                      : data.costs.tax_basis}
                  {data.costs.tax_rate_percent != null
                    ? ` ${data.costs.tax_rate_percent} %`
                    : " – Steuersatz nicht belegt"}
                </Rule>
              )}
              {data.costs.total_contract_value_status && (
                <Rule label="Vertragswert-Status">
                  {data.costs.total_contract_value_status}
                </Rule>
              )}
            </dl>

            {/* Netto/Brutto/MwSt (UAT Defect Batch A + UAT Re-Test)
            Evidence-first: sind Netz/Opposition direkt im Vertrag belegt
            (Recovery aus dem persistierten Dokumenttext), sind die Zellen
            klickbar und springen zur Fundstelle (Seite 7). Ohne belegten
            Satz bleibt die Gegen-Basis ehrlich "Zu prüfen" – nie erfunden. */}
            <div className="detail-basis netto-brutto">
              <h3>Netto / MwSt. / Brutto</h3>
              <p className="fact-basis-note">
                Basis:{" "}
                <strong>
                  {tax.base_tax_basis === "net"
                    ? "Netto (zzgl. USt.)"
                    : tax.base_tax_basis === "gross"
                      ? "Brutto (inkl. USt.)"
                      : "Unbekannt"}
                </strong>
                {tax.rate_percent != null && ` · ${tax.rate_percent} % MwSt.`}
              </p>
              <dl className="netto-brutto-grid">
                <dt>Monatlich netto</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.monthly_net,
                    currency: tax.currency,
                    evidence: taxEv("monthly_net"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
                <dt>Monatlich MwSt.{tax.rate_percent != null ? ` (${tax.rate_percent} %)` : ""}</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.monthly_tax,
                    currency: tax.currency,
                    evidence: taxEv("monthly_vat"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
                <dt>Monatlich brutto</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.monthly_gross,
                    currency: tax.currency,
                    evidence: taxEv("monthly_gross"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
                <dt>Jährlich netto</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.annual_net,
                    currency: tax.currency,
                    evidence: taxEv("annual_net"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
                <dt>Jährlich MwSt.{tax.rate_percent != null ? ` (${tax.rate_percent} %)` : ""}</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.annual_tax,
                    currency: tax.currency,
                    evidence: taxEv("annual_vat"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
                <dt>Jährlich brutto</dt>
                <dd>
                  {moneyCellWithEvidence({
                    amount: tax.annual_gross,
                    currency: tax.currency,
                    evidence: taxEv("annual_gross"),
                    activeEvidenceId,
                    onFocusEvidence: handleFocusEvidence,
                  })}
                </dd>
              </dl>
              {tax.source && (
                <p className="fact-basis-note">
                  <span className="fact-basis-label">Herkunft:</span> {tax.source}{" "}
                  Jährliche Werte aus den monatlich belegten Beträgen abgeleitet (× 12).
                </p>
              )}
              {!tax.source && tax.explanation && (
                <p className="fact-basis-note">{tax.explanation}</p>
              )}
            </div>

            {/* Preisentwicklung / -fixierung (UAT Defect Batch A) */}
            {(data.costs.price_development ?? []).length > 0 && (
              <div className="detail-basis">
                <h3>Preisentwicklung / Preisfixierung</h3>
                <ul className="price-dev-list">
                  {(data.costs.price_development ?? []).map((pd) => {
                    const advisEv = evidenceFor(evidence, [
                      pd.evidence_field_ref ?? "termination.evidence",
                    ]);
                    return (
                      <li key={pd.key} className="price-dev-item">
                        <span className="cost-cat-label">{pd.label}</span>
                        {pd.period_years != null && (
                          <span className="price-fixed-duration">
                            Preisfixierung: {pd.period_years} Jahre
                          </span>
                        )}
                        {advisEv ? (
                          <button
                            type="button"
                            className="fact-value-btn"
                            onClick={() => handleFocusEvidence(advisEv)}
                          >
                            <span className="fact-value">„{pd.text}“</span>
                            <span className="fact-cite">Quellenangabe</span>
                          </button>
                        ) : (
                          <span className="fact-value">„{pd.text}“</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {data.costs.annual_recurring_basis?.explanation && (
              <div className="detail-basis">
                <h3>Berechnungsgrundlage</h3>
                <BasisNote basis={data.costs.annual_recurring_basis} />
              </div>
            )}
            {!!data.costs.category_totals && data.costs.category_totals.length > 0 && (
              <div className="cost-categories">
                <h3>Positionen</h3>
                <ul className="cost-category-list">
                  {data.costs.category_totals.map((cat) => (
                    <li key={cat.key}>
                      <span className="cost-cat-label">{cat.label}</span>
                      <span className="cost-cat-value">
                        {cat.amount != null && cat.currency
                          ? formatCurrency(String(cat.amount), cat.currency)
                          : <span className="muted">kein Wert</span>}
                      </span>
                      {cat.status === "not_calculable" && (
                        <span className="fact-review">nicht aggregierbar</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!!data.costs.notes && data.costs.notes.length > 0 && (
              <ul className="cost-notes">
                {data.costs.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
            {financialEv && financialEv.requires_review && (
              <p className="fact-review-note">
                Die Kostenangabe ist nicht eindeutig (widersprüchliche Belege) – bitte manuell prüfen.
              </p>
            )}
            {data.costs.availability && (
              <div className="detail-cost-availability" aria-label="Erklärung der Kostenverfügbarkeit">
                <h3>Warum die jährlichen Kosten nicht automatisch stehen</h3>
                <p className="cost-avail-summary">{data.costs.availability.summary_de}</p>
                {data.costs.availability.found_facts.length > 0 && (
                  <div className="cost-avail-facts">
                    <h4>Im Vertrag belegte Angaben</h4>
                    <ul className="cost-category-list">
                      {data.costs.availability.found_facts.map((f) => (
                        <li key={f.key}>
                          <span className="cost-cat-label">{f.label_de}</span>
                          <span className="cost-cat-value">{f.value}</span>
                          {f.page != null && (
                            <EvidenceLink
                              label={`Seite ${f.page}`}
                              evidenceRef={f.evidence_ref}
                              evidence={data.evidence}
                              onFocusEvidence={handleFocusEvidence}
                            />
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {data.costs.availability.missing_inputs.length > 0 && (
                  <div className="cost-avail-missing">
                    <h4>Fehlend für die Berechnung</h4>
                    <ul>
                      {data.costs.availability.missing_inputs.map((m, i) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Leistungsumfang */}
          <section className="detail-card" aria-label="Leistungsumfang">
            <h2>Leistungsumfang</h2>
            {data.scope.included_services.length > 0 && (
              <>
                <h3>Inklusive Leistungen</h3>
                <ul className="detail-tags">
                  {data.scope.included_services.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </>
            )}
            {data.scope.excluded_services.length > 0 && (
              <>
                <h3>Ausgeschlossene Leistungen</h3>
                <ul className="detail-tags">
                  {data.scope.excluded_services.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </>
            )}
            {(() => {
              const scopeStatus = data.scope.scope_status;
              if (scopeStatus && Object.keys(scopeStatus).length > 0) {
                return (
                  <dl className="detail-rules">
                    {SCOPE_STATUS_ORDER.filter((k) => k in scopeStatus).map((k) => {
                      const st = scopeStatus[k];
                      return (
                        <div className="detail-rule fact-row" key={k}>
                          <dt>{SCOPE_STATUS_LABELS[k] ?? k.replace(/_/g, " ")}</dt>
                          <dd>
                            <ScopeStatusValue
                              status={st.status}
                              evidenceRef={st.evidence_ref ?? null}
                              evidence={data.evidence}
                              onFocusEvidence={handleFocusEvidence}
                            />
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                );
              }
              return (
                <dl className="detail-rules">
                  {data.scope.maintenance != null && (
                    <EvidenceRule label="Wartung" value={<YesNo v={data.scope.maintenance} />}
                      evidence={scopeEv} activeEvidenceId={activeEvidenceId}
                      onFocusEvidence={handleFocusEvidence} review={false} />
                  )}
                  {data.scope.inspection != null && (
                    <EvidenceRule label="Inspektion" value={<YesNo v={data.scope.inspection} />}
                      evidence={scopeEv} activeEvidenceId={activeEvidenceId}
                      onFocusEvidence={handleFocusEvidence} review={false} />
                  )}
                  {data.scope.repair != null && (
                    <EvidenceRule label="Reparatur" value={<YesNo v={data.scope.repair} />}
                      evidence={scopeEv} activeEvidenceId={activeEvidenceId}
                      onFocusEvidence={handleFocusEvidence} review={false} />
                  )}
                  {data.scope.calibration != null && (
                    <Rule label="Kalibrierung"><YesNo v={data.scope.calibration} /></Rule>
                  )}
                  {data.scope.software_updates != null && (
                    <Rule label="Software-Updates"><YesNo v={data.scope.software_updates} /></Rule>
                  )}
                  {data.scope.remote_support != null && (
                    <Rule label="Remote-Support"><YesNo v={data.scope.remote_support} /></Rule>
                  )}
                  {data.scope.technical_support != null && (
                    <Rule label="Technischer Support"><YesNo v={data.scope.technical_support} /></Rule>
                  )}
                  {data.scope.spare_parts_included != null && (
                    <Rule label="Ersatzteile inklusive"><YesNo v={data.scope.spare_parts_included} /></Rule>
                  )}
                  {data.scope.consumables_included != null && (
                    <Rule label="Verbrauchsmaterial inklusive"><YesNo v={data.scope.consumables_included} /></Rule>
                  )}
                  {data.scope.emergency_service != null && (
                    <Rule label="Notdienst"><YesNo v={data.scope.emergency_service} /></Rule>
                  )}
                </dl>
              );
            })()}
            {data.scope.note_de && (
              <p className="fact-basis-note">{data.scope.note_de}</p>
            )}
          </section>

          {/* SLA */}
          <section className="detail-card" aria-label="Service-Level">
            <h2>Service-Level (SLA)</h2>
            <dl className="detail-rules">
              <EvidenceRule label="Reaktionszeit" value={data.sla.response_time ?? <span className="muted">Unbekannt</span>}
                evidence={slaEv} activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence} review={false} />
              <EvidenceRule label="Behebungszeit" value={data.sla.resolution_time ?? <span className="muted">Unbekannt</span>}
                evidence={slaEv} activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence} review={false} />
              <EvidenceRule label="Verfügbarkeit 24/7" value={<YesNo v={data.sla.availability_24_7} />}
                evidence={slaEv} activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence} review={false} />
              {data.sla.service_hours && <Rule label="Servicezeiten">{data.sla.service_hours}</Rule>}
              {data.sla.emergency_availability && (
                <Rule label="Notfall-Erreichbarkeit">{data.sla.emergency_availability}</Rule>
              )}
              {data.sla.sla_notes && <Rule label="Anmerkungen">{data.sla.sla_notes}</Rule>}
            </dl>
          </section>

          {/* Geräte / Equipment (PR-4: Abdeckung, Review, Quellen-Navigation) */}
          {data.equipment.length > 0 && (
            <section className="detail-card" aria-label="Geräte und Leistungsabdeckung">
              <h2>Geräte &amp; Leistungsabdeckung</h2>
              {systemIdentity && (
                <p className="equipment-system">
                  <strong>System (aus Vertrag):</strong> {systemIdentity}
                  {systemIdentityEv && systemIdentityEv.page != null && (
                    <EvidenceLink
                      label={`Seite ${systemIdentityEv.page}`}
                      evidenceRef={systemIdentityEv.field_ref ?? null}
                      evidence={data.evidence}
                      onFocusEvidence={handleFocusEvidence}
                    />
                  )}
                </p>
              )}
              <ul className="equipment-list">
                {data.equipment.map((e, i) => {
                  const eqEv = e.field_ref
                    ? evidenceFor(evidence, [e.field_ref])
                    : null;
                  const active =
                    activeEvidenceId != null &&
                    eqEv != null &&
                    eqEv.evidence_id === activeEvidenceId;
                  return (
                    <li key={e.id || i} className="equipment-item">
                      <div className="equipment-head">
                        {eqEv ? (
                          <button
                            type="button"
                            className={`equipment-name-btn${active ? " active" : ""}`}
                            aria-pressed={active}
                            aria-label={`${e.device_name ?? e.system_name ?? "Gerät"} — Quelle öffnen`}
                            onClick={() => handleFocusEvidence(eqEv)}
                          >
                            <span className="equipment-name">
                              {e.device_name ?? e.system_name ?? "Gerät"}
                            </span>
                            <span className="fact-cite" aria-hidden="true">
                              Quellenangabe
                            </span>
                          </button>
                        ) : (
                          <span className="equipment-name">
                            {e.device_name ?? e.system_name ?? "Gerät"}
                          </span>
                        )}
                        {e.identification_quality && (
                          <span className={`fact-review${e.requires_review ? "" : " ok"}`}>
                            {identificationQualityLabel(e.identification_quality)}
                          </span>
                        )}
                        {e.requires_review && (
                          <span className="fact-review">Zu prüfen</span>
                        )}
                      </div>
                      <div className="muted">
                        {[e.manufacturer, e.model, e.serial_number ? `SN: ${e.serial_number}` : null]
                          .filter(Boolean)
                          .join(" · ") || "Keine Details"}
                      </div>
                      {e.relationship_quality && (
                        <div className="muted">
                          Zuordnung: {relationshipQualityLabel(e.relationship_quality)}
                        </div>
                      )}
                      {(e.coverage_start || e.coverage_end) && (
                        <div className="muted">
                          Abdeckung: {formatDate(e.coverage_start)} – {formatDate(e.coverage_end)}
                        </div>
                      )}
                      {e.service_scope && (
                        <div className="muted">Leistungsumfang: {e.service_scope}</div>
                      )}
                      {e.included_services && e.included_services.length > 0 && (
                        <div className="tag-row">
                          {e.included_services.map((s) => (
                            <span key={s} className="detail-tag">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                      {e.sla_notes && <div className="muted">SLA: {e.sla_notes}</div>}
                      {e.requires_review && e.review_reasons.length > 0 && (
                        <ul className="review-list">
                          {e.review_reasons.map((r) => (
                            <li key={r} className="muted">
                              {r}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {/* Handlungsbedarf (PR-4 Arbeitspunkte) */}
          {(data.work_items?.length ?? 0) > 0 && (
            <section className="detail-card" aria-label="Handlungsbedarf">
              <h2>Handlungsbedarf</h2>
              <ul className="detail-warnings">
                {data.work_items.map((w) => (
                  <li key={w.work_item_id} className={`warning-${w.severity}`}>
                    <span className={`severity-tag severity-${w.severity}`}>
                      {SEVERITY_LABEL[w.severity] ?? w.severity}
                    </span>
                    <span>
                      <span className="wi-type">{workItemTypeLabel(w.item_type)}</span>{" "}
                      — {w.title_de}
                    </span>
                    {w.target_date && (
                      <span className="muted">
                        {formatDate(w.target_date)}{" "}
                        {formatDaysRemaining(w.days_remaining)}
                      </span>
                    )}
                    <span className="muted">
                      Status: {workItemStatusLabel(w.status)}
                    </span>
                    {w.requires_review && (
                      <span className="fact-review">Zu prüfen</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Warnungen & Handlungsbedarf */}
          {data.warnings.length > 0 && (
            <section className="detail-card" aria-label="Warnungen und Handlungsbedarf">
              <h2>Warnungen &amp; Handlungsbedarf</h2>
              <ul className="detail-warnings">
                {data.warnings.map((w) => (
                  <li key={w.warning_type} className={`warning-${w.severity}`}>
                    <span className={`severity-tag severity-${w.severity}`}>
                      {SEVERITY_LABEL[w.severity] ?? w.severity}
                    </span>
                    <span>{w.title_de}</span>
                    {w.target_date && (
                      <span className="muted">
                        {formatDate(w.target_date)}{" "}
                        {formatDaysRemaining(w.days_remaining)}
                      </span>
                    )}
                    {w.requires_review && (
                      <span className="fact-review">Zu prüfen</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Identität */}
          <section className="detail-card" aria-label="Identität">
            <h2>Identität</h2>
            <dl className="detail-rules">
              <EvidenceRule label="Lieferant" value={data.supplier ?? <span className="muted">Unbekannt</span>}
                evidence={identityEv} activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence} review={false} />
              <EvidenceRule label="Vertragsnummer" value={data.contract_number ?? <span className="muted">Unbekannt</span>}
                evidence={identityEv} activeEvidenceId={activeEvidenceId}
                onFocusEvidence={handleFocusEvidence} review={false} />
              {Object.entries(data.identity).map(([k, v]) => {
                if (k === "contract_number") return null; // bereits oben gezeigt
                return (
                  <Rule key={k} label={IDENTITY_LABELS[k] ?? k.replace(/_/g, " ")}>
                    {String(v)}
                  </Rule>
                );
              })}
            </dl>
          </section>

          {/* Bestätigen & Überschreiben (UAT Defect Batch A) */}
          {onReload && (
            <OverridePanel data={data} orgSlug={orgSlug} onReload={onReload} />
          )}

          {/* Faktgenaue menschliche Prüfung (Customer-Demo-Readiness) */}
          {onReload && (
            <FactReviewPanel
              data={data}
              orgSlug={orgSlug}
              onReload={onReload}
              onNavigate={handleFocusEvidence}
            />
          )}
        </div>

        <aside className="detail-aside">
          <section className="detail-card" aria-label="Quelldokumente">
            <h2>Quelldokumente</h2>
            <div className="source-list">
              {docs.length === 0 && (
                <p className="muted">Keine Quelldokumente verknüpft.</p>
              )}
              {docs.map((d) => (
                <SourceLink
                  key={d.document_version_id}
                  document={d}
                  active={d.document_version_id === activeVersionId}
                  onSelect={handleSelectDoc}
                />
              ))}
            </div>
          </section>

          <section className="detail-card" aria-label="Quellenangaben">
            <h2>Quellenangaben</h2>
            <EvidencePane
              evidence={data.evidence}
              activeEvidenceId={activeEvidenceId}
              onNavigate={handleFocusEvidence}
            />
          </section>
        </aside>
      </section>

      <section
        className="detail-viewer"
        aria-label="Quelle anzeigen"
        ref={viewerSectionRef}
      >
        <h2>Quelle anzeigen</h2>
        <PdfViewer
          contractId={data.contract_id}
          orgSlug={orgSlug}
          documentVersionId={activeVersionId}
          active={activeDoc?.viewer_supported === true}
          navTarget={navTarget}
        />
      </section>
    </div>
  );
}
