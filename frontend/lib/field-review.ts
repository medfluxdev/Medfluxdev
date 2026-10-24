import type { SignalTone } from "@/components/ui/Signal";
import type {
  ContractDetailResponse, EvidenceRef, FieldCandidateDto, FieldEvidenceDto, FieldFindingDto, FieldReviewDto, FieldReviewFieldDto,
  FieldStageDto, FieldStatus, FieldTier, SourceState,
} from "@/lib/contract-detail-types";

/** Feldprüfung: ein Feld → Kandidatenwerte → Nachweise. Reine Hilfen für Karte, Übersicht und geführte Prüfung. */

export const TIER_ORDER: FieldTier[] = ["essential", "important", "optional"];
export const TIER_NAME: Record<FieldTier, string> = {
  essential: "Wesentliche Angaben",
  important: "Weitere wichtige Angaben",
  optional: "Optionale Angaben",
};
export const TIER_HINT: Record<FieldTier, string> = {
  essential: "Partner, Gegenstand, Laufzeit, Kündigung, Verlängerung, Preis, Währung, Steuer und Zahlungsrhythmus.",
  important: "Leistungen, Servicezeiten, Geräte und weitere Fristangaben.",
  optional: "Hinweise und Details – nur bei Bedarf.",
};
export const TIER_SHORT: Record<FieldTier, string> = { essential: "Wesentlich", important: "Weitere wichtige", optional: "Optional" };

/**
 * Zwei Prüfstufen für die geführte Prüfung: Pflicht und Optional. Die drei Wichtigkeitsstufen des Backends bleiben
 * unverändert; hier werden sie nur für die Anzeige zusammengefasst. „Wichtig“ geht standardmäßig in Optional auf.
 */
export const WICHTIG_ALS_PFLICHT = false;
export type ReviewLevel = "pflicht" | "optional";
export const LEVEL_ORDER: ReviewLevel[] = ["pflicht", "optional"];
export const LEVEL_NAME: Record<ReviewLevel, string> = { pflicht: "Pflicht", optional: "Optional" };

export function levelOf(tier: FieldTier, wichtigAlsPflicht: boolean = WICHTIG_ALS_PFLICHT): ReviewLevel {
  if (tier === "essential") return "pflicht";
  if (tier === "important") return wichtigAlsPflicht ? "pflicht" : "optional";
  return "optional";
}

export function levelFields(review: FieldReviewDto | null | undefined, level: ReviewLevel, wichtigAlsPflicht: boolean = WICHTIG_ALS_PFLICHT): FieldReviewFieldDto[] {
  return fieldsOf(review, undefined).filter((field) => levelOf(field.tier, wichtigAlsPflicht) === level);
}

/** Zähler einer Stufe aus den Stufen des Backends (nicht aus den Feldern, damit Berechnetes und Nachweise nicht mitzählen). */
export function levelCounts(review: FieldReviewDto | null | undefined, level: ReviewLevel, wichtigAlsPflicht: boolean = WICHTIG_ALS_PFLICHT): { total: number; open: number; decided: number } {
  const stages = (review?.stages ?? []).filter((stage) => levelOf(stage.tier, wichtigAlsPflicht) === level);
  return stages.reduce((sum, stage) => ({ total: sum.total + stage.total, open: sum.open + stage.open, decided: sum.decided + stage.decided }), { total: 0, open: 0, decided: 0 });
}

/** Die Stufe, in der die Prüfung weitergeht: Pflicht zuerst, dann Optional; null, wenn nichts mehr offen ist. */
export function nextOpenLevel(review: FieldReviewDto | null | undefined, wichtigAlsPflicht: boolean = WICHTIG_ALS_PFLICHT): ReviewLevel | null {
  return LEVEL_ORDER.find((level) => levelCounts(review, level, wichtigAlsPflicht).open > 0) ?? null;
}

/** Das nächste Feld mit offener Entscheidung in einer Stufe nach `afterKey` (reihum). */
export function nextDecisionInLevel(review: FieldReviewDto | null | undefined, level: ReviewLevel, afterKey: string | null): FieldReviewFieldDto | null {
  const all = levelFields(review, level);
  const start = afterKey ? all.findIndex((field) => field.fact_key === afterKey) : -1;
  for (let step = 1; step <= all.length; step += 1) {
    const candidate = all[(start + step + all.length) % all.length];
    if (candidate && candidate.decision_needed && candidate.fact_key !== afterKey) return candidate;
  }
  return null;
}

/** Ruhe & Signal: Farbe nur, wo eine Entscheidung wartet; Entschiedenes bleibt grün, Rest grau. */
export const STATUS_TONE: Record<FieldStatus, SignalTone> = {
  decided: "done",
  open: "ai",
  conflict: "warning",
  changed: "warning",
  deferred: "neutral",
  missing: "warning",
  absent: "neutral",
  derived: "neutral",
  waiting: "neutral",
};

export const SOURCE_TONE: Record<SourceState, SignalTone> = { verified: "done", located: "neutral", unresolved: "warning", unavailable: "warning" };

export function fieldsOf(review: FieldReviewDto | null | undefined, tier?: FieldTier): FieldReviewFieldDto[] {
  return (review?.fields ?? []).filter((field) => !tier || field.tier === tier);
}

/** Felder, die eine Entscheidung brauchen (optional: nur einer Stufe), in der Reihenfolge der Prüfung. */
export function decisionFields(review: FieldReviewDto | null | undefined, tier?: FieldTier): FieldReviewFieldDto[] {
  return fieldsOf(review, tier).filter((field) => field.decision_needed);
}

