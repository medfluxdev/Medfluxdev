"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { formatDate } from "@/lib/format";
import { listOwnershipAssignees, type AssigneeDto } from "@/lib/domain-api/ownership";
import {
  createPartner,
  listContractTypes,
  listLookups,
  listPartners,
  type ContractCategoryDto,
  type ContractTypeDto,
  type LookupDto,
  type PartnerDto,
} from "@/lib/domain-api/catalogs";
import {
  BUSINESS_STATUS_LABEL,
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

type Draft = Record<string, RegisterValue>;
type FieldKind = "text" | "textarea" | "bool" | "date" | "int" | "decimal" | "period" | "term_model" | "notice_to" | "price_adjustment" | "partner" | "type" | "category" | "account" | "storage" | "todo";
type FieldDef = { key: string; kind: FieldKind };

const PERIODS = ["initial_term", "minimum_term", "notice_period", "renewal_period"] as const;

const SECTIONS: { id: string; title: string; description: string; fields: FieldDef[] }[] = [
  {
    id: "identity",
    title: "Vertrag & Partner",
    description: "Kurzbeschreibung, Vertragspartner und Einordnung",
    fields: [
      { key: "short_description", kind: "text" },
      { key: "internal_number", kind: "text" },
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

const TERM_FIELDS: Record<TermModel, string[]> = {
  fixed_term: ["term_model", "term_start_date", "term_fixed_end_date", "initial_term"],
  terminable: ["term_model", "term_start_date", "notice_period", "notice_to"],
  terminable_min_term: ["term_model", "term_start_date", "minimum_term", "notice_period", "notice_to"],
  auto_renewal: ["term_model", "term_start_date", "term_fixed_end_date", "initial_term", "notice_period", "notice_to", "renewal_period"],
  perpetual: ["term_model", "term_start_date"],
};

const STATUS_TONE: Record<BusinessStatus, string> = {
  in_arbeit: "cw-badge-amber",
  gueltig: "cw-badge-green",
  gekuendigt: "cw-badge-red",
  beendet: "cw-badge-red",
  geloescht: "",
};

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

export default function ContractRegisterPanel({ contractId, orgSlug, onChanged }: { contractId: string; orgSlug: string; onChanged?: () => void }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const isAdmin = Boolean(account?.is_developer || role === "admin");
  const [register, setRegister] = useState<ContractRegister | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [editing, setEditing] = useState(false);
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
  const [newPartner, setNewPartner] = useState<{ short_name: string; name1: string; city: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getContractRegister(orgSlug, contractId);
      setRegister(data);
      setDraft(draftFrom(data));
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Stammdaten konnten nicht geladen werden.") });
    }
  }, [contractId, orgSlug]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      listPartners(orgSlug, { limit: 500 }),
      listContractTypes(orgSlug),
      listLookups(orgSlug),
      editable ? listOwnershipAssignees(orgSlug) : Promise.resolve({ items: [] as AssigneeDto[] }),
    ]).then(([partnerResult, typeResult, lookupResult, assigneeResult]) => {
      if (cancelled) return;
      if (partnerResult.status === "fulfilled") setPartners(partnerResult.value.items);
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
      setEditing(false);
      return;
    }
    if (await run(() => updateContractRegister(orgSlug, contractId, { changes }), "Stammdaten gespeichert.")) setEditing(false);
  }

  function confirm(keys: string[]) {
    void run(() => updateContractRegister(orgSlug, contractId, { changes: {}, confirm: keys }), "KI-Wert bestätigt.");
  }

  function acceptProposal(key: string) {
    void run(() => acceptRegisterProposal(orgSlug, contractId, key), "KI-Vorschlag übernommen.");
  }

  function applySuggestion(key: string, value: string) {
    void run(() => updateContractRegister(orgSlug, contractId, { changes: { [key]: value } }), "Vorschlag übernommen.");
  }

  async function submitNewPartner() {
    if (!newPartner) return;
    setBusy(true);
    setMessage(null);
    try {
      const created = await createPartner(orgSlug, { short_name: newPartner.short_name, name1: newPartner.name1 || newPartner.short_name, city: newPartner.city || null });
      setPartners((current) => [...current, created].sort((a, b) => a.short_name.localeCompare(b.short_name)));
      setDraft((current) => ({ ...current, partner_id: created.id }));
      setNewPartner(null);
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error, "Vertragspartner konnte nicht angelegt werden.") });
    } finally {
      setBusy(false);
    }
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
      case "int": return def.key === "reminder_lead_months" ? `${value} Monat(e) vor der Frist` : def.key === "retention_years_after_end" ? `${value} Jahr(e) nach Vertragsende` : def.key === "price_adjustment_interval_months" ? `alle ${value} Monat(e)` : String(value);
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
          <button type="button" className="rg-link" onClick={() => setNewPartner({ short_name: register?.supplier_text ?? "", name1: register?.supplier_text ?? "", city: "" })}>Neuer Partner</button>
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
  const proposalKeys = Object.entries(register.fields).filter(([, field]) => field.ai_proposed_value).map(([key]) => key);

  return <div className="rg-panel">
    <section className="cw-section rg-status" aria-labelledby="rg-status-heading">
      <div className="rg-status-row">
        <div>
          <h2 id="rg-status-heading">Vertrag {register.register_number ?? "ohne Nummer"}</h2>
          <p className="cw-muted">{register.has_ai_analysis ? "Werte aus der KI-Analyse sind gekennzeichnet und können bestätigt oder korrigiert werden." : "Manuell angelegter Vertrag ohne KI-Analyse."}</p>
        </div>
        <div className="rg-status-actions">
          <span className={`cw-badge ${STATUS_TONE[register.business_status]}`}>{register.business_status_label}</span>
          {editable && register.allowed_transitions.map((item) => <button key={item.target} type="button" className="btn" disabled={busy} onClick={() => { setTransition(item.target); setTransitionForm({ terminated_on: "", effective_date: "", note: "", acknowledge: false }); }}>→ {item.label}</button>)}
        </div>
      </div>
      {register.business_status === "in_arbeit" && register.missing_for_valid.length > 0 ? <p className="rg-hint">Für „Gültig“ fehlen noch: {register.missing_for_valid.map((key) => labelFor(key)).join(", ")}.</p> : null}
      {transition ? <form className="rg-transition" onSubmit={(event) => { event.preventDefault(); void submitTransition(); }}>
        <strong>Statuswechsel nach „{BUSINESS_STATUS_LABEL[transition]}“</strong>
        {transition === "gekuendigt" ? <>
          <label>Gekündigt am<input type="date" required value={transitionForm.terminated_on} onChange={(event) => setTransitionForm((form) => ({ ...form, terminated_on: event.target.value }))} /></label>
          <label>Gekündigt zum<input type="date" required value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label>
        </> : null}
        {transition === "beendet" ? <label>Beendet am<input type="date" value={transitionForm.effective_date} onChange={(event) => setTransitionForm((form) => ({ ...form, effective_date: event.target.value }))} /></label> : null}
        {transition === "gueltig" && register.review_pending ? <label className="rg-check"><input type="checkbox" checked={transitionForm.acknowledge} onChange={(event) => setTransitionForm((form) => ({ ...form, acknowledge: event.target.checked }))} />Die KI-Werte sind noch nicht vollständig geprüft. Ich gebe den Vertrag trotzdem frei.</label> : null}
        {transition === "geloescht" ? <p className="rg-hint">„Gelöscht“ markiert den Vertrag nur. Daten werden nicht entfernt.</p> : null}
        <label>Notiz (optional)<input type="text" maxLength={2000} value={transitionForm.note} onChange={(event) => setTransitionForm((form) => ({ ...form, note: event.target.value }))} /></label>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setTransition(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Status ändern</button></div>
      </form> : null}
    </section>

    <section className="cw-section" aria-labelledby="rg-terms-heading">
      <div className="cw-section-head"><div><h2 id="rg-terms-heading">Berechnete Fristen</h2><p>Deterministisch aus den Stammdaten berechnet (Stand {formatDate(register.as_of)}).</p></div></div>
      {terms.status === "incomplete" ? <p className="rg-hint">Fristen noch nicht berechenbar. Es fehlen: {terms.missing.map((key) => labelFor(key)).join(", ")}.</p> : null}
      <div className="rg-terms">
        <div><span>Kündbar bis</span><strong>{terms.cancel_by ? formatDate(terms.cancel_by) : "–"}</strong></div>
        <div><span>{terms.actual_end ? "Tatsächliches Ende" : "Mögliches Vertragsende"}</span><strong>{formatDate(terms.actual_end ?? terms.possible_end)}</strong></div>
        <div><span>Frühestes / festes Ende</span><strong>{formatDate(terms.earliest_end)}</strong></div>
        <div><span>Erinnerung am</span><strong>{formatDate(terms.reminder_date)}</strong></div>
      </div>
      {terms.explanation.length > 0 ? <ul className="rg-explanation">{terms.explanation.map((line) => <li key={line}>{line}</li>)}</ul> : null}
    </section>

    <section className="cw-section" aria-labelledby="rg-protection-heading">
      <div className="cw-section-head"><div><h2 id="rg-protection-heading">Vertraulichkeit & Aufbewahrung</h2><p>Wer den Vertrag sehen darf und ab wann er gelöscht werden darf.</p></div></div>
      <div className="rg-terms">
        <div><span>Vertraulich</span><strong>{register.confidentiality.effective ? (register.confidentiality.type_confidential && !register.confidentiality.is_confidential ? "Ja (über Vertragstyp)" : "Ja") : "Nein"}</strong></div>
        <div><span>Aufbewahrung</span><strong>{register.retention.years == null ? "Nicht festgelegt" : `${register.retention.years} Jahr(e) nach Vertragsende`}</strong>{register.retention.source ? <small className="cw-muted">{register.retention.source === "contract" ? "am Vertrag festgelegt" : "aus Vertragstyp"}</small> : null}</div>
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

    {newPartner ? <form className="cw-section rg-transition" aria-label="Neuen Vertragspartner anlegen" onSubmit={(event) => { event.preventDefault(); void submitNewPartner(); }}>
      <strong>Neuen Vertragspartner anlegen</strong>
      <label>Kurzname<input required value={newPartner.short_name} onChange={(event) => setNewPartner((form) => form && ({ ...form, short_name: event.target.value }))} /></label>
      <label>Name<input value={newPartner.name1} onChange={(event) => setNewPartner((form) => form && ({ ...form, name1: event.target.value }))} /></label>
      <label>Ort<input value={newPartner.city} onChange={(event) => setNewPartner((form) => form && ({ ...form, city: event.target.value }))} /></label>
      <div className="rg-actions"><button type="button" className="btn" onClick={() => setNewPartner(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Partner anlegen</button></div>
    </form> : null}

    <div className="rg-toolbar">
      {editable && !editing && register.business_status !== "geloescht" ? <button type="button" className="btn btn-primary" onClick={() => { setDraft(draftFrom(register)); setEditing(true); setMessage(null); }}>Stammdaten bearbeiten</button> : null}
      {editing ? <><button type="button" className="btn" disabled={busy} onClick={() => { setEditing(false); setDraft(draftFrom(register)); setNewPartner(null); }}>Abbrechen</button><button type="button" className="btn btn-primary" disabled={busy} onClick={() => void save()}>{busy ? "Wird gespeichert…" : "Speichern"}</button></> : null}
      <Link href="/partners" className="rg-link">Vertragspartner verwalten</Link>
    </div>

    {SECTIONS.map((section) => {
      const fields = section.id === "term" ? section.fields.filter((def) => visibleTermFields.has(def.key)) : section.fields;
      return <section className="cw-section" key={section.id} aria-labelledby={`rg-${section.id}-heading`}>
        <div className="cw-section-head"><div><h2 id={`rg-${section.id}-heading`}>{section.title}</h2><p>{section.description}</p></div></div>
        <dl className="rg-fields">{fields.map((def) => {
          const provenance = originOf(def);
          const label = def.kind === "period" ? PERIOD_LABEL[def.key as (typeof PERIODS)[number]] : register.fields[def.key]?.label ?? def.key;
          return <div key={def.key} className="rg-field">
            <dt>{editing && def.kind !== "period" ? <label htmlFor={`rg-${def.key}`}>{label}</label> : label}</dt>
            <dd>
              {editing ? input(def) : <span className="rg-value">{display(def)}</span>}
              {!editing && provenance?.origin ? <span className={`rg-origin rg-origin-${provenance.origin}`} title={provenance.source_field ? `Quelle: ${provenance.source_field}` : undefined}>{ORIGIN_LABEL[provenance.origin]}</span> : null}
              {!editing && editable && provenance?.origin === "ai" ? <button type="button" className="rg-link" disabled={busy} onClick={() => confirm(fieldKeys(def))}>Bestätigen</button> : null}
            </dd>
          </div>;
        })}</dl>
      </section>;
    })}
  </div>;
}
