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

// Verständliche Angaben sofort (Feldname deutsch, vorher → nachher); technische Rohdaten nur auf Wunsch (U9).
export default function HistoryDetails({ details, fieldLabels = {} }: { details: Record<string, unknown>; fieldLabels?: Record<string, string> }) {
  const entries = Object.entries(details ?? {}).filter(([key]) => !key.endsWith("_id") && key !== "deadline_id");
  if (entries.length === 0) return null;
  const readable = entries.filter(([key]) => key === "fields" || key in KEY_LABEL);
  const technical = entries.filter(([key]) => !(key === "fields" || key in KEY_LABEL));
  return <>
    {readable.length > 0 ? <ul className="hist-details">
      {readable.flatMap(([key, value]) => key === "fields" && value && typeof value === "object" && !Array.isArray(value)
        ? Object.entries(value as Record<string, unknown>).map(([field, change]) => <li key={`${key}.${field}`}><span>{fieldLabels[field] ?? field}</span> {text(change)}</li>)
        : [<li key={key}><span>{KEY_LABEL[key]}</span> {text(value)}</li>])}
    </ul> : null}
    {technical.length > 0 ? <details className="hist-technical"><summary>Technische Details</summary><ul className="hist-details">
      {technical.map(([key, value]) => <li key={key}><span>{key}</span> {text(value)}</li>)}
    </ul></details> : null}
  </>;
}
