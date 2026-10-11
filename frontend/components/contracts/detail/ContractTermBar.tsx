"use client";

import Signal from "@/components/ui/Signal";
import { formatDate } from "@/lib/format";

const DAY = 24 * 60 * 60 * 1000;

function parse(iso: string): number {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function localToday(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

/** „noch 2 Jahre, 5 Monate“ – ganze Kalendermonate zwischen zwei Tagen. */
export function remaining(fromIso: string, toIso: string): string {
  const [fy, fm, fd] = fromIso.slice(0, 10).split("-").map(Number);
  const [ty, tm, td] = toIso.slice(0, 10).split("-").map(Number);
  let months = (ty - fy) * 12 + (tm - fm) - (td < fd ? 1 : 0);
  if (months <= 0) {
    const days = Math.max(0, Math.round((parse(toIso) - parse(fromIso)) / DAY));
    return days === 1 ? "noch 1 Tag" : `noch ${days} Tage`;
  }
  const years = Math.floor(months / 12);
  months %= 12;
  const parts = [years ? `${years} ${years === 1 ? "Jahr" : "Jahre"}` : null, months ? `${months} ${months === 1 ? "Monat" : "Monate"}` : null].filter(Boolean);
  return `noch ${parts.join(", ")}`;
}

interface Props {
  start: string | null;
  end: string | null;
  cancelBy: string | null;
  /** Feste Laufzeit: endet ohne Kündigung (kein Kündigungstermin nötig). */
  fixedTerm?: boolean;
  /** Unbefristet: kein Ende, keine Leiste. */
  openEnded?: boolean;
  /** Nur für Tests; sonst der heutige Tag (lokal). */
  today?: string;
}

/**
 * Laufzeit als Leiste: Beginn → Ende, „Heute“ und der Kündigungstermin.
 * Nur mit bekanntem Beginn und Ende; alles steht zusätzlich als Text (aria-label und Legende).
 */
export default function ContractTermBar({ start, end, cancelBy, fixedTerm = false, openEnded = false, today = localToday() }: Props) {
  if (openEnded && start) return <p className="term-bar-open">Unbefristet seit {formatDate(start)} – kein festes Ende.</p>;
  if (!start || !end) return null;
  const from = parse(start);
  const to = parse(end);
  if (to <= from) return null;
  const now = parse(today);
  const pct = (value: number) => Math.min(100, Math.max(0, ((value - from) / (to - from)) * 100));
  const elapsed = pct(now);
  const ended = now > to;
  const left = ended ? "Laufzeit abgelaufen" : now < from ? "beginnt noch" : remaining(today, end);

  let cancel: { pct: number; tone: "neutral" | "warning" | "critical"; text: string } | null = null;
  if (cancelBy) {
    const days = Math.round((parse(cancelBy) - now) / DAY);
    cancel = {
      pct: pct(parse(cancelBy)),
      tone: days < 0 ? "critical" : days <= 30 ? "warning" : "neutral",
      text: days < 0 ? `Kündbar bis ${formatDate(cancelBy)} – verstrichen` : `Kündbar bis ${formatDate(cancelBy)}`,
    };
  }

  const description = [
    `Laufzeit vom ${formatDate(start)} bis ${formatDate(end)}`,
    ended ? "abgelaufen" : `heute ${Math.round(elapsed)} Prozent vergangen, ${left}`,
    cancel ? cancel.text : fixedTerm ? "feste Laufzeit, endet ohne Kündigung" : "Kündigungsfrist fehlt",
  ].join(", ");

  return <div className="term-bar" role="img" aria-label={description}>
    <div className="term-bar-track" aria-hidden="true">
      <div className="term-bar-fill" style={{ width: `${elapsed}%` }} />
      {!ended ? <div className="term-bar-today" style={{ left: `${elapsed}%` }} title="Heute" /> : null}
      {cancel ? <div className={`term-bar-cancel term-bar-cancel--${cancel.tone}`} style={{ left: `${cancel.pct}%` }} title={cancel.text} /> : null}
    </div>
    <div className="term-bar-legend" aria-hidden="true">
      <span>{formatDate(start)}</span>
      <span><b>Heute</b> · {left}</span>
      {cancel
        ? (cancel.tone === "neutral" ? <span className="term-bar-cancel-label">{cancel.text}</span> : <Signal tone={cancel.tone} size="sm">{cancel.text}</Signal>)
        : fixedTerm ? <span className="term-bar-cancel-label">Feste Laufzeit – endet ohne Kündigung</span> : <Signal tone="critical" size="sm">Kündigungsfrist fehlt</Signal>}
      <span>{formatDate(end)}</span>
    </div>
  </div>;
}
