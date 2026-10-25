"use client";

import StatusBadge from "@/components/ui/StatusBadge";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import { useSearchParams } from "next/navigation";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { loadAllPartners } from "@/components/master-data/definitions/partners";
import { QuickCreatePartner } from "@/components/master-data/lazy";
import { REGISTER_CHANGED_EVENT } from "@/lib/register-events";
import ContractRulesSection from "./ContractRulesSection";
import ContractAccessCard, { type AccessChanges } from "./ContractAccessCard";
import ContractRetentionCard from "./ContractRetentionCard";
import type { FormValues } from "@/components/master-data/types";
import MissingList from "@/components/ui/MissingList";
import PartnerSuggestions from "@/components/master-data/PartnerSuggestions";
import { levelOf } from "@/lib/field-review";
import RequiredBadge from "./RequiredBadge";
import FieldSuggestion, { type SuggestionKind } from "./FieldSuggestion";
import type { FieldReviewFieldDto } from "@/lib/contract-detail-types";
import AiOrigin from "@/components/ui/AiOrigin";
import Signal, { SignalIcon } from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { useSaveShortcut, useUnsavedChanges } from "@/components/ui/useFormGuards";
import { formatDate } from "@/lib/format";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import {
  listContractTypes,
  listLookups,
  type ContractCategoryDto,
  type ContractTypeDto,
  type LookupDto,
  type PartnerDto,
} from "@/lib/domain-api/catalogs";
import {
  BUSINESS_STATUS_LABEL,
  BUSINESS_STATUS_TONE,
  DURATION_UNIT_LABEL,
  NOTICE_TO_LABEL,
  ORIGIN_LABEL,
  TERM_MODEL_LABEL,
  acceptRegisterProposal,
  dismissRegisterProposal,
  changeContractStatus,
  getContractRegister,
  getPartnerPrefill,
  updateContractConfidentiality,
  updateContractRegister,
  type BusinessStatus,
  type ContractRegister,
  type DurationUnit,
  type NoticeTo,
  type RegisterField,
  type RegisterValue,
  type TermModel,
} from "@/lib/domain-api/register";
import { PRICE_ADJUSTMENT_LABEL } from "@/lib/domain-api/finance";
import { usePermissions } from "@/lib/use-permissions";
import { FIELD_PARAM, REVIEW_TARGET, baseFieldKey, contractHref } from "@/lib/fix-targets";
import Link from "next/link";
import ActionMenu from "@/components/ui/ActionMenu";
import { revealBox } from "@/lib/box-collapse";

type Draft = Record<string, RegisterValue>;
/** Laufzeitart → die Prüf-Angabe, aus der sie abgeleitet ist (für die KI-Plakette). */
const TERM_MODEL_FACT: Record<string, string> = {
  fixed_term: "dates.duration", terminable: "termination.cancellation_period", terminable_min_term: "dates.minimum_duration",
  auto_renewal: "termination.auto_renewal", perpetual: "dates.duration",
};
type FieldKind = "text" | "textarea" | "bool" | "date" | "int" | "decimal" | "period" | "term_model" | "notice_to" | "price_adjustment" | "partner" | "type" | "category" | "account" | "storage" | "auto_number";
type FieldDef = { key: string; kind: FieldKind };

const PERIODS = ["initial_term", "minimum_term", "notice_period", "renewal_period"] as const;

// „data“ = Reiter Vertragsdaten (was der Vertrag ist), „deadlines“ = Reiter Fristen & Aufgaben (was zu tun ist),
/** data = Vertragsdaten, deadlines = Fristen & Aufgaben, status = Karte „Vertragsstatus“ auf der Übersicht. */
export type RegisterView = "data" | "deadlines" | "status";

