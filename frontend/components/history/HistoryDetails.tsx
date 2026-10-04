const KEY_LABEL: Record<string, string> = {
  fields: "Felder",
  from: "von",
  to: "nach",
  note: "Notiz",
  title: "Titel",
  attachment_type: "Dokumentart",
  recipient: "Empfänger",
  subject: "Betreff",
  previous_effective_value: "vorher",
  new_effective_value: "jetzt",
  old_value: "vorher",
  value: "Wert",
  row_count: "Zeilen",
  due_date: "fällig",
};

function text(value: unknown): string {
  if (value == null || value === "") return "–";
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  if (Array.isArray(value)) return value.map(text).join(", ") || "–";
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if ("before" in record || "after" in record) return `${text(record.before)} → ${text(record.after)}`;
    if ("value" in record && Object.keys(record).length <= 2) return text(record.value);
    return Object.entries(record).map(([key, inner]) => `${KEY_LABEL[key] ?? key}: ${text(inner)}`).join("; ");
  }
  return String(value);
}

export default function HistoryDetails({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details ?? {}).filter(([key]) => !key.endsWith("_id") && key !== "deadline_id");
  if (entries.length === 0) return null;
  return <ul className="hist-details">
    {entries.flatMap(([key, value]) => key === "fields" && value && typeof value === "object" && !Array.isArray(value)
      ? Object.entries(value as Record<string, unknown>).map(([field, change]) => <li key={`${key}.${field}`}><span>{field}</span> {text(change)}</li>)
      : [<li key={key}><span>{KEY_LABEL[key] ?? key}</span> {text(value)}</li>])}
  </ul>;
}
