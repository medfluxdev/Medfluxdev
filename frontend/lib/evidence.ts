import type { SignalTone } from "@/components/ui/Signal";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import type { EvidenceReviewItem } from "@/lib/domain-api/register";
import { formatDate } from "@/lib/format";
import { evidencePrecision } from "@/lib/source-geometry";

/** Nachweise: Lage, Reihenfolge, Abschnitt, Prüfstand und Abgleich Dokument ↔ MedFlux (eine Quelle für Dokumente und „Nachweise prüfen“). */

export type Precision = "exact" | "approx" | "page" | "none";
export const PRECISION: Record<Precision, { label: string; tone: SignalTone; hint: string }> = {
  exact: { label: "Genau", tone: "done", hint: "Der Wortlaut steht genau an der markierten Stelle." },
  approx: { label: "Ungefähre Lage", tone: "warning", hint: "Die Stelle ist nur grob markiert – der Wortlaut wurde in der Box nicht nachgewiesen." },
  page: { label: "Nur Seite", tone: "neutral", hint: "Die Seite ist bekannt, aber keine Position auf der Seite." },
  none: { label: "Ohne Seite", tone: "warning", hint: "Keine Seitenangabe – die Quelle lässt sich im Original nicht anzeigen." },
};

/** Lage: vom Backend belegt (`location`), sonst aus der Geometrie geschätzt – „Genau“ nur mit Textbeleg. */
export function precisionOf(ref: EvidenceRef): Precision {
  if (ref.location) return ref.location;
  if (ref.page == null) return "none";
  if (!ref.bbox) return "page";
  if (evidencePrecision(ref.bbox, ref.bbox_space) === "coarse") return "approx";
  return ref.supports_exact_navigation ? "exact" : "approx";
}

export function where(ref: EvidenceRef): string | null {
  if (ref.page != null) return `Seite ${ref.page}`;
  if (ref.paragraph_index != null) return `Absatz ${ref.paragraph_index}`;
  if (ref.table_index != null) return `Tabelle ${ref.table_index}`;
  return null;
}

/**
 * Lesereihenfolge: Datei (Reihenfolge der Dokumente), Seite, Lage auf der Seite (oben → unten), Absatz/Tabelle;
 * ohne Seite am Ende. Die Nummer (1 … N) ist fest – Filter und Suche ändern sie nicht.
 */
export function orderEvidence(evidence: EvidenceRef[], documentIds: string[] = []): EvidenceRef[] {
  const docIndex = (ref: EvidenceRef) => { const index = documentIds.indexOf(ref.document_version_id ?? ""); return index < 0 ? documentIds.length : index; };
  const top = (ref: EvidenceRef) => (ref.bbox ? Math.min(ref.bbox.y0, ref.bbox.y1) : Number.MAX_SAFE_INTEGER);
  return evidence.map((ref, index) => ({ ref, index })).sort((a, b) =>
    docIndex(a.ref) - docIndex(b.ref)
    || (a.ref.page ?? Number.MAX_SAFE_INTEGER) - (b.ref.page ?? Number.MAX_SAFE_INTEGER)
    || top(a.ref) - top(b.ref)
    || (a.ref.paragraph_index ?? Number.MAX_SAFE_INTEGER) - (b.ref.paragraph_index ?? Number.MAX_SAFE_INTEGER)
    || (a.ref.table_index ?? Number.MAX_SAFE_INTEGER) - (b.ref.table_index ?? Number.MAX_SAFE_INTEGER)
    || a.index - b.index).map((entry) => entry.ref);
}

/** Nummer je Nachweis (1-basiert, in Lesereihenfolge) – dieselbe in Liste, Marke und Prüfung. */
export function evidenceNumbers(ordered: EvidenceRef[]): Map<string, number> {
  return new Map(ordered.map((ref, index) => [ref.evidence_id, index + 1]));
}

/** Prüf-Angabe zu jedem Nachweis (über die verknüpften Belege). */
export function factsByEvidence(facts: FactReviewStateDto[]): Map<string, FactReviewStateDto> {
  const map = new Map<string, FactReviewStateDto>();
  for (const fact of facts) for (const id of fact.linked_evidence_refs ?? []) if (id && !map.has(id)) map.set(id, fact);
  return map;
}