const svgIcon = (body: ReactNode) => <svg viewBox="0 0 24 24" focusable="false">{body}</svg>;
// Kachel je Kasten: Symbol + Kennfarbe der Art von Angabe (dekorativ, nie ein Zustand).
const SECTION_ICONS: Record<string, { icon: ReactNode; tile: string }> = {
  identity: { icon: svgIcon(<><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></>), tile: "section-tile--partner" },
  term: { icon: svgIcon(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>), tile: "section-tile--type" },
  organisation: { icon: svgIcon(<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />), tile: "section-tile--cost" },
  price: { icon: svgIcon(<path d="M4 17l6-6 4 4 6-7M15 8h5v5" />), tile: "section-tile--cost" },
  service: { icon: svgIcon(<><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" /></>), tile: "section-tile--device" },
};
// Gruppen im Kasten „Vertrag & Partner“: wie in der Organisationszuordnung links Titel + Zweck, rechts die Angaben.
const REGISTER_GROUPS: Record<string, { id: string; title: string; intro: string; icon: ReactNode; tile: string; keys: string[] }[]> = {
  identity: [
    { id: "contract", title: "Vertrag", intro: "Titel, Gegenstand und interne Nummer des Vertrags.", tile: "type",
      icon: svgIcon(<><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></>),
      keys: ["contract_title", "subject_text", "short_description", "register_number"] },
    { id: "partner", title: "Partner", intro: "Mit wem der Vertrag geschlossen ist und ob er Teil eines Rahmenvertrags ist.", tile: "partner",
      icon: svgIcon(<><circle cx="9" cy="8" r="3.2" /><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 5.5a3 3 0 0 1 0 5.8M18 14.5c1.8.8 3 2.7 3 5.5" /></>),
      keys: ["partner_id", "is_framework"] },
    { id: "class", title: "Einordnung", intro: "Art und Kategorie bestimmen Fristenregeln und Auswertungen.", tile: "device",
      icon: svgIcon(<><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></>),
      keys: ["contract_type_id", "contract_category_id"] },
    { id: "maintenance", title: "Wartung", intro: "Wie oft gewartet wird; daraus entsteht „Wartung fällig“ in Fristen & Aufgaben.", tile: "device",
      icon: svgIcon(<><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z" /></>),
      keys: ["maintenance_next_date", "maintenance_interval_months"] },
  ],
  term: [
    { id: "kind", title: "Vertragsart & Beginn", intro: "Wie der Vertrag läuft und wann er beginnt.", tile: "type",
      icon: svgIcon(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>),
      keys: ["term_model", "term_start_date"] },
    { id: "span", title: "Laufzeit & Ende", intro: "Wie lange der Vertrag läuft und wann er endet.", tile: "device",
      icon: svgIcon(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
      keys: ["term_fixed_end_date", "initial_term", "minimum_term"] },
    { id: "notice", title: "Kündigung & Verlängerung", intro: "Wann und wie gekündigt oder verlängert wird.", tile: "partner",
      icon: svgIcon(<><path d="M5 4h14v16H5z" /><path d="M9 9h6M9 13h4" /></>),
      keys: ["notice_period", "notice_to", "renewal_period"] },
  ],
  organisation: [
    { id: "storage", title: "Ablage", intro: "Wo das Original liegt.", tile: "cost",
      icon: svgIcon(<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />),
      keys: ["storage_location_code"] },
    { id: "billing", title: "Abrechnung", intro: "Konto und Abrechnungsart.", tile: "cost",
      icon: svgIcon(<><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M3 10h18M7 15h3" /></>),
      keys: ["account_number", "manual_billing"] },
  ],
  price: [
    { id: "adjustment", title: "Art & Höhe", intro: "Wie sich der Preis ändert.", tile: "cost",
      icon: svgIcon(<path d="M4 17l6-6 4 4 6-7M15 8h5v5" />),
      keys: ["price_adjustment_kind", "price_adjustment_percent", "price_adjustment_index_name"] },
    { id: "schedule", title: "Zeitplan", intro: "Wann die nächste Anpassung kommt.", tile: "type",
      icon: svgIcon(<><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>),
      keys: ["price_adjustment_next_date", "price_adjustment_interval_months"] },
  ],
};

function RegisterGroup({ id, title, intro, icon, tile, children }: { id: string; title: string; intro: string; icon: ReactNode; tile: string; children: ReactNode }) {
  return <section className="cw-og" aria-labelledby={id}>
    <div className="cw-og-intro">
      <span className={`cw-og-tile cw-og-tile--${tile}`} aria-hidden="true"><span className="cw-og-icon">{icon}</span></span>
      <div><h3 id={id}>{title}</h3><p>{intro}</p></div>
    </div>
    <div className="cw-og-body">{children}</div>
  </section>;
}
const STATUS_ICON = svgIcon(<path d="M5 21V4h11l-1.5 4L16 12H5" />);

const SECTIONS: { id: string; title: string; description: string; fields: FieldDef[]; view?: RegisterView }[] = [
  {
    id: "identity",
    title: "Vertrag & Partner",
    description: "Vertragstitel, Vertragspartner und Einordnung",
    fields: [
      { key: "contract_title", kind: "text" },
      { key: "short_description", kind: "text" },
      // Interne Nummer = automatisch vergebene, eindeutige Vertragsnummer (Nummernkreis), nie von Hand.
      { key: "register_number", kind: "auto_number" },
      { key: "partner_id", kind: "partner" },
      { key: "contract_type_id", kind: "type" },
      { key: "contract_category_id", kind: "category" },
      { key: "is_framework", kind: "bool" },
      { key: "subject_text", kind: "textarea" },
      // Wartung, nur bei Verträgen mit Wartung: daraus entsteht „Wartung fällig“ in Fristen & Aufgaben.
      { key: "maintenance_next_date", kind: "date" },
      { key: "maintenance_interval_months", kind: "int" },
    ],
  },
  {
    id: "term",
    title: "Laufzeit, Fristen & Kündigung",
    description: "Vertragslaufzeit und die daraus berechneten Fristen",
    fields: [
      { key: "term_model", kind: "term_model" },
      { key: "term_start_date", kind: "date" },
      { key: "term_fixed_end_date", kind: "date" },
      { key: "initial_term", kind: "period" },
      { key: "notice_period", kind: "period" },
      { key: "notice_to", kind: "notice_to" },
      { key: "minimum_term", kind: "period" },
      { key: "renewal_period", kind: "period" },
    ],
  },
  {
    id: "organisation",
    title: "Ablage & Abrechnung",
    description: "Original, Konto und Abrechnungsart",
    fields: [
      { key: "storage_location_code", kind: "storage" },
      { key: "account_number", kind: "text" },
      { key: "manual_billing", kind: "bool" },
    ],
  },
  {
    id: "price",
    title: "Preisanpassung",
    description: "Grundlage für die Hochrechnung künftiger Kosten in den Finanzdaten",
    fields: [
      { key: "price_adjustment_kind", kind: "price_adjustment" },
      { key: "price_adjustment_percent", kind: "decimal" },
      { key: "price_adjustment_index_name", kind: "text" },
      { key: "price_adjustment_next_date", kind: "date" },
      { key: "price_adjustment_interval_months", kind: "int" },
    ],
  },
];
// Nicht in diesen Kästen: Kündigungsdaten setzt nur der Statuswechsel („Gekündigt“), die Aufbewahrung
// pflegt „Aufbewahrung & Löschung“, Datenschutz „Zugriff & Datenschutz“ (je eine Stelle).
const RETENTION_KEYS = new Set(["retention_years_after_end"]);
const ACCESS_KEYS = new Set(["data_protection_relevant"]);
const TERMINATION_KEYS = new Set(["terminated_on", "terminated_effective"]);

// Karte „Vertragsstatus“: der normale Weg eines Vertrags (Storniert liegt daneben).
const STATUS_PATH = ["in_arbeit", "gueltig", "gekuendigt", "beendet"] as const;
const STEP_CHECK = <svg viewBox="0 0 24 24" focusable="false"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
const dateOf = (value: RegisterValue | undefined) => (value ? formatDate(String(value)) : null);

/** Was der Status bedeutet und was als Nächstes zu tun ist. */
const STATUS_STAGE: Partial<Record<BusinessStatus, { title: (r: ContractRegister) => string; text: (r: ContractRegister) => string }>> = {
  in_arbeit: {
    title: (r) => (r.missing_for_valid.length ? "In Arbeit – noch nicht freigegeben" : "Bereit zur Freigabe"),
    text: (r) => (r.missing_for_valid.length
      ? `Für „Gültig“ fehlen noch ${r.missing_for_valid.length} ${r.missing_for_valid.length === 1 ? "Angabe" : "Angaben"}. Erst danach werden Fristen und Kosten überwacht.`
      : "Alle Pflichtangaben sind da. Mit „Gültig“ beginnt die Überwachung von Fristen, Erinnerungen und Kosten."),
  },
  gueltig: {
    title: () => "Gültig – läuft",
    text: (r) => `Fristen und Erinnerungen werden überwacht${r.terms.cancel_by ? ` · kündbar bis ${formatDate(r.terms.cancel_by)}` : ""}${r.terms.actual_end ?? r.terms.possible_end ? ` · Vertragsende ${formatDate((r.terms.actual_end ?? r.terms.possible_end)!)}` : ""}. Kündigung versendet? Hier erfassen, damit die Überwachung zum richtigen Tag endet.`,
  },
  gekuendigt: {
    title: (r) => `Gekündigt${r.fields.terminated_effective?.value ? ` zum ${dateOf(r.fields.terminated_effective.value)}` : ""}`,
    text: () => "Bis zum Vertragsende laufen Kosten und Termine weiter. Danach den Vertrag als beendet markieren.",
  },
  beendet: {
    title: (r) => `Beendet${r.ended_on ? ` am ${formatDate(r.ended_on)}` : ""}`,
    text: () => "Keine Fristen mehr. Aufbewahrung und Löschprüfung laufen weiter.",
  },
  geloescht: {
    title: () => "Storniert",
    text: () => "Der Vertrag ist als ungültig markiert und zählt in keiner Auswertung. Die Daten bleiben erhalten.",
  },
};

/** Beschriftung eines Statuswechsels als Handlung. */
function transitionLabel(target: BusinessStatus, current: BusinessStatus): string {
  if (current === "geloescht") return `Stornierung aufheben (→ ${BUSINESS_STATUS_LABEL[target]})`;
  if (target === "gueltig") return current === "in_arbeit" ? "Als gültig freigeben" : "Wieder auf „Gültig“ setzen";
  if (target === "gekuendigt") return "Kündigung erfassen";
  if (target === "beendet") return "Als beendet markieren";
  if (target === "geloescht") return "Stornieren";
  if (target === "in_arbeit") return "Zurück auf „In Arbeit“";
  return `Auf „${BUSINESS_STATUS_LABEL[target]}“ setzen`;
}

/** Datum bzw. Hinweis unter einer Stufe (nur gepflegte bzw. berechnete Werte). */
function stepNote(step: (typeof STATUS_PATH)[number], state: string, r: ContractRegister): string {
  if (step === "gekuendigt") {
    if (state !== "todo") return [dateOf(r.fields.terminated_on?.value) ? `am ${dateOf(r.fields.terminated_on?.value)}` : null, dateOf(r.fields.terminated_effective?.value) ? `zum ${dateOf(r.fields.terminated_effective?.value)}` : null].filter(Boolean).join(" · ");
    return r.terms.cancel_by ? `kündbar bis ${formatDate(r.terms.cancel_by)}` : "";
  }
  if (step === "beendet") {
    if (state !== "todo") return r.ended_on ? `am ${formatDate(r.ended_on)}` : "";
    const end = r.terms.actual_end ?? r.terms.possible_end;
    return end ? `Vertragsende ${formatDate(end)}` : "";
  }
  if (step === "in_arbeit" && state === "current" && r.missing_for_valid.length) return `${r.missing_for_valid.length} Angaben fehlen`;
  return "";
}

const CALC_ICON = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 12h2M14 12h2M8 16h2M14 16h2" /></svg>;
const FLAG_ICON = <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="signal-icon"><path d="M5 21V4h11l-1.5 4L16 12H5" /></svg>;

// Kurze Erklaerungen fuer schwierige Felder (nur im Bearbeitungsmodus sichtbar).
const FIELD_HELP: Record<string, string> = {
  term_model: "Bestimmt, wie Fristen berechnet werden: Eine feste Laufzeit endet von selbst, kündbare Verträge laufen bis zur Kündigung, bei automatischer Verlängerung verlängert sich der Vertrag ohne Kündigung.",
  notice_period: "Wie lange vor dem Kündigungstermin die Kündigung beim Vertragspartner eingegangen sein muss.",
  notice_to: "Zu welchem Termin gekündigt werden kann – z. B. „zum Quartalsende“ = 31.03., 30.06., 30.09. oder 31.12.",
  minimum_term: "Frühestens nach dieser Zeit ist eine Kündigung wirksam.",
  renewal_period: "Um wie viel sich der Vertrag ohne Kündigung jeweils verlängert.",
  maintenance_next_date: "Ein Monat vorher entsteht der Termin „Wartung fällig“ unter Fristen & Aufgaben.",
  maintenance_interval_months: "Wie oft gewartet wird. Leer = einmaliger Termin; sonst entsteht nach „Erledigt“ der nächste Termin.",
};

const TERM_FIELDS: Record<TermModel, string[]> = {
  fixed_term: ["term_model", "term_start_date", "term_fixed_end_date", "initial_term"],
  terminable: ["term_model", "term_start_date", "notice_period", "notice_to"],
  terminable_min_term: ["term_model", "term_start_date", "minimum_term", "notice_period", "notice_to"],
  auto_renewal: ["term_model", "term_start_date", "term_fixed_end_date", "initial_term", "notice_period", "notice_to", "renewal_period"],
  perpetual: ["term_model", "term_start_date"],
};

const TERM_SECTION_KEYS = new Set(SECTIONS.find((section) => section.id === "term")!.fields.map((def) => def.key));


const PERIOD_LABEL: Record<(typeof PERIODS)[number], string> = {
  initial_term: "Laufzeit",
  minimum_term: "Mindestlaufzeit",
  notice_period: "Kündigungsfrist",
  renewal_period: "Verlängerung um",
};

// Tage zwischen zwei ISO-Daten (ohne Uhrzeit, unabhängig von der Zeitzone).
function daysBetween(from: string, to: string) {
  return Math.round((Date.UTC(+to.slice(0, 4), +to.slice(5, 7) - 1, +to.slice(8, 10)) - Date.UTC(+from.slice(0, 4), +from.slice(5, 7) - 1, +from.slice(8, 10))) / 86_400_000);
}

function fieldKeys(def: FieldDef): string[] {
  return def.kind === "period" ? [`${def.key}_value`, `${def.key}_unit`] : [def.key];
}

function same(left: RegisterValue | undefined, right: RegisterValue | undefined) {
  return (left ?? null) === (right ?? null);
}

function draftFrom(register: ContractRegister): Draft {
  const draft: Draft = {};
  for (const [key, field] of Object.entries(register.fields)) draft[key] = field.value;
  return draft;
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export default function ContractRegisterPanel({ contractId, orgSlug, onChanged, searchableKeys, onSearchInDocument, onShowSource, reviewFields, hiddenSections, afterStatus, view = "data", onOpenField, onOpenStatus }: {
  contractId: string;
  /** Welche Kästen: Vertragsdaten (Standard, mit Status, Regeln, KI-Vorschlägen) oder Fristen & Aufgaben (Erinnerungen). */
  view?: RegisterView;
  /** Feld, das auf dem anderen Reiter steht (z. B. „Erinnerung an“ aus „Für Gültig fehlen“). */
  onOpenField?: (key: string, view: RegisterView) => void;
  /** Statuswechsel steht auf der Übersicht (Karte „Vertragsstatus“): dorthin springen. */
  onOpenStatus?: () => void;
  /** Oben in den Vertragsdaten (Organisationszuordnung). */
  afterStatus?: ReactNode;
  /** Kästen, die der Vertragstyp nicht vorsieht; sie bleiben sichtbar, sobald ein Wert gepflegt ist. */
  hiddenSections?: Set<string>;
  orgSlug: string;
  onChanged?: () => void;
  /** Felder, die im Vertragsdokument gesucht werden können (erneute Erfassung). */
  searchableKeys?: Set<string>;
  onSearchInDocument?: (key: string) => void;
  /** Fundstelle eines aus dem Dokument übernommenen Werts zeigen. */
  onShowSource?: (source: { document_version_id: string; page: number; quote: string }) => void;
  /** Vertragsdaten-Feld -> zugehörige Prüf-Angabe (für Felder ohne eigene KI-Herkunft, z. B. Vertragspartner). */
  reviewFields?: FieldReviewFieldDto[];
}) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const toast = useToast();
  const isAdmin = Boolean(account?.is_developer || role === "admin");
  const [register, setRegister] = useState<ContractRegister | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  // Bearbeitet wird je Kasten (Vertrag & Partner, Laufzeit …); mehrere können offen sein,
  // „Speichern“ speichert alle offenen Änderungen, „Abbrechen“ verwirft die des Kastens.
  const [editSections, setEditSections] = useState<Set<string>>(new Set());
  const editing = editSections.size > 0;
  // Ein spaet eintreffender Ladevorgang darf laufende Eingaben nie ueberschreiben.
  const editingRef = useRef(false);
  useEffect(() => { editingRef.current = editing; }, [editing]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "error" | "ok"; text: string } | null>(null);
  const [partners, setPartners] = useState<PartnerDto[]>([]);
  const [types, setTypes] = useState<ContractTypeDto[]>([]);
  const [categories, setCategories] = useState<ContractCategoryDto[]>([]);
  const [storage, setStorage] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [transition, setTransition] = useState<BusinessStatus | null>(null);
  const transitionFormRef = useRef<HTMLFormElement | null>(null);

  // Ein eingeklappter Statuskasten verbirgt das Formular: aufklappen und hineinspringen.
  useEffect(() => {
    const form = transitionFormRef.current;
    if (!transition || !form) return;
    revealBox(form);
    form.scrollIntoView?.({ block: "nearest" });
    form.querySelector<HTMLElement>("input, button[type='submit']")?.focus();
  }, [transition]);
  const [transitionForm, setTransitionForm] = useState({ terminated_on: "", effective_date: "", note: "", acknowledge: false });
  // Sprung zu Aufbewahrung bzw. Datenschutz öffnet die Eingabe in der jeweiligen Karte.
  const [retentionRequest, setRetentionRequest] = useState(0);
  const [accessRequest, setAccessRequest] = useState(0);
  const [newPartner, setNewPartner] = useState<FormValues | null>(null);
  // „Erinnern“ im Bearbeitungsmodus: alle eigenen Erinnerungen; Hinzufügen über Anzahl + Einheit.
  // Sprungziel „Direkt zur Stelle“: Feld, zu dem gesprungen wird, mit optionalem Hinweis.
  const [target, setTarget] = useState<{ key: string; note?: string; at: number } | null>(null);
  const handledLink = useRef<string | null>(null);
  const searchParams = useSearchParams();
  const linkedField = searchParams?.get(FIELD_PARAM) ?? null;
  const { can } = usePermissions();

  const load = useCallback(async () => {
    try {
      const data = await getContractRegister(orgSlug, contractId);
      // Unvollständige Antwort nie anzeigen (sonst fehlen Felder still).
      if (!data?.fields || !data.terms) throw new Error("Stammdaten konnten nicht geladen werden.");
      setRegister(data);
      if (!editingRef.current) setDraft(draftFrom(data));
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Stammdaten konnten nicht geladen werden.") });
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);
  // Bestätigung über die KI-Prüfung im Kopf der Akte: hier nachladen.
  useEffect(() => {
    const reload = () => { void load(); };
    window.addEventListener(REGISTER_CHANGED_EVENT, reload);
    return () => window.removeEventListener(REGISTER_CHANGED_EVENT, reload);
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      loadAllPartners(orgSlug, true),
      listContractTypes(orgSlug),
      listLookups(orgSlug),
      editable ? listOwnershipAssignees(orgSlug) : Promise.resolve({ items: [] as AssigneeDto[] }),
    ]).then(([partnerResult, typeResult, lookupResult, assigneeResult]) => {
      if (cancelled) return;
      if (partnerResult.status === "fulfilled") setPartners(partnerResult.value ?? []);
      if (typeResult.status === "fulfilled") {
        setTypes(typeResult.value?.contract_types ?? []);
        setCategories(typeResult.value?.contract_categories ?? []);
      }
      if (lookupResult.status === "fulfilled") {
        const lookups = lookupResult.value?.items ?? [];
        setStorage(lookups.filter((item) => item.field_key === "storage_location"));
      }
      if (assigneeResult.status === "fulfilled") setAssignees(assigneeResult.value?.items ?? []);
    });
    return () => { cancelled = true; };
  }, [editable, orgSlug]);

  // Ziel aus der Adresse (?feld=…) einmal anspringen, sobald die Daten da sind (?abschnitt= macht die Vertragsakte).
  useEffect(() => {
    if (!register || !linkedField || view === "status") return;
    const link = `f:${linkedField}`;
    if (handledLink.current === link) return;
    handledLink.current = link;
    focusField(linkedField);
    // focusField liest den aktuellen Stand; neu auslösen soll nur ein neues Ziel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [register, linkedField]);

  // Nach dem Rendern (Bearbeitung offen): zum Feld scrollen, Cursor setzen, kurz hervorheben.
  // Kurz nachfassen, bis das Feld gerendert ist (Reiterwechsel, aufklappende Karte). Danach im Blick halten,
  // solange Karten darüber noch nachladen und die Stelle nach unten schieben – bis die Person selbst scrollt.
  useEffect(() => {
    if (!target) return;
    let frame = 0;
    let timer = 0;
    let tries = 0;
    let userMoved = false;
    const stop = () => { userMoved = true; };
    const events = ["wheel", "touchstart", "keydown", "mousedown"] as const;
    events.forEach((name) => window.addEventListener(name, stop, { passive: true, once: true }));
    const element = () => document.getElementById(`rg-field-${target.key}`) ?? document.getElementById(`rg-${target.key}`);
    const keepInView = (left: number) => {
      if (userMoved || left <= 0) return;
      const row = element();
      const box = row?.getBoundingClientRect();
      if (row && box && (box.top < 0 || box.bottom > window.innerHeight)) row.scrollIntoView?.({ block: "center" });
      timer = window.setTimeout(() => keepInView(left - 1), 150);
    };
    const seek = () => {
      const row = document.getElementById(`rg-field-${target.key}`);
      const control = document.getElementById(`rg-${target.key}`);
      if (!row && !control && tries++ < 20) { timer = window.setTimeout(seek, 50); return; }
      row?.scrollIntoView?.({ block: "center" });
      (control ?? row)?.focus({ preventScroll: true });
      timer = window.setTimeout(() => keepInView(14), 150);
    };
    frame = window.requestAnimationFrame(seek);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
      events.forEach((name) => window.removeEventListener(name, stop));
    };
  }, [target, editing]);

  // Vertragsstatus: ein Hauptschritt je Status, seltene Wechsel im „⋯“-Menü.
  const PRIMARY: Partial<Record<BusinessStatus, BusinessStatus>> = { in_arbeit: "gueltig", gueltig: "gekuendigt", gekuendigt: "beendet" };
  const transitions = register?.allowed_transitions ?? [];
  const primaryTransition = register
    ? transitions.find((item) => item.target === PRIMARY[register.business_status]) ?? (register.business_status === "geloescht" ? transitions[0] : undefined)
    : undefined;
  const otherTransitions = transitions.filter((item) => item !== primaryTransition);
  const primaryBlocked = Boolean(register && primaryTransition?.target === "gueltig" && register.missing_for_valid.length);
  const nextHint = register ? STATUS_STAGE[register.business_status]?.text(register) ?? "" : "";
  const termModel = (editing ? draft.term_model : register?.fields.term_model?.value) as TermModel | null | undefined;
  const visibleTermFields = useMemo(() => new Set(termModel ? TERM_FIELDS[termModel] : ["term_model"]), [termModel]);
  const visibleCategories = useMemo(() => {
    const typeId = (editing ? draft.contract_type_id : register?.fields.contract_type_id?.value) as string | null | undefined;
    const active = categories.filter((item) => item.is_active);
    return typeId ? active.filter((item) => item.contract_type_ids.includes(typeId)) : active;
  }, [categories, draft.contract_type_id, editing, register]);

  async function run(action: () => Promise<ContractRegister>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      const data = await action();
      setRegister(data);
      setDraft(draftFrom(data));
      setMessage({ tone: "ok", text: success });
      // Die Seite laedt nach dem Speichern neu; die Bestaetigung bleibt als Toast sichtbar.
      toast(success, "success");
      onChanged?.();
      return true;
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Die Änderung konnte nicht gespeichert werden.") });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!register) return;
    const changes: Draft = {};
    for (const [key, field] of Object.entries(register.fields)) {
      if (!same(draft[key], field.value)) changes[key] = draft[key] ?? null;
    }
    if (Object.keys(changes).length === 0) {
      closeAllEdits();
      return;
    }
    if (await run(() => updateContractRegister(orgSlug, contractId, { changes }), "Stammdaten gespeichert.")) closeAllEdits();
  }

  function closeAllEdits() {
    setEditSections(new Set());
    leaveTarget();
  }

  const dirty = editing && Boolean(register) && Object.entries(register?.fields ?? {}).some(([key, field]) => !same(draft[key], field.value));
  useUnsavedChanges(dirty);
  useSaveShortcut(editing, () => { if (!busy) void save(); });

  function confirm(keys: string[]) {
    void run(() => updateContractRegister(orgSlug, contractId, { changes: {}, confirm: keys }), "KI-Wert bestätigt.");
  }

  function acceptProposal(key: string) {
    void run(() => acceptRegisterProposal(orgSlug, contractId, key), "KI-Vorschlag übernommen.");
  }

  function dismissProposal(key: string) {
    void run(() => dismissRegisterProposal(orgSlug, contractId, key), "Vorschlag ignoriert – der aktuelle Wert bleibt.");
  }

  function applySuggestion(key: string, value: string) {
    void run(() => updateContractRegister(orgSlug, contractId, { changes: { [key]: value } }), "Vorschlag übernommen.");
  }

  async function partnerCreated(id: string) {
    setNewPartner(null);
    setPartners(await loadAllPartners(orgSlug, true).catch(() => partners));
    setDraft((current) => ({ ...current, partner_id: id }));
  }

  async function saveAccess(changes: AccessChanges) {
    if (changes.confidentiality) {
      const ok = await run(() => updateContractConfidentiality(orgSlug, contractId, changes.confidentiality!), changes.dataProtection === undefined ? "Vertraulichkeit gespeichert." : "Zugriff gespeichert.");
      if (!ok) return false;
    }
    if (changes.dataProtection !== undefined) {
      return run(() => updateContractRegister(orgSlug, contractId, { changes: { data_protection_relevant: changes.dataProtection ?? null } }), "Datenschutz gespeichert.");
    }
    return true;
  }

  function saveRetention(value: number | null) {
    return run(() => updateContractRegister(orgSlug, contractId, { changes: { retention_years_after_end: value } }), value == null ? "Aufbewahrung auf Standard zurückgesetzt." : "Aufbewahrung gespeichert.");
  }

  // Kündigungsdaten ändert nur der Statuswechsel: zur Karte „Vertragsstatus“ springen.
  function openStatus() {
    if (view !== "status" && onOpenStatus) { onOpenStatus(); return; }
    const status = document.getElementById("rg-status-heading")?.closest("section");
    if (status) revealBox(status);
    status?.scrollIntoView?.({ block: "start" });
    status?.querySelector<HTMLElement>(".vs-next button")?.focus();
  }

  /** Statuswechsel öffnen; Daten vorbelegt (heute bzw. berechnetes Vertragsende), änderbar. */
  function startTransition(target: BusinessStatus) {
    if (!register) return;
    const today = register.as_of;
    const end = register.terms.actual_end ?? register.terms.possible_end ?? "";
    const effective = register.fields.terminated_effective?.value ? String(register.fields.terminated_effective.value) : "";
    setTransition(target);
    setTransitionForm({
      terminated_on: target === "gekuendigt" ? today : "",
      effective_date: target === "gekuendigt" ? end : target === "beendet" ? (effective || end || today) : "",
      note: "",
      acknowledge: false,
    });
  }

  async function submitTransition() {
    if (!transition) return;
    const ok = await run(() => changeContractStatus(orgSlug, contractId, {
      target: transition,
      terminated_on: transitionForm.terminated_on || null,
      effective_date: transitionForm.effective_date || null,
      note: transitionForm.note || null,
      acknowledge_unreviewed: transitionForm.acknowledge,
    }), `Status auf „${BUSINESS_STATUS_LABEL[transition]}“ gesetzt.`);
    if (ok) setTransition(null);
  }

  function labelFor(key: string): string {
    if (key.endsWith("_value") && PERIODS.some((prefix) => `${prefix}_value` === key)) return PERIOD_LABEL[key.replace(/_value$/, "") as (typeof PERIODS)[number]];
    return register?.fields[key]?.label ?? key;
  }

  // Feld in der Adresse merken (Zurück, Teilen), ohne die Seite neu zu laden.
  function setFieldParam(key: string | null) {
    try {
      const params = new URLSearchParams(window.location.search);
      if (key) params.set(FIELD_PARAM, key); else params.delete(FIELD_PARAM);
      handledLink.current = key ? `f:${key}` : null;
      const query = params.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  /**
   * „Direkt zur Stelle“: Bearbeitung öffnen (wenn erlaubt), zum Feld springen und den Cursor setzen.
   * Eine offene Bearbeitung bleibt erhalten; ein für die Vertragsart verborgenes Feld führt zur Vertragsart.
   */
  function focusField(rawKey: string) {
    if (!register) return;
    const key = baseFieldKey(rawKey);
    if (RETENTION_KEYS.has(key) || ACCESS_KEYS.has(key)) {
      if (RETENTION_KEYS.has(key)) setRetentionRequest(Date.now()); else setAccessRequest(Date.now());
      window.requestAnimationFrame(() => document.getElementById(`rg-field-${key}`)?.scrollIntoView?.({ block: "center" }));
      return;
    }
    if (TERMINATION_KEYS.has(key)) { openStatus(); return; }
    const home = viewOf(key);
    if (home !== view) { onOpenField?.(key, home); return; }
    const model = (editing ? draft.term_model : register.fields.term_model?.value) as TermModel | null | undefined;
    const hidden = TERM_SECTION_KEYS.has(key) && !(model ? TERM_FIELDS[model] : ["term_model"]).includes(key);
    const canEdit = editable && register.business_status !== "geloescht";
    const notes: string[] = [];
    if (hidden) notes.push(model ? `„${labelFor(rawKey)}“ gehört nicht zur gewählten Vertragsart.` : `Erst die Vertragsart wählen – danach erscheint „${labelFor(rawKey)}“.`);
    if (!canEdit) notes.push("Nur Lesen – Änderungen über das Vertragsmanagement.");
    const targetKey = hidden ? "term_model" : key;
    if (canEdit) startEdit(sectionOf(targetKey));
    setTarget({ key: hidden ? "term_model" : key, note: notes.join(" ") || undefined, at: Date.now() });
  }

  function viewOf(key: string): RegisterView {
    // Erinnerungseinstellungen stehen in „Termine & Aufgaben“ (ContractReminderSettings).
    if (key.startsWith("reminder_") || key === "escalation_recipient_account_id") return "deadlines";
    return SECTIONS.find((section) => section.fields.some((def) => def.key === key))?.view ?? "data";
  }

  function sectionOf(key: string): string {
    return SECTIONS.find((section) => section.fields.some((def) => def.key === key))?.id ?? SECTIONS[0].id;
  }

  // Offene Eingaben in anderen Kästen bleiben erhalten.
  function startEdit(sectionId: string) {
    if (!register) return;
    if (!editingRef.current) {
      editingRef.current = true;
      setDraft(draftFrom(register));
      setMessage(null);
    }
    setEditSections((current) => current.has(sectionId) ? current : new Set([...current, sectionId]));
  }

  function cancelEdit(sectionId: string) {
    if (!register) return;
    const section = SECTIONS.find((item) => item.id === sectionId);
    const keys = new Set((section?.fields ?? []).flatMap((def) => fieldKeys(def)));
    const fresh = draftFrom(register);
    setDraft((current) => Object.fromEntries(Object.entries(current).map(([key, value]) => [key, keys.has(key) ? fresh[key] : value])) as Draft);
    const next = new Set(editSections);
    next.delete(sectionId);
    setEditSections(next);
    if (next.size === 0) {
      setDraft(fresh);
      setNewPartner(null);
      leaveTarget();
    }
  }

  function jumpTo(rawKey: string) {
    setFieldParam(baseFieldKey(rawKey));
    focusField(rawKey);
  }

  function leaveTarget() {
    setTarget(null);
    try {
      if (new URLSearchParams(window.location.search).has(FIELD_PARAM)) setFieldParam(null);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  function display(def: FieldDef): string {
    if (!register) return "";
    if (def.kind === "period") {
      const value = register.fields[`${def.key}_value`]?.value;
      const unit = register.fields[`${def.key}_unit`]?.value as DurationUnit | null;
      return value == null || !unit ? "Nicht erfasst" : `${value} ${DURATION_UNIT_LABEL[unit]}`;
    }
    const field = register.fields[def.key];
    const value = field?.value;
    if (value == null || value === "") return def.kind === "bool" ? "Nein" : "Nicht erfasst";
    switch (def.kind) {
      case "bool": return value ? "Ja" : "Nein";
      case "date": return formatDate(String(value));
      case "term_model": return TERM_MODEL_LABEL[value as TermModel] ?? String(value);
      case "notice_to": return NOTICE_TO_LABEL[value as NoticeTo] ?? String(value);
      case "price_adjustment": return PRICE_ADJUSTMENT_LABEL[String(value)] ?? String(value);
      case "decimal": return `${Number(value).toLocaleString("de-DE")} %`;
      case "storage": return register.storage_location_label ?? storage.find((item) => item.code === value)?.label ?? String(value);
      case "int": return def.key === "retention_years_after_end" ? `${value} Jahr(e) nach Vertragsende` : def.key === "price_adjustment_interval_months" || def.key === "maintenance_interval_months" ? `alle ${value} Monat(e)` : String(value);
      case "partner":
      case "type":
      case "category":
      case "account": return field.display ?? "Auswahl nicht mehr verfügbar";
      default: return String(value);
    }
  }

  // Prüf-Angabe je Vertragsdaten-Feld (Vertragstitel, Vertragspartner, Vertragstyp) – für Plakette und Vorschlag.
  const reviewByField = useMemo(() => {
    const map: Record<string, FieldReviewFieldDto> = {};
    for (const field of reviewFields ?? []) if (field.kind === "extracted" && field.present && field.register_field) map[field.register_field] = field;
    return map;
  }, [reviewFields]);
  const reviewLinks = useMemo(() => Object.fromEntries(Object.entries(reviewByField).map(([key, field]) => [key, { factKey: field.fact_key, decided: field.status === "decided" }])), [reviewByField]);
  const [kept, setKept] = useState<Record<string, true>>({});
  const keepKey = (key: string, docValue: string, stored: string) => `medflux.keep.${contractId}.${key}.${docValue}|${stored}`;
  useEffect(() => {
    try {
      const next: Record<string, true> = {};
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const k = window.localStorage.key(i);
        if (k?.startsWith(`medflux.keep.${contractId}.`)) next[k] = true;
      }
      setKept(next);
    } catch {
      setKept({});
    }
  }, [contractId]);

  /** Vorschlag aus der Prüfung für ein Feld: leer + Prüfwert = Vorschlag; gefüllt + anderer Prüfwert = Widerspruch. */
  function suggestionFor(def: FieldDef): { kind: SuggestionKind; text: string; value: string; page: number | null } | null {
    if (!register) return null;
    const field = reviewByField[def.key];
    if (!field) return null;
    const docText = (field.current ?? field.document_value ?? "").trim();
    if (!docText) return null;
    let value: string | null = null;
    if (def.key === "contract_title") value = docText;
    else if (def.key === "contract_type_id") value = types.find((item) => item.label.trim().toLowerCase() === docText.toLowerCase())?.id ?? null;
    else if (def.key === "partner_id") value = partners.find((item) => [item.short_name, item.name1].some((name) => name.trim().toLowerCase() === docText.toLowerCase()))?.id ?? null;
    if (!value) return null;
    const stored = register.fields[def.key];
    const page = (field.evidence.find((item) => item.evidence_id === field.primary_evidence_id) ?? field.evidence[0])?.page ?? null;
    if (stored?.value == null || stored.value === "") return { kind: field.status === "decided" ? "confirmed" : "ai", text: docText, value, page };
    if (String(stored.value) === value) return null;
    const storedText = stored.display ?? String(stored.value);
    if (kept[keepKey(def.key, docText, storedText)]) return null;
    return { kind: "conflict", text: docText, value, page };
  }

  function keepCurrent(def: FieldDef, docText: string) {
    const stored = register?.fields[def.key];
    const key = keepKey(def.key, docText, stored?.display ?? String(stored?.value ?? ""));
    try { window.localStorage.setItem(key, "1"); } catch { /* nur Komfort */ }
    setKept((current) => ({ ...current, [key]: true }));
  }

  // „Neuer Partner“: Name aus dem Vertrag und alles, was die KI zum Partner belegt gefunden hat (Adresse, Telefon, E-Mail).
  async function startNewPartner() {
    const name = register?.supplier_text ?? "";
    const base: FormValues = { short_name: name, name1: name };
    try {
      const found = await getPartnerPrefill(orgSlug, contractId);
      const filled = Object.keys(found.values);
      if (filled.length) toast(`Aus dem Vertrag vorbelegt: ${found.sources.map((item) => item.label).join(", ")}. Bitte prüfen.`, "success");
      setNewPartner({ ...base, ...found.values });
    } catch {
      setNewPartner(base);
    }
  }

  function originOf(def: FieldDef): RegisterField | undefined {
    return register?.fields[fieldKeys(def)[0]];
  }

  function input(def: FieldDef) {
    const key = def.key;
    const id = `rg-${key}`;
    const set = (k: string, value: RegisterValue) => setDraft((current) => ({ ...current, [k]: value }));
    const text = (k: string) => (draft[k] == null ? "" : String(draft[k]));
    switch (def.kind) {
      case "textarea":
        return <textarea id={id} rows={3} value={text(key)} onChange={(event) => set(key, event.target.value)} />;
      case "bool":
        return <input id={id} type="checkbox" checked={Boolean(draft[key])} onChange={(event) => set(key, event.target.checked)} />;
      case "date":
        return <input id={id} type="date" value={text(key)} onChange={(event) => set(key, event.target.value || null)} />;
      case "int":
        return <input id={id} type="number" min={0} value={text(key)} onChange={(event) => set(key, event.target.value === "" ? null : Number(event.target.value))} />;
      case "decimal":
        return <input id={id} inputMode="decimal" value={text(key)} onChange={(event) => set(key, event.target.value.trim() === "" ? null : event.target.value)} />;
      case "price_adjustment":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Keine Angabe</option>
          {Object.entries(PRICE_ADJUSTMENT_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>;
      case "period":
        return <span className="rg-period">
          <input id={id} type="number" min={0} aria-label={`${PERIOD_LABEL[key as (typeof PERIODS)[number]]} (Anzahl)`} value={text(`${key}_value`)} onChange={(event) => set(`${key}_value`, event.target.value === "" ? null : Number(event.target.value))} />
          <select aria-label={`${PERIOD_LABEL[key as (typeof PERIODS)[number]]} (Einheit)`} value={text(`${key}_unit`)} onChange={(event) => set(`${key}_unit`, event.target.value || null)}>
            <option value="">–</option>
            {(Object.keys(DURATION_UNIT_LABEL) as DurationUnit[]).map((unit) => <option key={unit} value={unit}>{DURATION_UNIT_LABEL[unit]}</option>)}
          </select>
        </span>;
      case "term_model":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Bitte auswählen</option>
          {(Object.keys(TERM_MODEL_LABEL) as TermModel[]).map((value) => <option key={value} value={value}>{TERM_MODEL_LABEL[value]}</option>)}
        </select>;
      case "notice_to":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Bitte auswählen</option>
          {(Object.keys(NOTICE_TO_LABEL) as NoticeTo[]).map((value) => <option key={value} value={value}>{NOTICE_TO_LABEL[value]}</option>)}
        </select>;
      case "partner":
        return <span className="rg-partner">
          <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
            <option value="">Kein Vertragspartner</option>
            {partners.filter((item) => item.is_active || item.id === draft[key]).map((item) => <option key={item.id} value={item.id}>{item.short_name}{item.city ? ` · ${item.city}` : ""}</option>)}
          </select>
          {can("partner.edit") ? <button type="button" className="rg-link" onClick={() => void startNewPartner()}>Neuer Partner</button> : null}
        </span>;
      case "type":
        return <select id={id} value={text(key)} onChange={(event) => setDraft((current) => ({ ...current, contract_type_id: event.target.value || null, contract_category_id: null }))}>
          <option value="">Bitte auswählen</option>
          {types.filter((item) => item.is_active || item.id === draft[key]).map((item) => <option key={item.id} value={item.id}>{item.label}{item.is_confidential ? " (vertraulich)" : ""}</option>)}
        </select>;
      case "category":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Bitte auswählen</option>
          {visibleCategories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>;
      case "account":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Niemand</option>
          {assignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
        </select>;
      case "storage":
        return <select id={id} value={text(key)} onChange={(event) => set(key, event.target.value || null)}>
          <option value="">Nicht erfasst</option>
          {storage.map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}
        </select>;
      default:
        return <input id={id} type="text" value={text(key)} onChange={(event) => set(key, event.target.value)} />;
    }
  }

  if (!register) {
    return <section className="cw-section" aria-busy="true"><p role="status">{message?.text ?? "Stammdaten werden geladen…"}</p></section>;
  }

  const terms = register.terms;
  const fixedTerm = register.fields.term_model?.value === "fixed_term";
  const proposalKeys = Object.entries(register.fields).filter(([, field]) => field.ai_proposed_value).map(([key]) => key);

  // Kurzfassung je Kasten (sichtbar, wenn eingeklappt): 2–3 wichtige Werte, Fehlendes als Signal.
  const allDefs = SECTIONS.flatMap((section) => section.fields);
  const shown = (key: string) => {
    const def = allDefs.find((item) => item.key === key);
    const value = def ? display(def) : "Nicht erfasst";
    return value === "Nicht erfasst" ? null : value;
  };
  const joinParts = (parts: ReactNode[]) => parts.filter(Boolean).map((part, index) => <span key={index} className="summary-part">{index > 0 ? <span className="sep" aria-hidden="true">·</span> : null}{part}</span>);
  function summaryFor(sectionId: string): ReactNode {
    if (!register) return null;
    if (sectionId === "organisation") {
      const storageLabel = shown("storage_location_code");
      const accountNumber = shown("account_number");
      const parts = [storageLabel ? <>Ablage <b>{storageLabel}</b></> : null, accountNumber ? <>Konto <b>{accountNumber}</b></> : null, register.fields.manual_billing?.value ? "Manuelle Abrechnung" : null];
      return parts.some(Boolean) ? joinParts(parts) : "Nichts erfasst";
    }
    if (sectionId === "price") {
      const kind = shown("price_adjustment_kind");
      if (!kind) return "Keine Preisanpassung erfasst";
      const next = shown("price_adjustment_next_date");
      return joinParts([<b key="k">{kind}</b>, shown("price_adjustment_percent") ?? shown("price_adjustment_index_name"), next ? <>nächste <b>{next}</b></> : null]);
    }
    if (sectionId === "identity") {
      const partner = shown("partner_id");
      return joinParts([
        partner ? <b>{partner}</b> : <Signal tone="warning" size="sm">Vertragspartner fehlt</Signal>,
        shown("contract_type_id"),
        register.register_number ? `Nr. ${register.register_number}` : null,
      ]);
    }
    if (sectionId === "term") {
      const model = shown("term_model");
      if (terms.status === "incomplete") {
        const noticeMissing = terms.missing.some((key) => key.startsWith("notice_period"));
        return joinParts([model, <Signal key="missing" tone="critical" size="sm">{noticeMissing ? "Kündigungsfrist fehlt" : "Fristen nicht berechenbar"}</Signal>]);
      }
      const end = terms.actual_end ?? terms.possible_end;
      return joinParts([
        model,
        fixedTerm
          ? end ? <>Vertragsende <b>{formatDate(end)}</b></> : null
          : terms.cancel_by ? <>Kündbar bis <b>{formatDate(terms.cancel_by)}</b></> : end ? <>Vertragsende <b>{formatDate(end)}</b></> : null,
      ]);
    }
    return null;
  }

  // Kündigung ist eine Tatsache, kein Problem: neutral, nur lesbar; geändert wird sie über den Status.
  const terminationRow = register.business_status === "gekuendigt" ? <div className="rg-termrow">
    <Signal tone="neutral" icon={FLAG_ICON}>Gekündigt</Signal>
    <span>
      {register.fields.terminated_on?.value ? <>am <span className="num">{formatDate(String(register.fields.terminated_on.value))}</span></> : null}
      {register.fields.terminated_on?.value && register.fields.terminated_effective?.value ? " · " : null}
      {register.fields.terminated_effective?.value ? <>zum <span className="num">{formatDate(String(register.fields.terminated_effective.value))}</span></> : null}
    </span>
    {editable ? <button type="button" className="rg-link rg-termrow-link" onClick={openStatus}>Status ändern</button> : null}
  </div> : null;

  // Berechnet: sichtbar anders als Eingaben (gestrichelte Kacheln, schattierter Streifen). Erinnerungsdaten stehen
  // nur unter „Erinnerung & Verantwortung“.
  const contractEnd = terms.actual_end ?? terms.possible_end;
  const remaining = contractEnd ? daysBetween(register.as_of, contractEnd) : null;
  const termEditing = editSections.has("term");
  const termCalc = <div className="rg-calc" aria-labelledby="rg-calc-label">
    <div className="rg-calc-head"><span className="rg-calc-tag" id="rg-calc-label">{CALC_ICON}Berechnet</span><small>{termEditing ? "Wird nach dem Speichern neu berechnet" : `Automatisch aus den Angaben oben, Stand ${formatDate(register.as_of)}`}</small></div>
    {terms.status === "incomplete" ? <div className="rg-hintbar">
      <SignalIcon tone="warning" />
      <MissingList intro="Fristen noch nicht berechenbar. Es fehlen:" items={terms.missing.map((key) => ({ key, label: labelFor(key), onSelect: () => jumpTo(key) }))} />
    </div> : <>
      <dl className="rg-calc-tiles">
        {contractEnd ? <div className="rg-calc-tile"><dt>Vertragsende</dt><dd className="num">{formatDate(contractEnd)}</dd></div> : null}
        {!fixedTerm && terms.cancel_by ? <div className="rg-calc-tile"><dt>Kündbar bis</dt><dd className="num">{formatDate(terms.cancel_by)}</dd></div> : null}
        {remaining != null && remaining >= 0 ? <div className="rg-calc-tile"><dt>Restlaufzeit</dt><dd className="num">{remaining === 1 ? "1 Tag" : `${remaining} Tage`}</dd></div> : null}
      </dl>
      {!termEditing && terms.explanation.length ? <details className="rg-how"><summary>Wie berechnet?</summary><p>{terms.explanation.join(" ")}</p></details> : null}
    </>}
  </div>;

  return <div className="rg-panel">
    {view === "status" ? <CollapsibleSection
      id="rg-status"
      className="rg-status vs-card"
      title="Vertragsstatus"
      description="Wo der Vertrag steht und was als Nächstes zu tun ist."
      summary={joinParts([
        <>Status <b>{register.business_status_label}</b></>,
        register.business_status === "in_arbeit" && register.missing_for_valid.length ? <Signal tone="warning" size="sm">{`Für „Gültig“ fehlen ${register.missing_for_valid.length}`}</Signal> : null,
        register.has_ai_analysis && register.review_pending ? <Signal tone="ai" size="sm">KI-Prüfung offen</Signal> : null,
      ])}
      icon={STATUS_ICON}
      iconClassName="section-tile--accent"
      forceOpen={transition !== null}
      actions={<span className="rg-status-actions"><StatusBadge label={register.business_status_label} tone={BUSINESS_STATUS_TONE[register.business_status] ?? "neutral"} /></span>}
    >
      {/* Weg des Vertrags: erledigte Stufen mit Haken, die aktuelle hervorgehoben, Daten soweit gepflegt. */}
      <ol className={`vs-steps vs-tone--${register.business_status}${register.business_status === "geloescht" ? " is-cancelled" : ""}`} aria-label="Statusverlauf">
        {STATUS_PATH.map((step, index) => {
          const position = STATUS_PATH.indexOf(register.business_status as (typeof STATUS_PATH)[number]);
          const state = position < 0 ? "todo" : index < position ? "done" : index === position ? "current" : "todo";
          // Jede erlaubte Stufe ist klickbar und öffnet den Statuswechsel (z. B. zurück auf „In Arbeit“).
          const reachable = editable && transition === null && transitions.some((item) => item.target === step);
          const body = <>
            <span className="vs-dot" aria-hidden="true">{state === "done" ? STEP_CHECK : index + 1}</span>
            <span className="vs-step-label">{BUSINESS_STATUS_LABEL[step]}</span>
          </>;
          return <li key={step} className={`vs-step is-${state}${reachable ? " is-reachable" : ""}`} aria-current={state === "current" ? "step" : undefined}>
            {reachable
              ? <button type="button" className="vs-step-button" disabled={busy || (step === "gueltig" && primaryBlocked)} title={step === "gueltig" && primaryBlocked ? "Erst die fehlenden Angaben ergänzen" : transitionLabel(step, register.business_status)} onClick={() => startTransition(step)} aria-label={`Status auf „${BUSINESS_STATUS_LABEL[step]}“ setzen`}>{body}</button>
              : body}
            <small className="vs-step-date">{stepNote(step, state, register)}</small>
          </li>;
        })}
      </ol>
      {register.business_status === "geloescht" ? <p className="vs-cancelled"><Signal tone="critical" size="sm">Storniert</Signal> Als ungültig markiert – alle Daten bleiben erhalten.</p> : null}

      <div className={`vs-next vs-tone--${register.business_status}`}>
        <div className="vs-next-text">
          <strong>{STATUS_STAGE[register.business_status]?.title(register) ?? register.business_status_label}</strong>
          <span>{nextHint}</span>
        </div>
        {editable && primaryTransition ? <button type="button" className={`btn ${primaryTransition.target === "geloescht" ? "btn-danger" : "btn-primary"}`} disabled={busy || transition !== null || primaryBlocked} title={primaryBlocked ? "Erst die fehlenden Angaben ergänzen" : undefined} onClick={() => startTransition(primaryTransition.target)}>{transitionLabel(primaryTransition.target, register.business_status)}</button> : null}
        {editable && otherTransitions.length ? <ActionMenu label="Weitere Statuswechsel" disabled={busy || transition !== null} items={otherTransitions.map((item) => ({ label: transitionLabel(item.target, register.business_status), danger: item.target === "geloescht", onSelect: () => startTransition(item.target) }))} /> : null}
      </div>

      {register.business_status === "in_arbeit" && register.missing_for_valid.length ? <MissingList
        className="rg-hint"
        intro="Für „Gültig“ fehlen noch:"
        items={register.missing_for_valid.map((key) => ({ key, label: labelFor(key), onSelect: () => onOpenField?.(key, viewOf(key)) }))}
      /> : null}
      {register.has_ai_analysis && register.review_pending && register.business_status === "in_arbeit" ? <p className="vs-review"><Signal tone="ai" size="sm">KI-Prüfung offen</Signal> Vor der Freigabe die Werte aus dem Dokument bestätigen. <Link scroll={false} className="rg-link" href={contractHref(contractId, REVIEW_TARGET)}>Angaben prüfen →</Link></p> : null}

      {transition ? <form ref={transitionFormRef} className="rg-transition" onSubmit={(event) => { event.preventDefault(); void submitTransition(); }}>
        <strong>{register.business_status === "geloescht" ? "Stornierung aufheben" : `Statuswechsel nach „${BUSINESS_STATUS_LABEL[transition]}“`}</strong>
        {register.business_status === "geloescht" ? <p className="rg-hint">Der Vertrag kehrt in den Status vor der Stornierung zurück: „{BUSINESS_STATUS_LABEL[transition]}“. Die Daten bleiben unverändert.</p> : null}
        {transition === "gekuendigt" ? <>
          <label>Gekündigt am<input type="date" required value={transitionForm.terminated_on} onChange={(event) => setTransitionForm((form) => ({ ...form, terminated_on: event.target.value }))} /></label>
          <label>Gekündigt zum<input type="date" required value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label>
          <p className="field-hint">Vorschlag: heute und das berechnete Vertragsende – bitte mit dem Kündigungsschreiben abgleichen.</p>
        </> : null}
        {transition === "beendet" ? <label>Beendet am<input type="date" value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label> : null}
        {transition === "gueltig" && register.review_pending ? <label className="rg-check"><input type="checkbox" checked={transitionForm.acknowledge} onChange={(event) => setTransitionForm((form) => ({ ...form, acknowledge: event.target.checked }))} />Die KI-Werte sind noch nicht vollständig geprüft. Ich gebe den Vertrag trotzdem frei.</label> : null}
        {transition === "in_arbeit" && register.business_status !== "geloescht" ? <p className="rg-hint">Zurück in Bearbeitung: Fristen, Erinnerungen und Kosten werden nicht überwacht, bis der Vertrag wieder „Gültig“ ist. Die Daten bleiben unverändert.</p> : null}
        {transition === "geloescht" ? <p className="rg-hint">„Storniert“ markiert den Vertrag nur als ungültig; Daten bleiben. Einen Vertrag ganz entfernen: „⋯ → Löschung beantragen“ im Kopf.</p> : null}
        <label>Notiz (optional)<input type="text" maxLength={2000} value={transitionForm.note} onChange={(event) => setTransitionForm((form) => ({ ...form, note: event.target.value }))} /></label>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setTransition(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Status ändern</button></div>
      </form> : null}
    </CollapsibleSection> : null}
    {view === "data" ? <>

    {afterStatus}

    <ContractRulesSection organizationSlug={orgSlug} contractId={contractId} version={register} />

    {editable && (register.partner_suggestions.length > 0 || register.type_suggestion || proposalKeys.length > 0) ? <section className="cw-section rg-ai" aria-labelledby="rg-ai-heading">
      <div className="cw-section-head"><div><h2 id="rg-ai-heading">KI-Vorschläge</h2><p>Nichts wird automatisch übernommen. Bitte prüfen und bestätigen.</p></div></div>
      <ul>
        {register.partner_suggestions.map((item) => <li key={item.id}>Vertragspartner „{register.supplier_text}“ entspricht vermutlich <strong>{item.short_name}</strong>{item.city ? ` (${item.city})` : ""} · Übereinstimmung {Math.round(item.score * 100)} % <button type="button" className="btn" disabled={busy} onClick={() => applySuggestion("partner_id", item.id)}>Übernehmen</button></li>)}
        {register.type_suggestion ? <li>Vertragstyp <strong>{register.type_suggestion.label}</strong> (aus {register.type_suggestion.reason}) <button type="button" className="btn" disabled={busy} onClick={() => applySuggestion("contract_type_id", register.type_suggestion!.id)}>Übernehmen</button></li> : null}
        {proposalKeys.map((key) => <li key={key}><AiOrigin state="unreviewed" factKey={register.fields[key].ai_proposed_value?.source_field} subject={labelFor(key)} /> {register.fields[key].ai_proposed_value?.document ? `„${register.fields[key].ai_proposed_value?.document}“` : "Neue Analyse"} schlägt für <strong>{labelFor(key)}</strong> vor: {String(register.fields[key].ai_proposed_value?.value ?? "leer")} (aktuell: {String(register.fields[key].value ?? "leer")}) <span className="rg-proposal-actions"><button type="button" className="btn" disabled={busy} onClick={() => acceptProposal(key)}>Übernehmen</button><button type="button" className="btn btn-ghost" disabled={busy} onClick={() => dismissProposal(key)} title="Der aktuelle Wert ist richtig – dieser Vorschlag wird nicht erneut angezeigt">Ignorieren</button></span></li>)}
      </ul>
    </section> : null}
    {/* Angaben aus dem Vertrag, die in die Stammdaten des Vertragspartners gehören (E-Mail, Telefon, Anschrift). */}
    {typeof register.fields.partner_id?.value === "string" && register.fields.partner_id.value
      ? <PartnerSuggestions orgSlug={orgSlug} partnerId={register.fields.partner_id.value} contractId={contractId} /> : null}
    </> : null}

    {/* Erfolg nur als Toast; ein Text hier stünde zwischen den Kästen. Fehler bleiben sichtbar. */}
    {message?.tone === "error" ? <p role="alert" className="rg-error">{message.text}</p> : null}

    {newPartner !== null ? <QuickCreatePartner
      organizationSlug={orgSlug}
      open={newPartner !== null}
      preset={newPartner ?? undefined}
      onClose={() => setNewPartner(null)}
      onCreated={({ id }) => void partnerCreated(id)}
    /> : null}

    {SECTIONS.map((section) => {
      if ((section.view ?? "data") !== view) return null;
      const maintenanceHidden = hiddenSections?.has("maintenance") && register.fields.maintenance_next_date?.value == null && register.fields.maintenance_interval_months?.value == null;
      const fields = section.id === "term"
        ? section.fields.filter((def) => visibleTermFields.has(def.key))
        : section.fields.filter((def) => !(def.key.startsWith("maintenance_") && maintenanceHidden));
      // Nur dieser Kasten zeigt Eingabefelder (die übrigen Werte bleiben lesbar).
      const editing = editSections.has(section.id);
      if (hiddenSections?.has(section.id) && !editing && fields.every((def) => register.fields[def.key]?.value == null)) return null;
      const canEditHere = editable && register.business_status !== "geloescht";
      const actions = editing
        ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => cancelEdit(section.id)} aria-label={`Abbrechen (${section.title})`}>Abbrechen</button>
        : canEditHere
          ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => startEdit(section.id)} aria-label={`${section.title} bearbeiten`} data-shortcut="edit" aria-keyshortcuts="E" title="Bearbeiten (E)">Bearbeiten</button>
          : null;
      const isTerm = section.id === "term";
      // Kopf von „Vertrag & Partner“: nur die Pflichtangaben der Prüfung zu dieser Karte (Vertragspartner, Vertragsgegenstand, Vertragsart …);
      // gezählt wird, was in der Prüfung entschieden ist. Widersprüche stehen daneben.
      const pflicht = (reviewFields ?? []).filter((field) => field.card === "partner" && field.kind === "extracted" && levelOf(field.tier) === "pflicht" && (field.decision_needed || field.status === "decided"));
      const filledCount = pflicht.filter((field) => field.status === "decided").length;
      const conflictCount = section.id === "identity" ? fields.filter((def) => suggestionFor(def)?.kind === "conflict").length : 0;
      const identityBadge = section.id === "identity" && pflicht.length > 0
        ? <RequiredBadge tone={filledCount === pflicht.length && conflictCount === 0 ? "done" : "warning"}>{`${filledCount} von ${pflicht.length} Pflichtangaben${conflictCount ? ` · ${conflictCount} ${conflictCount === 1 ? "Widerspruch" : "Widersprüche"}` : ""}`}</RequiredBadge>
        : null;
      const renderField = (def: FieldDef) => {
          if (def.kind === "auto_number") {
            const earlier = register.fields.internal_number?.value;
            return <div key={def.key} id="rg-field-register_number" className="rg-field">
              <dt>Interne Nummer</dt>
              <dd>
                <span className="rg-value">{register.register_number ?? "Wird beim ersten Speichern vergeben"}</span>
                <span className="rg-origin rg-origin-system" title="Vom Programm aus dem Nummernkreis vergeben – eindeutig, nicht änderbar">Automatisch</span>
                {earlier ? <span className="field-hint rg-help">Frühere interne Nummer: {String(earlier)}</span> : null}
              </dd>
            </div>;
          }
          const provenance = originOf(def);
          const label = def.kind === "period" ? PERIOD_LABEL[def.key as (typeof PERIODS)[number]] : register.fields[def.key]?.label ?? def.key;
          const isTarget = target?.key === def.key;
          const empty = !editing && def.kind !== "bool" && display(def) === "Nicht erfasst";
          // Erinnerungen: „Standard“ (geerbt) oder „Angepasst“ (geändert), nicht die Herkunft „Manuell“.
          const openSource = provenance?.document_source && onShowSource ? () => onShowSource(provenance.document_source!) : null;
          const aiState = provenance?.origin === "ai" ? "unreviewed" : provenance?.origin === "ai_confirmed" ? "confirmed" : null;
          // KI-Werte: eine Plakette (Bestätigt/Ungeprüft), die die Quelle öffnet; sonst die stille Herkunft wie bisher.
          // Die Vertragsart nach Laufzeit („Feste Laufzeit“ …) ist keine eigene Prüf-Angabe: die Plakette führt zur Angabe, aus der sie folgt.
          const termModelFact = def.key === "term_model" ? TERM_MODEL_FACT[String(register.fields.term_model?.value ?? "")] : undefined;
          // Felder ohne eigene KI-Herkunft (z. B. Vertragspartner) führen trotzdem zur zugehörigen Prüf-Angabe.
          const reviewLink = !aiState ? reviewLinks[def.key] : undefined;
          const suggestion = suggestionFor(def);
          const originBadge = aiState ? <AiOrigin state={aiState} onOpenSource={openSource} factKey={termModelFact ?? provenance?.source_field} subject={def.key === "term_model" ? undefined : label} />
            : reviewLink ? <AiOrigin state={reviewLink.decided ? "confirmed" : "unreviewed"} onOpenSource={openSource} factKey={reviewLink.factKey} subject={label} />
            : provenance?.origin ? <span className={`rg-origin rg-origin-${provenance.origin}`} title={provenance.source_field ? `Quelle: ${provenance.source_field}` : undefined}>{ORIGIN_LABEL[provenance.origin]}</span> : null;
          const sourceChip = !aiState && provenance?.document_source && onShowSource ? <button type="button" className="cw-source-button" title={`„${provenance.document_source.quote}“`} onClick={() => onShowSource(provenance.document_source!)} aria-label={`Fundstelle von ${label}: Seite ${provenance.document_source.page}`}>Quelle</button> : null;
          return <div key={def.key} id={`rg-field-${def.key}`} className={isTarget ? "rg-field rg-field--target" : "rg-field"} tabIndex={isTarget ? -1 : undefined}>
            <dt>{editing && def.kind !== "period" ? <label htmlFor={`rg-${def.key}`}>{label}</label> : label}{editing && isTerm ? <>{originBadge}{sourceChip}</> : null}</dt>
            <dd>
              {editing ? input(def) : suggestion && suggestion.kind !== "conflict" ? null : <span className="rg-value">{display(def)}</span>}
              {!editing && suggestion ? <FieldSuggestion kind={suggestion.kind} value={suggestion.text} page={suggestion.page} busy={busy}
                onApply={() => void run(() => updateContractRegister(orgSlug, contractId, { changes: { [def.key]: suggestion.value } }), "Aus der Prüfung übernommen.")}
                onKeep={suggestion.kind === "conflict" ? () => keepCurrent(def, suggestion.text) : undefined}
                onOther={suggestion.kind === "ai" ? () => { startEdit(section.id); } : undefined} /> : null}
              {editing && FIELD_HELP[def.key] ? <span className="field-hint rg-help">{FIELD_HELP[def.key]}</span> : null}
              {!editing ? <>{originBadge}{sourceChip}</> : null}
              {!editing && editable && provenance?.origin === "ai" ? <button type="button" className="rg-link" disabled={busy} onClick={() => confirm(fieldKeys(def))}>Bestätigen</button> : null}
              {empty && !suggestion && editable && register.business_status !== "geloescht" ? <button type="button" className="rg-add" onClick={() => jumpTo(def.key)} aria-label={`${label} erfassen`}>Erfassen</button> : null}
              {empty && editable && onSearchInDocument && searchableKeys?.has(def.key) && register.business_status !== "geloescht" ? <button type="button" className="rg-link" onClick={() => onSearchInDocument(def.key)} aria-label={`${label} im Dokument suchen`}>Im Dokument suchen</button> : null}
              {isTarget && target?.note ? <span className="rg-field-note" role="status">{target.note}</span> : null}
            </dd>
          </div>;
      };
      const groupDefs = REGISTER_GROUPS[section.id];
      const renderFields = () => groupDefs
        ? <div className="cw-ov-groups cw-ov-groups--blocks">{groupDefs.map((group) => {
          const items = fields.filter((def) => group.keys.includes(def.key));
          if (items.length === 0) return null;
          return <RegisterGroup key={group.id} id={`rg-group-${group.id}`} title={group.title} intro={group.intro} icon={group.icon} tile={group.tile}>
            <dl className="rg-fields rg-fields--single">{items.map(renderField)}</dl>
          </RegisterGroup>;
        })}</div>
        : <dl className="rg-fields">{fields.map(renderField)}</dl>;
      return <Fragment key={section.id}><CollapsibleSection id={`rg-${section.id}`} title={section.title} description={editing && dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : section.id === "identity" ? <>{section.description} {identityBadge}</> : section.description} summary={summaryFor(section.id)} actions={actions} forceOpen={editing || (target !== null && fields.some((def) => def.key === target.key))} icon={SECTION_ICONS[section.id]?.icon} iconClassName={SECTION_ICONS[section.id]?.tile}>
        {isTerm ? terminationRow : null}
        {renderFields()}
        {isTerm ? termCalc : null}
        {editing ? <div className="cw-savebar" role="region" aria-label={`${section.title} speichern`}>
          <div className="cw-savebar-msg">{dirty ? <><Signal tone="info" size="sm">Ungespeicherte Änderungen</Signal><span><kbd>Strg</kbd> + <kbd>S</kbd> speichert</span></> : <span>Keine Änderungen</span>}</div>
          <div className="cw-savebar-actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void save()} aria-keyshortcuts="Control+S">{busy ? "Wird gespeichert…" : "Speichern"}</button>
          </div>
        </div> : null}
      </CollapsibleSection>
      {isTerm ? <>
        <ContractRetentionCard
          register={register}
          typeDefaultYears={types.find((item) => item.id === register.fields.contract_type_id?.value)?.retention_years ?? null}
          canEdit={canEditHere}
          busy={busy}
          onSaveYears={saveRetention}
          editRequest={retentionRequest}
        />
        <ContractAccessCard
          register={register}
          contractId={contractId}
          orgSlug={orgSlug}
          assignees={assignees}
          isAdmin={isAdmin && register.business_status !== "geloescht"}
          canEditData={canEditHere}
          busy={busy}
          onSave={saveAccess}
          onConfirm={() => confirm(["data_protection_relevant"])}
          editRequest={accessRequest}
        />
      </> : null}
      </Fragment>;
    })}
  </div>;
}
