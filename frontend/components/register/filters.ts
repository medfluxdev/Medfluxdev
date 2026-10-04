import type { ColumnType, FilterOp, GridColumn, GridFilter } from "@/lib/domain-api/registerGrid";
import { formatDate } from "@/lib/format";

export const OPS_BY_TYPE: Record<ColumnType, FilterOp[]> = {
  text: ["contains", "empty", "not_empty"],
  enum: ["in", "empty", "not_empty"],
  status: ["in"],
  account: ["me", "in", "empty", "not_empty"],
  bool: ["is"],
  date: ["within_days", "due_within_days", "overdue", "range", "empty", "not_empty"],
  money: ["range", "empty", "not_empty"],
  number: ["range", "empty", "not_empty"],
};

export const OP_LABEL: Record<FilterOp, string> = {
  contains: "enthält",
  empty: "ist leer",
  not_empty: "ist nicht leer",
  in: "ist einer von",
  me: "bin ich",
  is: "ist",
  within_days: "in den nächsten … Tagen",
  due_within_days: "fällig bis in … Tagen (inkl. überfällig)",
  overdue: "heute oder früher",
  range: "von … bis",
};

function rangeText(value: unknown, type: ColumnType) {
  const bounds = (value ?? {}) as { from?: string; to?: string };
  const show = (part?: string) => (part ? (type === "date" ? formatDate(part) : part) : "…");
  return `${show(bounds.from)} – ${show(bounds.to)}`;
}

export function describeFilter(filter: GridFilter, column: GridColumn | undefined): string {
  const label = column?.label ?? filter.column;
  switch (filter.op) {
    case "contains": return `${label} enthält „${String(filter.value ?? "")}“`;
    case "in": {
      const values = Array.isArray(filter.value) ? filter.value.map(String) : [];
      const named = values.map((value) => column?.options?.find((option) => option.value === value)?.label ?? (value === "" ? "(ohne)" : value));
      return `${label}: ${named.join(", ") || "–"}`;
    }
    case "is": return `${label}: ${filter.value ? "Ja" : "Nein"}`;
    case "within_days": return `${label} in den nächsten ${String(filter.value ?? 0)} Tagen`;
    case "due_within_days": return `${label} fällig bis in ${String(filter.value ?? 0)} Tagen`;
    case "range": return `${label}: ${rangeText(filter.value, column?.type ?? "text")}`;
    case "me": return `${label}: ich`;
    default: return `${label} ${OP_LABEL[filter.op]}`;
  }
}