/** Lesbare Überschrift: Name der Prüf-Angabe (ohne „Nachweis:“), sonst aus dem Quellfeld, nie eine Roh-ID. */
export function titleOf(ref: EvidenceRef, factByEvidence: Map<string, FactReviewStateDto>): string {
  const fact = factByEvidence.get(ref.evidence_id);
  if (fact) return fact.label_de.replace(/^Nachweis:\s*/, "");
  const parts = (ref.field_ref ?? "").split(".").filter((part) => part && part !== "evidence" && !/^\d+$/.test(part));
  const index = (ref.field_ref ?? "").match(/\.(\d+)(?:\.|$)/)?.[1];
  if ((ref.field_ref ?? "").includes("cost_line") && index != null) return `Kostenposition ${Number(index) + 1}`;
  const last = parts[parts.length - 1];
  if (!last) return "Nachweis";
  const words = last.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** KI-Sicherheit (0..1) des Nachweises, sonst der Angabe; null = keine Angabe. */
export function confidenceOf(ref: EvidenceRef, fact: FactReviewStateDto | undefined): number | null {
  const value = ref.confidence ?? fact?.ai_confidence ?? null;
  return value != null && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)} %`;
}

// ---------------------------------------------------------------------------- Abschnitte

export type SectionTone = "partner" | "accent" | "cost" | "type" | "device" | "neutral";
export interface EvidenceSection { key: string; label: string; tone: SectionTone }

/** Reihenfolge der geführten Prüfung; Kennfarbe je Abschnitt (wie die Karten der Vertragsakte). */
export const EVIDENCE_SECTIONS: (EvidenceSection & { groups: string[] })[] = [
  { key: "partner", label: "Vertrag & Partner", tone: "partner", groups: ["identity"] },
  { key: "term", label: "Laufzeit", tone: "accent", groups: ["dates", "termination"] },
  { key: "cost", label: "Kosten", tone: "cost", groups: ["costs", "payment"] },
  { key: "services", label: "Leistungen", tone: "type", groups: ["scope", "services", "sla"] },
  { key: "device", label: "Gerät", tone: "device", groups: ["equipment", "identity_equipment"] },
  { key: "other", label: "Weitere Angaben", tone: "neutral", groups: [] },
];

/** Abschnitt nach Schlüssel (z. B. aus einem Vorschlag der erneuten Erfassung). */
export function sectionByKey(key: string): EvidenceSection {
  const found = EVIDENCE_SECTIONS.find((section) => section.key === key) ?? EVIDENCE_SECTIONS[EVIDENCE_SECTIONS.length - 1];
  return { key: found.key, label: found.label, tone: found.tone };
}

function groupOf(ref: EvidenceRef, fact: FactReviewStateDto | undefined): string {
  const key = fact?.fact_key.replace(/^evidence\./, "") ?? ref.field_ref ?? "";
  if (key.startsWith("identity.system_identity")) return "equipment";
  return key.split(".")[0] ?? "";
}

export function sectionOf(ref: EvidenceRef, fact: FactReviewStateDto | undefined): EvidenceSection {
  const group = groupOf(ref, fact);
  const found = EVIDENCE_SECTIONS.find((section) => section.groups.includes(group)) ?? EVIDENCE_SECTIONS[EVIDENCE_SECTIONS.length - 1];
  return { key: found.key, label: found.label, tone: found.tone };
}

/** Geführte Reihenfolge: nach Abschnitt, darin in Lesereihenfolge (Seite, oben → unten). */
export function guidedOrder(ordered: EvidenceRef[], factByEvidence: Map<string, FactReviewStateDto>): EvidenceRef[] {
  const rank = (ref: EvidenceRef) => EVIDENCE_SECTIONS.findIndex((section) => section.key === sectionOf(ref, factByEvidence.get(ref.evidence_id)).key);
  return ordered.map((ref, index) => ({ ref, index })).sort((a, b) => rank(a.ref) - rank(b.ref) || a.index - b.index).map((entry) => entry.ref);
}

// ---------------------------------------------------------------------------- Prüfstand

export type EvidenceStatus = "open" | "confirmed" | "deviation" | "skipped";
export const STATUS_VIEW: Record<EvidenceStatus, { label: string; tone: SignalTone }> = {
  open: { label: "Noch nicht geprüft", tone: "neutral" },
  confirmed: { label: "Bestätigt", tone: "done" },
  deviation: { label: "Abweichend", tone: "warning" },
  skipped: { label: "Übersprungen", tone: "neutral" },
};
const HUMAN_DONE = new Set(["confirmed", "corrected"]);

/**
 * Prüfstand eines Nachweises: das Ergebnis der Nachweisprüfung; ohne eines zählt eine frühere Bestätigung der
 * Angabe nur, wenn die Fundstelle genau belegt ist („Nur Seite“/„ungefähr“ bleibt offen, automatische Übernahme auch).
 */
export function evidenceStatus(ref: EvidenceRef, fact: FactReviewStateDto | undefined, review: EvidenceReviewItem | undefined): EvidenceStatus {
  if (review) return review.status === "confirmed" ? "confirmed" : review.status === "skipped" ? "skipped" : "deviation";
  if (fact && HUMAN_DONE.has(fact.state) && precisionOf(ref) === "exact") return "confirmed";
  return "open";
}

// ---------------------------------------------------------------------------- Werte

const MONEY = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
const NUMBER = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 });

/** Anzeige eines Fakt-Werts wie in den Vertragsdaten (Datum TT.MM.JJJJ, Beträge in Euro); null = kein Wert. */
export function valueText(factKey: string, value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  const numeric = typeof value === "number" ? value : typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value.trim()) ? Number(value) : null;
  if (numeric != null && Number.isFinite(numeric)) {
    if (/vat_rate|tax_rate|percent/.test(factKey)) return `${NUMBER.format(numeric)} %`;
    if (factKey.startsWith("costs.")) return MONEY.format(numeric);
    return NUMBER.format(numeric);
  }
  if (typeof value === "string") {
    const text = value.trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? formatDate(text) : text;
  }
  const json = JSON.stringify(value);
  return json ? (json.length > 160 ? `${json.slice(0, 160)}…` : json) : null;
}

/** „Im Dokument (erkannt)“: der erkannte Wert der Angabe; bei reinen Nachweisen der Wortlaut. */
export function documentValue(ref: EvidenceRef, fact: FactReviewStateDto | undefined): string | null {
  if (fact && !fact.is_evidence_item) return valueText(fact.fact_key, fact.original_value);
  return ref.snippet?.trim() || null;
}

/**
 * „In MedFlux gespeichert“: der Wert in den Vertragsdaten (Angaben mit eigenem Feld), sonst der wirksame Wert der
 * Angabe. Reine Nachweise ohne Angabe haben keinen gespeicherten Wert (null).
 */
export function storedValue(fact: FactReviewStateDto | undefined): string | null {
  if (!fact || fact.is_evidence_item) return null;
  if (fact.register_field) return fact.stored_value ?? null;
  return valueText(fact.fact_key, fact.effective_value);
}

/** Vergleichsschlüssel: ohne Leerraum, Satz- und Sonderzeichen, Groß/Klein („Frankfurtam Main“ = „Frankfurt am Main“). */
export function matchKey(text: string | null | undefined): string {
  return (text ?? "").normalize("NFKC").toLocaleLowerCase("de-DE").replace(/[\s\p{P}\p{S}_]+/gu, "");
}

export function sameText(a: string | null | undefined, b: string | null | undefined): boolean {
  const key = matchKey(a);
  return key.length > 0 && key === matchKey(b);
}

export interface DiffToken { text: string; changed: boolean }

/** Einfacher Wortvergleich (LCS über die Vergleichsschlüssel der Wörter); geänderte Wörter beider Seiten markiert. */
export function wordDiff(a: string, b: string): { a: DiffToken[]; b: DiffToken[] } {
  const left = a.split(/\s+/).filter(Boolean);
  const right = b.split(/\s+/).filter(Boolean);
  const lk = left.map(matchKey);
  const rk = right.map(matchKey);
  const table = Array.from({ length: left.length + 1 }, () => new Array<number>(right.length + 1).fill(0));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      table[i][j] = lk[i] === rk[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const keepLeft = new Set<number>();
  const keepRight = new Set<number>();
  for (let i = 0, j = 0; i < left.length && j < right.length;) {
    if (lk[i] === rk[j]) { keepLeft.add(i); keepRight.add(j); i += 1; j += 1; }
    else if (table[i + 1][j] >= table[i][j + 1]) i += 1;
    else j += 1;
  }
  return {
    a: left.map((text, index) => ({ text, changed: !keepLeft.has(index) && lk[index] !== "" })),
    b: right.map((text, index) => ({ text, changed: !keepRight.has(index) && rk[index] !== "" })),
  };
}

// ---------------------------------------------------------------------------- Zeilen und Runde

export interface EvidenceRow {
  ref: EvidenceRef;
  fact: FactReviewStateDto | undefined;
  number: number;
  title: string;
  section: EvidenceSection;
  status: EvidenceStatus;
}

export function evidenceRows(
  ordered: EvidenceRef[],
  numbers: Map<string, number>,
  factByEvidence: Map<string, FactReviewStateDto>,
  statusOf: (ref: EvidenceRef) => EvidenceStatus,
): EvidenceRow[] {
  return ordered.map((ref, index) => {
    const fact = factByEvidence.get(ref.evidence_id);
    return { ref, fact, number: numbers.get(ref.evidence_id) ?? index + 1, title: titleOf(ref, factByEvidence), section: sectionOf(ref, fact), status: statusOf(ref) };
  });
}

/** „34 geprüft: 30 bestätigt · 3 abweichend (übernommen 2, geklärt 1) · 1 übersprungen“ (wie der Eintrag im Verlauf). */
export function roundSummary(counts: Partial<Record<EvidenceReviewItem["status"], number>>): string {
  const n = (key: EvidenceReviewItem["status"]) => counts[key] ?? 0;
  const deviating = n("document") + n("medflux") + n("manual");
  const parts = [`${n("confirmed")} bestätigt`];
  if (deviating) {
    const detail = [[n("document"), `übernommen ${n("document")}`], [n("medflux"), `geklärt ${n("medflux")}`], [n("manual"), `von Hand ${n("manual")}`]]
      .filter(([value]) => value).map(([, text]) => text);
    parts.push(`${deviating} abweichend (${detail.join(", ")})`);
  }
  if (n("skipped")) parts.push(`${n("skipped")} übersprungen`);
  return `${n("confirmed") + deviating + n("skipped")} geprüft: ${parts.join(" · ")}`;
}
