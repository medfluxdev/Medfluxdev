"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import PageHeader from "@/components/ui/PageHeader";
import { getOrganizationStructure } from "@/lib/domain-api/organizations";
import {
  listContractTypes,
  listPartners,
  type ContractCategoryDto,
  type ContractTypeDto,
  type PartnerDto,
} from "@/lib/domain-api/catalogs";
import {
  DURATION_UNIT_LABEL,
  NOTICE_TO_LABEL,
  TERM_MODEL_LABEL,
  createRegisterContract,
  type DurationUnit,
  type NoticeTo,
  type RegisterValue,
  type TermModel,
} from "@/lib/domain-api/register";

type Hospital = { id: string; name: string; is_active: boolean };

const EMPTY = {
  short_description: "",
  partner_id: "",
  contract_type_id: "",
  contract_category_id: "",
  term_model: "",
  term_start_date: "",
  term_fixed_end_date: "",
  notice_period_value: "",
  notice_period_unit: "months",
  notice_to: "",
  renewal_period_value: "",
  renewal_period_unit: "years",
  minimum_term_value: "",
  minimum_term_unit: "years",
};

export default function NewContractPage() {
  const router = useRouter();
  const { organizationSlug, role, account } = useAuth();
  const canCreate = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [form, setForm] = useState(EMPTY);
  const [hospitalId, setHospitalId] = useState("");
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [partners, setPartners] = useState<PartnerDto[]>([]);
  const [types, setTypes] = useState<ContractTypeDto[]>([]);
  const [categories, setCategories] = useState<ContractCategoryDto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!organizationSlug || !canCreate) return;
    let cancelled = false;
    Promise.allSettled([
      listPartners(organizationSlug, { limit: 500 }),
      listContractTypes(organizationSlug),
      role === "admin" || account?.is_developer ? getOrganizationStructure(organizationSlug) : Promise.resolve(null),
    ]).then(([partnerResult, typeResult, structureResult]) => {
      if (cancelled) return;
      if (partnerResult.status === "fulfilled") setPartners(partnerResult.value.items);
      if (typeResult.status === "fulfilled") {
        setTypes(typeResult.value.contract_types.filter((item) => item.is_active));
        setCategories(typeResult.value.contract_categories.filter((item) => item.is_active));
      }
      if (structureResult.status === "fulfilled" && structureResult.value) {
        setHospitals((structureResult.value.hospitals ?? []).filter((item: Hospital) => item.is_active));
      }
    });
    return () => { cancelled = true; };
  }, [account?.is_developer, canCreate, organizationSlug, role]);

  const visibleCategories = useMemo(
    () => (form.contract_type_id ? categories.filter((item) => item.contract_type_ids.includes(form.contract_type_id)) : categories),
    [categories, form.contract_type_id],
  );
  const model = form.term_model as TermModel | "";
  const needsNotice = model === "terminable" || model === "terminable_min_term" || model === "auto_renewal";
  const needsEnd = model === "fixed_term" || model === "auto_renewal";

  function set<K extends keyof typeof EMPTY>(key: K, value: string) {
    setForm((current) => ({ ...current, [key]: value, ...(key === "contract_type_id" ? { contract_category_id: "" } : {}) }));
  }

  async function submit() {
    if (!organizationSlug) return;
    setBusy(true);
    setError(null);
    const values: Record<string, RegisterValue> = {};
    const text = (key: keyof typeof EMPTY) => (form[key].trim() ? form[key].trim() : null);
    values.short_description = text("short_description");
    for (const key of ["partner_id", "contract_type_id", "contract_category_id", "term_model", "term_start_date"] as const) {
      if (text(key)) values[key] = text(key);
    }
    if (needsEnd && text("term_fixed_end_date")) values.term_fixed_end_date = text("term_fixed_end_date");
    if (needsNotice && text("notice_period_value")) {
      values.notice_period_value = Number(form.notice_period_value);
      values.notice_period_unit = form.notice_period_unit;
    }
    if (needsNotice && text("notice_to")) values.notice_to = text("notice_to");
    if (model === "auto_renewal" && text("renewal_period_value")) {
      values.renewal_period_value = Number(form.renewal_period_value);
      values.renewal_period_unit = form.renewal_period_unit;
    }
    if (model === "terminable_min_term" && text("minimum_term_value")) {
      values.minimum_term_value = Number(form.minimum_term_value);
      values.minimum_term_unit = form.minimum_term_unit;
    }
    try {
      const created = await createRegisterContract(organizationSlug, { hospital_id: hospitalId || null, values });
      router.push(`/contracts/${created.contract_id}?tab=register`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Vertrag konnte nicht angelegt werden.");
      setBusy(false);
    }
  }

  if (!canCreate) {
    return <div className="page"><p>Keine Berechtigung zum Anlegen von Verträgen.</p></div>;
  }

  const units = Object.keys(DURATION_UNIT_LABEL) as DurationUnit[];

  return <div className="page">
    <PageHeader
      title="Vertrag anlegen"
      description="Vertrag ohne Dokument erfassen. Dokumente und KI-Analyse können später ergänzt werden."
      actions={<Link href="/import" className="btn">Stattdessen Dokument importieren</Link>}
    />
    <form className="cw-section" aria-label="Neuer Vertrag" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div className="rg-form-grid">
        <label style={{ gridColumn: "1 / -1" }}>Kurzbeschreibung *<input required maxLength={500} value={form.short_description} onChange={(event) => set("short_description", event.target.value)} /></label>
        {hospitals.length > 0 ? <label>Krankenhaus / Gesellschaft<select value={hospitalId} onChange={(event) => setHospitalId(event.target.value)}><option value="">Organisationsweit</option>{hospitals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : null}
        <label>Vertragspartner<select value={form.partner_id} onChange={(event) => set("partner_id", event.target.value)}><option value="">Später auswählen</option>{partners.map((item) => <option key={item.id} value={item.id}>{item.short_name}{item.city ? ` · ${item.city}` : ""}</option>)}</select></label>
        <label>Vertragstyp<select value={form.contract_type_id} onChange={(event) => set("contract_type_id", event.target.value)}><option value="">Bitte auswählen</option>{types.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>Kategorie<select value={form.contract_category_id} onChange={(event) => set("contract_category_id", event.target.value)}><option value="">Bitte auswählen</option>{visibleCategories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <label>Vertragsart<select value={form.term_model} onChange={(event) => set("term_model", event.target.value)}><option value="">Bitte auswählen</option>{(Object.keys(TERM_MODEL_LABEL) as TermModel[]).map((value) => <option key={value} value={value}>{TERM_MODEL_LABEL[value]}</option>)}</select></label>
        <label>Vertragsbeginn<input type="date" value={form.term_start_date} onChange={(event) => set("term_start_date", event.target.value)} /></label>
        {needsEnd ? <label>Festes Vertragsende<input type="date" value={form.term_fixed_end_date} onChange={(event) => set("term_fixed_end_date", event.target.value)} /></label> : null}
        {model === "terminable_min_term" ? <label>Mindestlaufzeit<span className="rg-period"><input type="number" min={0} aria-label="Mindestlaufzeit (Anzahl)" value={form.minimum_term_value} onChange={(event) => set("minimum_term_value", event.target.value)} /><select aria-label="Mindestlaufzeit (Einheit)" value={form.minimum_term_unit} onChange={(event) => set("minimum_term_unit", event.target.value)}>{units.map((unit) => <option key={unit} value={unit}>{DURATION_UNIT_LABEL[unit]}</option>)}</select></span></label> : null}
        {needsNotice ? <label>Kündigungsfrist<span className="rg-period"><input type="number" min={0} aria-label="Kündigungsfrist (Anzahl)" value={form.notice_period_value} onChange={(event) => set("notice_period_value", event.target.value)} /><select aria-label="Kündigungsfrist (Einheit)" value={form.notice_period_unit} onChange={(event) => set("notice_period_unit", event.target.value)}>{units.map((unit) => <option key={unit} value={unit}>{DURATION_UNIT_LABEL[unit]}</option>)}</select></span></label> : null}
        {needsNotice ? <label>Kündigung zum<select value={form.notice_to} onChange={(event) => set("notice_to", event.target.value)}><option value="">Bitte auswählen</option>{(Object.keys(NOTICE_TO_LABEL) as NoticeTo[]).map((value) => <option key={value} value={value}>{NOTICE_TO_LABEL[value]}</option>)}</select></label> : null}
        {model === "auto_renewal" ? <label>Verlängerung um<span className="rg-period"><input type="number" min={0} aria-label="Verlängerung (Anzahl)" value={form.renewal_period_value} onChange={(event) => set("renewal_period_value", event.target.value)} /><select aria-label="Verlängerung (Einheit)" value={form.renewal_period_unit} onChange={(event) => set("renewal_period_unit", event.target.value)}>{units.map((unit) => <option key={unit} value={unit}>{DURATION_UNIT_LABEL[unit]}</option>)}</select></span></label> : null}
      </div>
      {error ? <p role="alert" className="rg-error">{error}</p> : null}
      <div className="rg-actions" style={{ marginTop: 16 }}>
        <Link href="/contracts" className="btn">Abbrechen</Link>
        <button type="submit" className="btn btn-primary" disabled={busy || !form.short_description.trim()}>{busy ? "Wird angelegt…" : "Vertrag anlegen"}</button>
      </div>
      <p className="cw-muted">Der Vertrag erhält automatisch die nächste Vertragsnummer und startet im Status „In Arbeit“. Weitere Angaben folgen in den Stammdaten.</p>
    </form>
  </div>;
}
