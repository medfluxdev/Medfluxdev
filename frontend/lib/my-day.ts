import type { DeadlineDto } from "@/lib/domain-api/deadlines";
import type { RenewalListItem } from "@/lib/domain-api/registerGrid";
import { formatDate } from "@/lib/format";

export type TodoTone = "critical" | "warning" | "ai" | "neutral";
export type TodoIcon = "cal" | "scale" | "alert" | "hour" | "spark" | "eur";

export interface TodoRow {
  key: "overdue" | "decision" | "missingEnd" | "dueSoon" | "aiReview" | "missingCosts";
  tone: TodoTone;
  icon: TodoIcon;
  /** Statuswort (farbig), z. B. „Überfällig“. */
  word: string;
  /** Anzahl; bei genau einem Element steht stattdessen dessen Name im Titel. */
  count: number;
  title: string;
  context: string;
  action: string;
  href: string;
}

export interface TodoInput {
  /** Offene, überfällige Termine der Person. */
  overdue: DeadlineDto[];
  /** Kündigungsfristen (≤ 90 Tage) ohne erfasste Entscheidung. */
  openDecisions: RenewalListItem[];
  /** Anzahl Verträge ohne Vertragsende samt Ziel der Liste. */
  missingEnd: { count: number; href: string };
  /** Anzahl Verträge ohne Kosten samt Ziel der Liste. */
  missingCosts: { count: number; href: string };
  /** Verträge mit offener KI-Prüfung (nur für Prüfende). */
  reviewCount: number;
  /** Ziele der Sammelansichten. */
  hrefs: { overdue: string; decisions: string; review: string };
}

const label = (item: RenewalListItem) => [item.register_number, item.short_description].filter(Boolean).join(" · ") || "Vertrag";

/**
 * „Zu erledigen“: eine Liste für alles, was wirklich zu tun ist – das Dringendste zuerst.
 * Reihenfolge: überfällig → Entscheidung (≤ 30 Tage) → Frist unbekannt → bald fällig (31–90 Tage) → KI-Prüfung → Kosten fehlen.
 * Ein Element nennt seinen Namen, mehrere werden zu einer Zeile mit Anzahl; Zeilen ohne Treffer entfallen.
 */
