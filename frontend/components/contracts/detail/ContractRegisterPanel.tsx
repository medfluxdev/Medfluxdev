"use client";

import StatusBadge from "@/components/ui/StatusBadge";
import ReminderLeadsEditor from "./ReminderLeadsEditor";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { loadAllPartners } from "@/components/master-data/definitions/partners";
import { QuickCreatePartner } from "@/components/master-data/lazy";
import { REGISTER_CHANGED_EVENT } from "./AiReviewButton";
import ContractRulesSection from "./ContractRulesSection";
import type { FormValues } from "@/components/master-data/types";
import MissingList from "@/components/ui/MissingList";
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
  changeContractStatus,
  getContractRegister,
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
import { coverPdfUrl } from "@/lib/domain-api/registerGrid";
import { usePermissions } from "@/lib/use-permissions";
import { FIELD_PARAM, baseFieldKey } from "@/lib/fix-targets";

type Draft = Record<string, RegisterValue>;
type FieldKind = "text" | "textarea" | "bool" | "date" | "int" | "decimal" | "period" | "term_model" | "notice_to" | "price_adjustment" | "partner" | "type" | "category" | "account" | "storage" | "todo" | "auto_number";
type FieldDef = { key: string; kind: FieldKind };

const PERIODS = ["initial_term", "minimum_term", "notice_period", "renewal_period"] as const;