export function stageOf(review: FieldReviewDto | null | undefined, tier: FieldTier): FieldStageDto | undefined {
  return review?.stages.find((stage) => stage.tier === tier);
}

/** Die nächste Stufe mit offenen Entscheidungen (wesentlich zuerst). */
export function nextOpenTier(review: FieldReviewDto | null | undefined): FieldTier | null {
  return TIER_ORDER.find((tier) => (stageOf(review, tier)?.open ?? 0) > 0) ?? null;
}

/** Das nächste Feld mit offener Entscheidung nach `afterKey` (reihum innerhalb der Stufe), sonst null. */
export function nextDecision(review: FieldReviewDto | null | undefined, tier: FieldTier, afterKey: string | null): FieldReviewFieldDto | null {
  const all = fieldsOf(review, tier);
  const start = afterKey ? all.findIndex((field) => field.fact_key === afterKey) : -1;
  for (let step = 1; step <= all.length; step += 1) {
    const candidate = all[(start + step + all.length) % all.length];
    if (candidate && candidate.decision_needed && candidate.fact_key !== afterKey) return candidate;
  }
  return null;
}

export function fieldByKey(review: FieldReviewDto | null | undefined, key: string | null | undefined): FieldReviewFieldDto | undefined {
  return key ? review?.fields.find((field) => field.fact_key === key) : undefined;
}

/** Nachweise eines Kandidaten (in der Reihenfolge des Felds). */
export function candidateEvidence(field: FieldReviewFieldDto, candidate: FieldCandidateDto): FieldEvidenceDto[] {
  const ids = new Set(candidate.evidence_ids);
  return field.evidence.filter((entry) => ids.has(entry.evidence_id));
}

export function pluralize(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** Kurzaussage über den Stand: sagt nie „alles geprüft“, solange etwas offen ist. */
export function reviewHeadline(review: FieldReviewDto | null | undefined): { tone: SignalTone; text: string } | null {
  if (!review) return null;
  const essential = stageOf(review, "essential");
  if (!essential || essential.total === 0) return null;
  if (essential.open > 0) return { tone: "ai", text: `${pluralize(essential.open, "wesentliche Entscheidung", "wesentliche Entscheidungen")} offen` };
  if (review.decisions_open > 0) return { tone: "done", text: "Wesentliche Prüfung abgeschlossen" };
  return { tone: "done", text: "Wesentliche Prüfung abgeschlossen · alle Angaben entschieden" };
}

/** Das Feld, aus dem ein Wert stammt (Schlüssel der Prüf-Angabe); Nachweis-Angaben gehören zu Weiteren Informationen. */
export function fieldForFact(review: FieldReviewDto | null | undefined, factKey: string | null | undefined): FieldReviewFieldDto | undefined {
  return fieldByKey(review, factKey);
}

export function findingsOpen(review: FieldReviewDto | null | undefined): FieldFindingDto[] {
  return (review?.findings ?? []).filter((finding) => finding.decision === null);
}

/** Nachweis aus dem Lesemodell des Vertrags (zum Anzeigen im Original). */
export function refOf(data: Pick<ContractDetailResponse, "evidence">, evidenceId: string | null | undefined): EvidenceRef | undefined {
  return evidenceId ? data.evidence.find((ref) => ref.evidence_id === evidenceId) : undefined;
}

/**
 * Gruppenbestätigung: andere offene Felder derselben Karte und Stufe, deren Wert eindeutig ist (ein Kandidat),
 * die Fundstelle genau belegt und die nicht umstritten sind. Nur diese Werte werden angezeigt und bestätigt.
 */
export function groupConfirmable(review: FieldReviewDto | null | undefined, current: FieldReviewFieldDto): FieldReviewFieldDto[] {
  return fieldsOf(review, current.tier).filter((field) => field.fact_key !== current.fact_key
    && field.card === current.card && field.kind === "extracted"
    && field.status === "open" && field.present && field.candidates.length === 1
    && field.source_state === "verified" && field.active_evidence_count >= 1);
}

export const STATUS_HINT: Partial<Record<FieldStatus, string>> = {
  open: "Wert aus dem Dokument – noch nicht von einer Person entschieden.",
  conflict: "Mehrere Werte kommen in Frage.",
  changed: "Seit der letzten Entscheidung hat sich etwas Wesentliches geändert.",
  deferred: "Zurückgestellt.",
  missing: "Im Dokument nicht gefunden.",
  absent: "Ausdrücklich als „nicht im Dokument“ festgehalten.",
};

const NUMBER_DE = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * Anzeige eines Werts für Listen und Entscheidungen: Zahlen deutsch formatiert (Beträge mit der Währung der Akte, nur wenn
 * sie bekannt ist – nie ein erfundenes „€“), Prozent mit Zeichen; alles andere unverändert.
 */
export function shownValue(review: FieldReviewDto | null | undefined, factKey: string, text: string | null | undefined): string | null {
  if (text == null || text === "") return null;
  const trimmed = text.trim();
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) return text;
  const value = Number(trimmed);
  if (/vat_rate|tax_rate|percent/.test(factKey)) return `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(value)} %`;
  if (factKey.startsWith("costs.")) {
    const currency = review?.fields.find((field) => field.fact_key === "costs.currency")?.current;
    return `${NUMBER_DE.format(value)}${currency ? ` ${currency}` : ""}`;
  }
  return text;
}
