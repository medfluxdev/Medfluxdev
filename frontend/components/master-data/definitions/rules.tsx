import { listContractTypes, type ContractTypeDto } from "@/lib/domain-api/catalogs";
import { createRule, listRules, updateRule, type ContractRuleDto, type RuleCatalog, type RuleKind, type RuleValues } from "@/lib/domain-api/rules";
import { optional, text, type EntityDefinition, type FieldDef, type FormValues } from "../types";

export interface RuleContext {
  kinds: RuleCatalog["kinds"];
  fields: RuleCatalog["required_fields"];
  types: ContractTypeDto[];
}

async function loadContext(organizationSlug: string): Promise<RuleContext & { rows: ContractRuleDto[] }> {
  const [catalog, types] = await Promise.all([listRules(organizationSlug), listContractTypes(organizationSlug)]);
  return { kinds: catalog.kinds, fields: catalog.required_fields, types: types.contract_types, rows: catalog.items };
}

function formatNumber(value: string | null) {
  if (value == null) return "";
  return Number(value).toLocaleString("de-DE", { maximumFractionDigits: 2 });
}

// Lesbare Kurzform, z. B. „Kündigungsfrist mindestens 3 Monate“.
export function describeRule(rule: Pick<ContractRuleDto, "rule_kind" | "threshold" | "field_key">, context: Pick<RuleContext, "kinds" | "fields">): string {
  const kind = context.kinds.find((item) => item.key === rule.rule_kind);
  if (!kind) return rule.rule_kind;
  if (rule.rule_kind === "required_field") {
    return `${context.fields.find((item) => item.key === rule.field_key)?.label ?? rule.field_key ?? "Angabe"} vorhanden`;
  }
  return `${kind.label} ${formatNumber(rule.threshold)}${kind.unit ? ` ${kind.unit}` : ""}`;
}

function toValues(form: FormValues): RuleValues {
  const kind = text(form, "rule_kind") as RuleKind;
  return {
    label: text(form, "label"),
    description: optional(form, "description"),
    rule_kind: kind,
    threshold: kind === "required_field" ? null : (text(form, "threshold").replace(",", ".") || null),
    field_key: kind === "required_field" ? optional(form, "field_key") : null,
    contract_type_ids: Array.isArray(form.contract_type_ids) ? form.contract_type_ids : [],
  };
}

export const ruleDefinition: EntityDefinition<ContractRuleDto, RuleContext> = {
  kind: "rule",
  singular: "Vertragsregel",
  plural: "Vertragsregeln",
  objectType: "contract_rule",
  usageLabel: "Verstöße",
  load: async (organizationSlug) => {
    const { rows, ...context } = await loadContext(organizationSlug);
    return { rows, context };
  },
  loadContext: async (organizationSlug) => {
    const { kinds, fields, types } = await loadContext(organizationSlug);
    return { kinds, fields, types };
  },
  id: (row) => row.id,
  label: (row) => row.label,
  formLabel: (form) => text(form, "label"),
  active: (row) => row.is_active,
  searchText: (row, context) => `${row.label} ${row.description ?? ""} ${describeRule(row, context)}`,
  columns: (context) => [
    { key: "label", label: "Regel", rowHeader: true, sortValue: (row) => row.label.toLocaleLowerCase("de"), render: (row) => row.label },
    { key: "check", label: "Prüfung", render: (row) => describeRule(row, context) },
    { key: "types", label: "Gilt für", render: (row) => row.contract_type_ids.length
      ? context.types.filter((type) => row.contract_type_ids.includes(type.id)).map((type) => type.label).join(", ")
      : "Alle Vertragstypen" },
  ],
  fields: (context, form): FieldDef[] => {
    const kind = context.kinds.find((item) => item.key === text(form, "rule_kind"));
    return [
      { key: "label", label: "Bezeichnung", required: true, maxLength: 160, wide: true, hint: "Erscheint in der Vertragsliste, z. B. „Kündigungsfrist ≥ 3 Monate“." },
      {
        key: "rule_kind", label: "Was wird geprüft?", kind: "select", required: true,
        options: context.kinds.map((item) => ({ value: item.key, label: item.label })),
      },
      ...(kind?.key === "required_field"
        ? [{ key: "field_key", label: "Pflichtangabe", kind: "select", required: true, options: context.fields.map((item) => ({ value: item.key, label: item.label })) } as FieldDef]
        : [{ key: "threshold", label: `Grenzwert${kind?.unit ? ` (${kind.unit})` : ""}`, kind: "number", required: true, min: 0, hint: "Fehlt die Angabe am Vertrag, zeigt die Prüfung „Angabe fehlt“ – es wird nichts geschätzt." } as FieldDef]),
      {
        key: "contract_type_ids", label: "Gilt für Vertragstypen", kind: "checks",
        options: context.types.filter((type) => type.is_active).map((type) => ({ value: type.id, label: type.label })),
        hint: "Ohne Auswahl gilt die Regel für alle Verträge.",
      },
      { key: "description", label: "Erläuterung", kind: "textarea", maxLength: 500 },
    ];
  },
  emptyForm: (_context, preset) => ({ label: "", rule_kind: "min_notice_months", threshold: "", field_key: "", contract_type_ids: [], description: "", ...preset }),
  toForm: (row) => ({
    label: row.label, rule_kind: row.rule_kind, threshold: row.threshold ?? "", field_key: row.field_key ?? "",
    contract_type_ids: [...row.contract_type_ids], description: row.description ?? "",
  }),
  create: (organizationSlug, form) => createRule(organizationSlug, toValues(form)),
  update: (organizationSlug, row, form) => updateRule(organizationSlug, row.id, toValues(form)),
  setActive: (organizationSlug, row, active) => updateRule(organizationSlug, row.id, { is_active: active }),
  registerFilter: (row) => ({ column: "rules_violated", value: row.label, op: "contains" }),
  intro: "Regeln prüft das System selbst anhand der gepflegten Vertragsdaten – nicht die KI. Ergebnis je Vertrag: erfüllt, verletzt oder „Angabe fehlt“. In der Vertragsliste stehen die Spalten „Vertragsregeln“ und „Regelverstöße“ zur Verfügung.",
};