const SECTIONS: { id: string; title: string; description: string; fields: FieldDef[] }[] = [
  {
    id: "identity",
    title: "Vertrag & Partner",
    description: "Kurzbeschreibung, Vertragspartner und Einordnung",
    fields: [
      { key: "short_description", kind: "text" },
      // Interne Nummer = automatisch vergebene, eindeutige Vertragsnummer (Nummernkreis), nie von Hand.
      { key: "register_number", kind: "auto_number" },
      { key: "partner_id", kind: "partner" },
      { key: "contract_type_id", kind: "type" },
      { key: "contract_category_id", kind: "category" },
      { key: "is_framework", kind: "bool" },
      { key: "data_protection_relevant", kind: "bool" },
      { key: "subject_text", kind: "textarea" },
    ],
  },
  {
    id: "term",
    title: "Laufzeit & Kündigung",
    description: "Grundlage für die automatisch berechneten Fristen",
    fields: [
      { key: "term_model", kind: "term_model" },
      { key: "term_start_date", kind: "date" },
      { key: "term_fixed_end_date", kind: "date" },
      { key: "initial_term", kind: "period" },
      { key: "minimum_term", kind: "period" },
      { key: "notice_period", kind: "period" },
      { key: "notice_to", kind: "notice_to" },
      { key: "renewal_period", kind: "period" },
    ],
  },
  {
    id: "reminder",
    title: "Erinnerung & Verantwortung",
    description: "Wer wird wann an die Frist erinnert",
    fields: [
      { key: "reminder_lead_months", kind: "int" },
      { key: "reminder_recipient_account_id", kind: "account" },
      { key: "escalation_recipient_account_id", kind: "account" },
      { key: "reminder_todo", kind: "todo" },
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
  {
    id: "maintenance",
    title: "Wartung",
    description: "Grundlage für die Erinnerung „Wartung fällig“",
    fields: [
      { key: "maintenance_next_date", kind: "date" },
      { key: "maintenance_interval_months", kind: "int" },
    ],
  },
  {
    id: "termination",
    title: "Kündigung & Aufbewahrung",
    description: "Dokumentierte Kündigung und Löschfrist",
    fields: [
      { key: "terminated_on", kind: "date" },
      { key: "terminated_effective", kind: "date" },
      { key: "retention_years_after_end", kind: "int" },
    ],
  },
];

// Kurze Erklaerungen fuer schwierige Felder (nur im Bearbeitungsmodus sichtbar).
const FIELD_HELP: Record<string, string> = {
  term_model: "Bestimmt, wie Fristen berechnet werden: Eine feste Laufzeit endet von selbst, kündbare Verträge laufen bis zur Kündigung, bei automatischer Verlängerung verlängert sich der Vertrag ohne Kündigung.",
  notice_period: "Wie lange vor dem Kündigungstermin die Kündigung beim Vertragspartner eingegangen sein muss.",
  notice_to: "Zu welchem Termin gekündigt werden kann – z. B. „zum Quartalsende“ = 31.03., 30.06., 30.09. oder 31.12.",
  minimum_term: "Frühestens nach dieser Zeit ist eine Kündigung wirksam.",
  renewal_period: "Um wie viel sich der Vertrag ohne Kündigung jeweils verlängert.",
  reminder_lead_months: "Wie viele Monate vor dem Kündigungstermin (bei fester Laufzeit: vor dem Vertragsende) die erste Erinnerung kommt. Leer = Standard (4 Monate).",
  retention_years_after_end: "Leer lassen, um die Aufbewahrungsfrist des Vertragstyps zu verwenden.",
  maintenance_next_date: "Ein Monat vorher entsteht der Termin „Wartung fällig“ unter Fristen & Aufgaben.",
  maintenance_interval_months: "Leer lassen für einen einmaligen Termin; sonst entsteht nach Erledigung der nächste Termin.",
  data_protection_relevant: "Ja, wenn der Vertragspartner personenbezogene Daten verarbeitet (Auftragsverarbeitung nach Art. 28 DSGVO).",
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

export default function ContractRegisterPanel({ contractId, orgSlug, onChanged, searchableKeys, onSearchInDocument, onShowSource, hiddenSections }: {
  contractId: string;
  /** Kästen, die der Vertragstyp nicht vorsieht; sie bleiben sichtbar, sobald ein Wert gepflegt ist. */
  hiddenSections?: Set<string>;
  orgSlug: string;
  onChanged?: () => void;
  /** Felder, die im Vertragsdokument gesucht werden können (erneute Erfassung). */
  searchableKeys?: Set<string>;
  onSearchInDocument?: (key: string) => void;
  /** Fundstelle eines aus dem Dokument übernommenen Werts zeigen. */
  onShowSource?: (source: { document_version_id: string; page: number; quote: string }) => void;
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
  const [todos, setTodos] = useState<LookupDto[]>([]);
  const [assignees, setAssignees] = useState<AssigneeDto[]>([]);
  const [transition, setTransition] = useState<BusinessStatus | null>(null);
  const [transitionForm, setTransitionForm] = useState({ terminated_on: "", effective_date: "", note: "", acknowledge: false });
  const [confidentialDraft, setConfidentialDraft] = useState<{ is_confidential: boolean; grants: string[] } | null>(null);
  const [newPartner, setNewPartner] = useState<FormValues | null>(null);
  // Sprungziel „Direkt zur Stelle“: Feld, zu dem gesprungen wird, mit optionalem Hinweis.
  const [target, setTarget] = useState<{ key: string; note?: string; at: number } | null>(null);
  const handledLink = useRef<string | null>(null);
  const searchParams = useSearchParams();
  const linkedField = searchParams?.get(FIELD_PARAM) ?? null;
  const { can } = usePermissions();

  const load = useCallback(async () => {
    try {
      const data = await getContractRegister(orgSlug, contractId);
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
      if (partnerResult.status === "fulfilled") setPartners(partnerResult.value);
      if (typeResult.status === "fulfilled") {
        setTypes(typeResult.value.contract_types);
        setCategories(typeResult.value.contract_categories);
      }
      if (lookupResult.status === "fulfilled") {
        setStorage(lookupResult.value.items.filter((item) => item.field_key === "storage_location"));
        setTodos(lookupResult.value.items.filter((item) => item.field_key === "todo_template"));
      }
      if (assigneeResult.status === "fulfilled") setAssignees(assigneeResult.value.items);
    });
    return () => { cancelled = true; };
  }, [editable, orgSlug]);

  // Ziel aus der Adresse (?feld=…) einmal anspringen, sobald die Daten da sind (?abschnitt= macht die Vertragsakte).
  useEffect(() => {
    if (!register || !linkedField) return;
    const link = `f:${linkedField}`;
    if (handledLink.current === link) return;
    handledLink.current = link;
    focusField(linkedField);
    // focusField liest den aktuellen Stand; neu auslösen soll nur ein neues Ziel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [register, linkedField]);

  // Nach dem Rendern (Bearbeitung offen): zum Feld scrollen, Cursor setzen, kurz hervorheben.
  useEffect(() => {
    if (!target) return;
    const frame = window.requestAnimationFrame(() => {
      const row = document.getElementById(`rg-field-${target.key}`);
      const control = document.getElementById(`rg-${target.key}`);
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      row?.scrollIntoView?.({ block: "center", behavior: reduce ? "auto" : "smooth" });
      (control ?? row)?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [target, editing]);

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
      setEditSections(new Set());
      leaveTarget();
      return;
    }
    if (await run(() => updateContractRegister(orgSlug, contractId, { changes }), "Stammdaten gespeichert.")) {
      setEditSections(new Set());
      leaveTarget();
    }
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

  function applySuggestion(key: string, value: string) {
    void run(() => updateContractRegister(orgSlug, contractId, { changes: { [key]: value } }), "Vorschlag übernommen.");
  }

  async function partnerCreated(id: string) {
    setNewPartner(null);
    setPartners(await loadAllPartners(orgSlug, true).catch(() => partners));
    setDraft((current) => ({ ...current, partner_id: id }));
  }

  async function submitConfidentiality() {
    if (!confidentialDraft) return;
    const ok = await run(() => updateContractConfidentiality(orgSlug, contractId, {
      is_confidential: confidentialDraft.is_confidential,
      grant_account_ids: confidentialDraft.grants,
    }), "Vertraulichkeit gespeichert.");
    if (ok) setConfidentialDraft(null);
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
    if ((value == null || value === "") && def.key === "reminder_lead_months") return `${register.reminders?.default_lead_months ?? 4} Monate vor der Frist (Standard)`;
    if (value == null || value === "") return def.kind === "bool" ? "Nein" : "Nicht erfasst";
    switch (def.kind) {
      case "bool": return value ? "Ja" : "Nein";
      case "date": return formatDate(String(value));
      case "term_model": return TERM_MODEL_LABEL[value as TermModel] ?? String(value);
      case "notice_to": return NOTICE_TO_LABEL[value as NoticeTo] ?? String(value);
      case "price_adjustment": return PRICE_ADJUSTMENT_LABEL[String(value)] ?? String(value);
      case "decimal": return `${Number(value).toLocaleString("de-DE")} %`;
      case "storage": return register.storage_location_label ?? storage.find((item) => item.code === value)?.label ?? String(value);
      case "int": return def.key === "reminder_lead_months" ? `${value} Monat(e) vor der Frist` : def.key === "retention_years_after_end" ? `${value} Jahr(e) nach Vertragsende` : def.key === "price_adjustment_interval_months" || def.key === "maintenance_interval_months" ? `alle ${value} Monat(e)` : String(value);
      case "partner":
      case "type":
      case "category":
      case "account": return field.display ?? "Auswahl nicht mehr verfügbar";
      default: return String(value);
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
          {can("partner.edit") ? <button type="button" className="rg-link" onClick={() => setNewPartner({ short_name: register?.supplier_text ?? "", name1: register?.supplier_text ?? "" })}>Neuer Partner</button> : null}
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
      case "todo":
        return <>
          <input id={id} list="rg-todo-templates" value={text(key)} onChange={(event) => set(key, event.target.value)} />
          <datalist id="rg-todo-templates">{todos.map((item) => <option key={item.id} value={item.label}>{item.description ?? ""}</option>)}</datalist>
        </>;
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

  return <div className="rg-panel">
    <section className="cw-section rg-status" aria-labelledby="rg-status-heading">
      <div className="rg-status-row">
        <div>
          <h2 id="rg-status-heading">Bearbeitungsstatus</h2>
          <p className="cw-muted">{register.has_ai_analysis ? "Werte aus der KI-Analyse sind gekennzeichnet und können bestätigt oder korrigiert werden." : "Manuell angelegter Vertrag ohne KI-Analyse."}</p>
        </div>
        <div className="rg-status-actions">
          <StatusBadge label={register.business_status_label} tone={BUSINESS_STATUS_TONE[register.business_status] ?? "neutral"} />
          {editable && register.allowed_transitions.map((item) => <button key={item.target} type="button" className={item.target === "geloescht" ? "btn btn-ghost btn-danger" : "btn"} disabled={busy} onClick={() => { setTransition(item.target); setTransitionForm({ terminated_on: "", effective_date: "", note: "", acknowledge: false }); }}>→ {item.label}</button>)}
        </div>
      </div>
      {register.business_status === "in_arbeit" ? <MissingList
        className="rg-hint"
        intro="Für „Gültig“ fehlen noch:"
        items={register.missing_for_valid.map((key) => ({ key, label: labelFor(key), onSelect: () => jumpTo(key) }))}
      /> : null}
      {transition ? <form className="rg-transition" onSubmit={(event) => { event.preventDefault(); void submitTransition(); }}>
        <strong>Statuswechsel nach „{BUSINESS_STATUS_LABEL[transition]}“</strong>
        {transition === "gekuendigt" ? <>
          <label>Gekündigt am<input type="date" required value={transitionForm.terminated_on} onChange={(event) => setTransitionForm((form) => ({ ...form, terminated_on: event.target.value }))} /></label>
          <label>Gekündigt zum<input type="date" required value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label>
        </> : null}
        {transition === "beendet" ? <label>Beendet am<input type="date" value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label> : null}
        {transition === "gueltig" && register.review_pending ? <label className="rg-check"><input type="checkbox" checked={transitionForm.acknowledge} onChange={(event) => setTransitionForm((form) => ({ ...form, acknowledge: event.target.checked }))} />Die KI-Werte sind noch nicht vollständig geprüft. Ich gebe den Vertrag trotzdem frei.</label> : null}
        {transition === "geloescht" ? <p className="rg-hint">„Storniert“ markiert den Vertrag nur als ungültig; Daten bleiben. Einen Vertrag ganz entfernen: „⋯ → Löschung beantragen“ im Kopf.</p> : null}
        <label>Notiz (optional)<input type="text" maxLength={2000} value={transitionForm.note} onChange={(event) => setTransitionForm((form) => ({ ...form, note: event.target.value }))} /></label>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setTransition(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Status ändern</button></div>
      </form> : null}
    </section>

    <ContractRulesSection organizationSlug={orgSlug} contractId={contractId} version={register} />

    <section className="cw-section" aria-labelledby="rg-terms-heading">
      <div className="cw-section-head"><div><h2 id="rg-terms-heading">Berechnete Fristen</h2><p>Deterministisch aus den Stammdaten berechnet (Stand {formatDate(register.as_of)}).</p></div></div>
      {terms.status === "incomplete" ? <MissingList
        className="rg-hint"
        intro="Fristen noch nicht berechenbar. Es fehlen:"
        items={terms.missing.map((key) => ({ key, label: labelFor(key), onSelect: () => jumpTo(key) }))}
      /> : null}
      <div className="rg-terms">
        {/* Feste Laufzeit endet ohne Kündigung: kein „Kündbar bis“, ein Vertragsende. */}
        {fixedTerm ? null : <div><span>Kündbar bis</span><strong>{terms.cancel_by ? formatDate(terms.cancel_by) : "–"}</strong></div>}
        <div><span>{terms.actual_end ? "Tatsächliches Ende" : fixedTerm ? "Vertragsende" : "Mögliches Vertragsende"}</span><strong>{formatDate(terms.actual_end ?? terms.possible_end)}</strong></div>
        {fixedTerm ? null : <div><span>Frühestes / festes Ende</span><strong>{formatDate(terms.earliest_end)}</strong></div>}
        <div><span>{(terms.reminder_dates?.length ?? 0) > 1 ? "Erinnerungen am" : "Erinnerung am"}</span><strong>{terms.reminder_dates?.length ? terms.reminder_dates.map((value) => formatDate(value)).join(", ") : formatDate(terms.reminder_date)}</strong></div>
      </div>
      {terms.explanation.length > 0 ? <ul className="rg-explanation">{terms.explanation.map((line) => <li key={line}>{line}</li>)}</ul> : null}
    </section>

    <section className="cw-section" aria-labelledby="rg-protection-heading">
      <div className="cw-section-head"><div><h2 id="rg-protection-heading">Vertraulichkeit & Aufbewahrung</h2><p>Wer den Vertrag sehen darf und ab wann er gelöscht werden darf.</p></div></div>
      <div className="rg-terms">
        <div><span>Vertraulich</span><strong>{register.confidentiality.effective ? (register.confidentiality.type_confidential && !register.confidentiality.is_confidential ? "Ja (über Vertragstyp)" : "Ja") : "Nein"}</strong></div>
        <div><span>Aufbewahrung</span><strong>{register.retention.years == null ? "Nicht festgelegt" : `${register.retention.years} Jahr(e) nach Vertragsende`}</strong>{register.retention.years == null && editable && register.business_status !== "geloescht" ? <button type="button" className="rg-link" onClick={() => jumpTo("retention_years_after_end")} aria-label="Aufbewahrung festlegen">Festlegen</button> : null}{register.retention.source ? <small className="cw-muted">{register.retention.source === "contract" ? "am Vertrag festgelegt" : "aus Vertragstyp"}</small> : null}</div>
        <div><span>Löschen ab</span><strong>{register.retention.deletion_from ? formatDate(register.retention.deletion_from) : "–"}</strong>{!register.retention.deletion_from ? <small className="cw-muted">erst nach bekanntem Vertragsende</small> : null}</div>
      </div>
      {register.confidentiality.effective ? <p className="cw-muted">Sichtbar für Administratoren, die verantwortliche Person, die Erinnerungsempfänger{register.confidentiality.grants.length > 0 ? ` und freigegeben für: ${register.confidentiality.grants.map((item) => item.display_name).join(", ")}` : ""}.</p> : null}
      {isAdmin && !confidentialDraft ? <div className="rg-actions"><button type="button" className="btn" disabled={busy} onClick={() => setConfidentialDraft({ is_confidential: register.confidentiality.is_confidential, grants: register.confidentiality.grants.map((item) => item.account_id) })}>Vertraulichkeit bearbeiten</button></div> : null}
      {confidentialDraft ? <form className="rg-transition" aria-label="Vertraulichkeit bearbeiten" onSubmit={(event) => { event.preventDefault(); void submitConfidentiality(); }}>
        <label className="rg-check"><input type="checkbox" checked={confidentialDraft.is_confidential} onChange={(event) => setConfidentialDraft((form) => form && ({ ...form, is_confidential: event.target.checked }))} />Vertrag als vertraulich kennzeichnen</label>
        {register.confidentiality.type_confidential ? <p className="rg-hint">Der Vertragstyp ist bereits vertraulich. Der Vertrag bleibt deshalb auch ohne Kennzeichen geschützt.</p> : null}
        <fieldset className="rg-grants"><legend>Zusätzlich freigeben für</legend>
          {assignees.length === 0 ? <p className="cw-muted">Keine Benutzer verfügbar.</p> : assignees.map((item) => <label key={item.id} className="rg-check"><input type="checkbox" checked={confidentialDraft.grants.includes(item.id)} onChange={(event) => setConfidentialDraft((form) => form && ({ ...form, grants: event.target.checked ? [...form.grants, item.id] : form.grants.filter((id) => id !== item.id) }))} />{item.display_name}</label>)}
        </fieldset>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setConfidentialDraft(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
      </form> : null}
    </section>

    {editable && (register.partner_suggestions.length > 0 || register.type_suggestion || proposalKeys.length > 0) ? <section className="cw-section rg-ai" aria-labelledby="rg-ai-heading">
      <div className="cw-section-head"><div><h2 id="rg-ai-heading">KI-Vorschläge</h2><p>Nichts wird automatisch übernommen. Bitte prüfen und bestätigen.</p></div></div>
      <ul>
        {register.partner_suggestions.map((item) => <li key={item.id}>Vertragspartner „{register.supplier_text}“ entspricht vermutlich <strong>{item.short_name}</strong>{item.city ? ` (${item.city})` : ""} · Übereinstimmung {Math.round(item.score * 100)} % <button type="button" className="btn" disabled={busy} onClick={() => applySuggestion("partner_id", item.id)}>Übernehmen</button></li>)}
        {register.type_suggestion ? <li>Vertragstyp <strong>{register.type_suggestion.label}</strong> (aus {register.type_suggestion.reason}) <button type="button" className="btn" disabled={busy} onClick={() => applySuggestion("contract_type_id", register.type_suggestion!.id)}>Übernehmen</button></li> : null}
        {proposalKeys.map((key) => <li key={key}>{register.fields[key].ai_proposed_value?.document ? `„${register.fields[key].ai_proposed_value?.document}“` : "Neue Analyse"} schlägt für <strong>{labelFor(key)}</strong> vor: {String(register.fields[key].ai_proposed_value?.value ?? "leer")} (aktuell: {String(register.fields[key].value ?? "leer")}) <button type="button" className="btn" disabled={busy} onClick={() => acceptProposal(key)}>Übernehmen</button></li>)}
      </ul>
    </section> : null}

    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

    {newPartner !== null ? <QuickCreatePartner
      organizationSlug={orgSlug}
      open={newPartner !== null}
      preset={newPartner ?? undefined}
      onClose={() => setNewPartner(null)}
      onCreated={({ id }) => void partnerCreated(id)}
    /> : null}

    <div className="rg-toolbar">
        <a href={coverPdfUrl(orgSlug, contractId)} target="_blank" rel="noopener noreferrer" className="btn">Deckblatt (PDF)</a>
      <Link href="/stammdaten/vertragspartner" className="rg-link">Vertragspartner verwalten</Link>
    </div>

    {SECTIONS.map((section) => {
      const fields = section.id === "term" ? section.fields.filter((def) => visibleTermFields.has(def.key)) : section.fields;
      // Nur dieser Kasten zeigt Eingabefelder (die übrigen Werte bleiben lesbar).
      const editing = editSections.has(section.id);
      if (hiddenSections?.has(section.id) && !editing && fields.every((def) => register.fields[def.key]?.value == null)) return null;
      const canEditHere = editable && register.business_status !== "geloescht";
      const actions = editing
        ? <><button type="button" className="btn btn-sm" disabled={busy} onClick={() => cancelEdit(section.id)} aria-label={`Abbrechen (${section.title})`}>Abbrechen</button><button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void save()} aria-keyshortcuts="Control+S">{busy ? "Wird gespeichert…" : "Speichern"}</button></>
        : canEditHere
          ? <button type="button" className="btn btn-sm" disabled={busy} onClick={() => startEdit(section.id)} aria-label={`${section.title} bearbeiten`}>Bearbeiten</button>
          : null;
      return <CollapsibleSection key={section.id} id={`rg-${section.id}`} title={section.title} description={editing && dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : section.description} actions={actions} forceOpen={editing || (target !== null && fields.some((def) => def.key === target.key))}>
        <dl className="rg-fields">{fields.map((def) => {
          if (def.kind === "auto_number") {
            const earlier = register.fields.internal_number?.value;
            return <div key={def.key} id="rg-field-register_number" className="rg-field">
              <dt>Interne Nummer</dt>
              <dd>
                <span className="rg-value">{register.register_number ?? "Wird beim ersten Speichern vergeben"}</span>
                <span className="rg-origin rg-origin-system" title="Vom Programm aus dem Nummernkreis vergeben – eindeutig, nicht änderbar">automatisch</span>
                {earlier ? <span className="field-hint rg-help">Frühere interne Nummer: {String(earlier)}</span> : null}
              </dd>
            </div>;
          }
          const provenance = originOf(def);
          const label = def.kind === "period" ? PERIOD_LABEL[def.key as (typeof PERIODS)[number]] : register.fields[def.key]?.label ?? def.key;
          const isTarget = target?.key === def.key;
          const empty = !editing && def.kind !== "bool" && display(def) === "Nicht erfasst";
          return <div key={def.key} id={`rg-field-${def.key}`} className={isTarget ? "rg-field rg-field--target" : "rg-field"} tabIndex={isTarget ? -1 : undefined}>
            <dt>{editing && def.kind !== "period" ? <label htmlFor={`rg-${def.key}`}>{label}</label> : label}</dt>
            <dd>
              {editing ? input(def) : <span className="rg-value">{display(def)}</span>}
              {editing && FIELD_HELP[def.key] ? <span className="field-hint rg-help">{FIELD_HELP[def.key]}</span> : null}
              {!editing && provenance?.origin ? <span className={`rg-origin rg-origin-${provenance.origin}`} title={provenance.source_field ? `Quelle: ${provenance.source_field}` : undefined}>{ORIGIN_LABEL[provenance.origin]}</span> : null}
              {!editing && provenance?.document_source && onShowSource ? <button type="button" className="rg-link" title={`„${provenance.document_source.quote}“`} onClick={() => onShowSource(provenance.document_source!)} aria-label={`Fundstelle von ${label}: Seite ${provenance.document_source.page}`}>S. {provenance.document_source.page}</button> : null}
              {!editing && editable && provenance?.origin === "ai" ? <button type="button" className="rg-link" disabled={busy} onClick={() => confirm(fieldKeys(def))}>Bestätigen</button> : null}
              {empty && editable && register.business_status !== "geloescht" ? <button type="button" className="rg-link" onClick={() => jumpTo(def.key)} aria-label={`${label} erfassen`}>Erfassen</button> : null}
              {empty && editable && onSearchInDocument && searchableKeys?.has(def.key) && register.business_status !== "geloescht" ? <button type="button" className="rg-link" onClick={() => onSearchInDocument(def.key)} aria-label={`${label} im Dokument suchen`}>Im Dokument suchen</button> : null}
              {isTarget && target?.note ? <span className="rg-field-note" role="status">{target.note}</span> : null}
            </dd>
          </div>;
        })}</dl>
        {section.id === "reminder" ? <ReminderLeadsEditor contractId={contractId} orgSlug={orgSlug} register={register} editable={canEditHere} onSaved={(next) => { setRegister(next); onChanged?.(); }} /> : null}
      </CollapsibleSection>;
    })}
  </div>;
}