export function buildTodo(input: TodoInput): TodoRow[] {
  const rows: TodoRow[] = [];

  const overdue = [...input.overdue].sort((a, b) => a.due_date.localeCompare(b.due_date));
  if (overdue.length === 1) {
    const [item] = overdue;
    rows.push({
      key: "overdue", tone: "critical", icon: "cal", word: "Überfällig", count: 1, title: item.title,
      context: `${item.contract_label ?? "Vertrag"} · fällig seit ${formatDate(item.due_date)}`, action: "Öffnen",
      href: `/contracts/${item.contract_id}?tab=deadlines`,
    });
  } else if (overdue.length > 1) {
    rows.push({
      key: "overdue", tone: "critical", icon: "cal", word: "Überfällig", count: overdue.length, title: `${overdue.length} Termine überfällig`,
      context: `ältester seit ${formatDate(overdue[0].due_date)}`, action: "Anzeigen", href: input.hrefs.overdue,
    });
  }

  const open = [...input.openDecisions].sort((a, b) => a.days_left - b.days_left);
  const urgent = open.filter((item) => item.days_left <= 30);
  const soon = open.filter((item) => item.days_left > 30);
  if (urgent.length === 1) {
    const [item] = urgent;
    rows.push({
      key: "decision", tone: "critical", icon: "scale", word: "Entscheidung", count: 1, title: `Kündigungsfrist ohne Entscheidung: ${label(item)}`,
      context: `${item.partner ?? "Vertragspartner offen"} · Kündigung bis ${formatDate(item.cancel_by)}`, action: "Entscheiden",
      href: `/contracts/${item.contract_id}?tab=deadlines`,
    });
  } else if (urgent.length > 1) {
    rows.push({
      key: "decision", tone: "critical", icon: "scale", word: "Entscheidung", count: urgent.length,
      title: `${urgent.length} Kündigungsfristen in 30 Tagen ohne Entscheidung`,
      context: `nächste: ${formatDate(urgent[0].cancel_by)}${urgent[0].partner ? ` · ${urgent[0].partner}` : ""}`, action: "Entscheiden", href: input.hrefs.decisions,
    });
  }

  if (input.missingEnd.count > 0) {
    rows.push({
      key: "missingEnd", tone: "critical", icon: "alert", word: "Frist unbekannt", count: input.missingEnd.count,
      title: input.missingEnd.count === 1 ? "1 Vertrag ohne Vertragsende" : `${input.missingEnd.count} Verträgen fehlt das Vertragsende`,
      context: "Kündigungsfrist kann nicht überwacht werden", action: "Ergänzen", href: input.missingEnd.href,
    });
  }

  if (soon.length === 1) {
    const [item] = soon;
    rows.push({
      key: "dueSoon", tone: "warning", icon: "hour", word: "Bald fällig", count: 1, title: `Kündigungsfrist in ${item.days_left} Tagen: ${label(item)}`,
      context: `${item.partner ?? "Vertragspartner offen"} · Kündigung bis ${formatDate(item.cancel_by)}`, action: "Anzeigen",
      href: `/contracts/${item.contract_id}?tab=deadlines`,
    });
  } else if (soon.length > 1) {
    rows.push({
      key: "dueSoon", tone: "warning", icon: "hour", word: "Bald fällig", count: soon.length, title: `${soon.length} Kündigungsfristen in 31–90 Tagen`,
      context: "Entscheidung rechtzeitig vorbereiten", action: "Anzeigen", href: input.hrefs.decisions,
    });
  }

  if (input.reviewCount > 0) {
    rows.push({
      key: "aiReview", tone: "ai", icon: "spark", word: "KI-Prüfung", count: input.reviewCount,
      title: input.reviewCount === 1 ? "1 Vertrag wartet auf Ihre Prüfung" : `${input.reviewCount} Verträge warten auf Ihre Prüfung`,
      context: "Vorschläge der KI bestätigen oder korrigieren", action: "Prüfen", href: input.hrefs.review,
    });
  }

  if (input.missingCosts.count > 0) {
    rows.push({
      key: "missingCosts", tone: "neutral", icon: "eur", word: "Kosten fehlen", count: input.missingCosts.count,
      title: input.missingCosts.count === 1 ? "1 Vertrag ohne Kosten" : `${input.missingCosts.count} Verträgen fehlen die Kosten`,
      context: "Jahreskosten sind dadurch unvollständig", action: "Ergänzen", href: input.missingCosts.href,
    });
  }
  return rows;
}

/** Kurzform für die Zahlenzeile: „2,4 Mio. €“, sonst ganze Euro („8.000 €“). */
export function compactEuro(amount: string | null | undefined): string {
  const value = Number(amount);
  if (amount == null || !Number.isFinite(value)) return "–";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio. €`;
  return `${Math.round(value).toLocaleString("de-DE")} €`;
}

export type MyDayTab = "todo" | "dates" | "notice" | "figures";
const TAB_KEY = "medflux.myday.tab";

/** Zuletzt gewählter Reiter – gilt nur für den heutigen Tag, am nächsten Tag greift wieder die Regel. */
export function readStoredTab(today: string): MyDayTab | null {
  try {
    const raw = JSON.parse(window.localStorage.getItem(TAB_KEY) ?? "null") as { day?: string; tab?: string } | null;
    return raw && raw.day === today && (raw.tab === "todo" || raw.tab === "dates" || raw.tab === "notice" || raw.tab === "figures") ? raw.tab : null;
  } catch {
    return null;
  }
}

export function storeTab(today: string, tab: MyDayTab) {
  try { window.localStorage.setItem(TAB_KEY, JSON.stringify({ day: today, tab })); } catch { /* nur Komfort */ }
}
