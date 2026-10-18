import type { SignalTone } from "@/components/ui/Signal";
import type { EvidenceRef, FactReviewStateDto, FieldReviewDto } from "@/lib/contract-detail-types";
import type { EvidenceReviewItem } from "@/lib/domain-api/register";
import { formatDate } from "@/lib/format";
import { evidencePrecision } from "@/lib/source-geometry";

/** Nachweise: Lage, Reihenfolge, Abschnitt, Prüfstand und Abgleich Dokument ↔ MedFlux (eine Quelle für Dokumente und „Nachweise prüfen“). */

export type Precision = "exact" | "approx" | "page" | "none";
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

// ---------------------------------------------------------------------------- Abschnitte

export type SectionTone = "partner" | "accent" | "cost" | "type" | "device" | "neutral";
export interface EvidenceSection { key: string; label: string; tone: SectionTone }

/** Reihenfolge der geführten Prüfung; Kennfarbe je Abschnitt, Name wie der Reiter der Vertragsakte, in dem die Angabe steht
 *  (gleiche Namen in der KI-Analyse, Backend `reextract/facts.SECTIONS`). */
export const EVIDENCE_SECTIONS: (EvidenceSection & { groups: string[] })[] = [
  { key: "partner", label: "Vertragsdaten", tone: "partner", groups: ["identity"] },
  { key: "term", label: "Fristen & Aufgaben", tone: "accent", groups: ["dates", "termination"] },
  { key: "cost", label: "Finanzen", tone: "cost", groups: ["costs", "payment"] },
  { key: "services", label: "Leistungen & SLA", tone: "type", groups: ["scope", "services", "sla"] },
  { key: "device", label: "Verknüpfungen (Geräte)", tone: "device", groups: ["equipment", "identity_equipment"] },
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

// ---------------------------------------------------------------------------- Prüfstand

export type EvidenceStatus = "open" | "confirmed" | "deviation" | "skipped" | "excluded" | "extra";
/** Stand eines Nachweises = Stand seines Felds (ein Feld, eine Entscheidung) – nicht ein eigener Prüfauftrag. */
export const STATUS_VIEW: Record<EvidenceStatus, { label: string; tone: SignalTone }> = {
  open: { label: "Offen", tone: "neutral" },
  confirmed: { label: "Entschieden", tone: "done" },
  deviation: { label: "Widerspruch", tone: "warning" },
  skipped: { label: "Zurückgestellt", tone: "neutral" },
  excluded: { label: "Ausgeschlossen", tone: "neutral" },
  extra: { label: "Weitere Information", tone: "neutral" },
};

const statusCache = new WeakMap<FieldReviewDto, Map<string, EvidenceStatus>>();

function fieldStatusMap(review: FieldReviewDto): Map<string, EvidenceStatus> {
  const cached = statusCache.get(review);
  if (cached) return cached;
  const map = new Map<string, EvidenceStatus>();
  for (const finding of review.findings) for (const id of finding.evidence_ids) if (id) map.set(id, "extra");
  for (const field of review.fields) {
    const own: EvidenceStatus = field.status === "decided" || field.status === "derived" || field.status === "absent" ? "confirmed"
      : field.status === "conflict" || field.status === "changed" ? "deviation" : field.status === "deferred" ? "skipped" : "open";
    for (const entry of field.evidence) if (entry.evidence_id) map.set(entry.evidence_id, entry.excluded ? "excluded" : own);
  }
  statusCache.set(review, map);
  return map;
}

/** Stand eines Nachweises aus der Feldprüfung; ohne Feldprüfung oder ohne Zuordnung bleibt er offen. */
export function fieldEvidenceStatus(evidenceId: string, review: FieldReviewDto | null | undefined): EvidenceStatus {
  return review ? fieldStatusMap(review).get(evidenceId) ?? "open" : "open";
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
