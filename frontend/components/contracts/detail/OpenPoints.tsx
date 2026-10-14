"use client";

import { revealBox } from "@/lib/box-collapse";
import Link from "next/link";
import EmptyState from "@/components/ui/EmptyState";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import type { DetailWarning } from "@/lib/contract-detail-types";
import { contractHref, warningTarget, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import type { Gap } from "./ContractGaps";

/** Offene Aufgabe aus der Vertragsakte (Auszug der benötigten Felder). */
export interface OpenTask {
  work_item_id: string;
  item_type: string;
  severity: string;
  title_de: string;
  why_de?: string | null;
  requires_review: boolean;
}

export interface OpenPoint {
  key: string;
  tone: SignalTone;
  word: string;
  title: string;
  why: string;
  action: string;
  /** Ziel in der Vertragsakte (Direkt zur Stelle) oder Anker auf dieser Seite. */
  target: FixTarget | null;
  anchor?: string;
  rank: number;
}

// Freigegebene Zuordnung (Plan Vertragsseite, Schritt 5): Reihenfolge Kritisch → Prüfen (Priorität hoch)
// → KI-Prüfung → Prüfen → Hinweis.
const RANK = { critical: 0, high: 1, ai: 2, warning: 3, info: 4 } as const;

function bySeverity(severity: string): { tone: SignalTone; word: string; rank: number; priority: boolean } {
  if (severity === "critical") return { tone: "critical", word: "Kritisch", rank: RANK.critical, priority: false };
  if (severity === "high") return { tone: "warning", word: "Prüfen", rank: RANK.high, priority: true };
  if (severity === "medium") return { tone: "warning", word: "Prüfen", rank: RANK.warning, priority: false };
  return { tone: "info", word: "Hinweis", rank: RANK.info, priority: false };
}

export function buildOpenPoints({ gaps, tasks, warnings, scopeToCheck, scopeTotal, slaToCheck = 0, reviewOpen = 0, cancelByUnknown = false }: {
  gaps: Gap[];
  tasks: OpenTask[];
  warnings: DetailWarning[];
  /** Leistungen mit noch nicht bestätigtem KI-Wert und Leistungen mit Wert überhaupt (wie die Faktprüfung). */
  scopeToCheck: number;
  scopeTotal: number;
  /** SLA-Werte aus dem Dokument, die noch niemand bestätigt hat. */
  slaToCheck?: number;
  /** Offene Angaben der Faktprüfung (Zahl im Punkt „KI-Werte bestätigen“). */
  reviewOpen?: number;
  /** Kündbar-bis lässt sich nicht berechnen (Kopf zeigt „Nicht berechenbar“). */
  cancelByUnknown?: boolean;
}): OpenPoint[] {
  const points: OpenPoint[] = [];
  // Gleiche Aussage wie im Kopf; entfällt, wenn eine fristrelevante Lücke schon genannt ist.
  if (cancelByUnknown && !gaps.some((gap) => gap.blocksDeadline)) {
    points.push({ key: "cancel-by", tone: "critical", word: "Kritisch", title: "Kündigungstermin nicht berechenbar", why: "Ohne Kündigungsfrist wird der Kündigungstermin nicht berechnet und nicht überwacht.", action: "Kündigungsfrist erfassen", target: { tab: "register", field: "notice_period_value" }, rank: RANK.critical });
  }
  for (const gap of gaps) {
    if (gap.key === "review") {
      points.push({ key: `gap-${gap.key}`, tone: "ai", word: "KI-Prüfung", title: "KI-Werte bestätigen", why: reviewOpen > 0 ? `${reviewOpen} ${reviewOpen === 1 ? "Angabe aus dem Dokument ist" : "Angaben aus dem Dokument sind"} noch nicht bestätigt.` : "Werte aus dem Dokument sind noch nicht bestätigt.", action: "Werte prüfen", target: gap.target, rank: RANK.ai });
      continue;
    }
    if (gap.blocksDeadline) {
      points.push({ key: `gap-${gap.key}`, tone: "critical", word: "Kritisch", title: `${gap.label} fehlt`, why: "Ohne diese Angabe wird die Kündigungsfrist nicht berechnet und nicht überwacht.", action: gap.command, target: gap.target, rank: RANK.critical });
      continue;
    }
    points.push({ key: `gap-${gap.key}`, tone: "warning", word: "Prüfen", title: gap.label, why: gap.reason, action: gap.command, target: gap.target, rank: RANK.warning });
  }
  for (const task of tasks) {
    const target = workItemTarget(task.item_type, task.requires_review);
    if (task.requires_review) {
      points.push({ key: `task-${task.work_item_id}`, tone: "ai", word: "KI-Prüfung", title: task.title_de, why: task.why_de ?? "Wert aus dem Dokument bitte prüfen.", action: "Prüfen", target, rank: RANK.ai });
      continue;
    }
    const level = bySeverity(task.severity);
    points.push({ key: `task-${task.work_item_id}`, tone: level.tone, word: level.word, title: task.title_de, why: [task.why_de, level.priority ? "Priorität hoch" : null].filter(Boolean).join(" · ") || "Offene Aufgabe", action: "Erledigen", target, rank: level.rank });
  }
  warnings.forEach((warning, index) => {
    // Eine Warnung, die eine Prüfung verlangt, folgt ihrem Schweregrad (z. B. Berechnungskonflikt → Prüfen).
    const level = bySeverity(warning.severity);
    points.push({ key: `warning-${warning.warning_type}-${index}`, tone: level.tone, word: level.word, title: warning.title_de, why: [warning.requires_review ? "Bitte prüfen" : null, level.priority ? "Priorität hoch" : null].filter(Boolean).join(" · ") || "Hinweis aus der Berechnung", action: "Ansehen", target: warningTarget(warning.warning_type, false) ?? { tab: "deadlines" }, rank: level.rank });
  });
  if (scopeToCheck > 0) {
    points.push({ key: "scope", tone: "warning", word: "Prüfen", title: "Leistungsumfang ungeklärt", why: `${scopeToCheck} von ${scopeTotal} Leistungen aus dem Dokument ${scopeToCheck === 1 ? "ist" : "sind"} noch nicht bestätigt.`, action: "Leistungen", target: null, anchor: "leistungsumfang-heading", rank: RANK.warning });
  }
  if (slaToCheck > 0) {
    points.push({ key: "sla-check", tone: "warning", word: "Prüfen", title: "SLA-Werte bestätigen", why: `${slaToCheck} ${slaToCheck === 1 ? "SLA-Wert aus dem Dokument ist" : "SLA-Werte aus dem Dokument sind"} noch nicht bestätigt.`, action: "SLA", target: null, anchor: "sla-heading", rank: RANK.warning });
  }
  return points.map((point, index) => ({ point, index })).sort((a, b) => a.point.rank - b.point.rank || a.index - b.index).map(({ point }) => point);
}

/** „Offene Punkte“: alles, was an diesem Vertrag zu tun ist, nach Dringlichkeit. Ein Primärknopf. */
export default function OpenPoints({ contractId, points, searchHref, onOpen }: {
  contractId: string;
  /** null = wird noch geladen. */
  points: OpenPoint[] | null;
  /** „Fehlende Angaben im Dokument suchen“ (erneute Erfassung), wenn möglich. */
  searchHref?: string | null;
  onOpen: (target: FixTarget) => void;
}) {
  const primary = (points ?? []).findIndex((point) => point.tone === "critical");
  return <section className="cw-section open-points" aria-labelledby="open-points-heading">
    <div className="cw-section-head">
      <div>
        <h2 id="open-points-heading">Offene Punkte{points?.length ? <span className="count-chip" aria-label={`${points.length} offen`}>{points.length}</span> : null}</h2>
        <p>Nach Dringlichkeit – jeder Punkt führt direkt zur Stelle, an der er erledigt wird. Auch über Strg+K erreichbar.</p>
      </div>
      {searchHref ? <Link className="btn btn-sm" href={searchHref}>Fehlende Angaben im Dokument suchen</Link> : null}
    </div>
    {points === null ? <p className="cw-muted" role="status">Wird geladen…</p> : points.length === 0 ? <EmptyState variant="calm" title="Keine offenen Punkte">Für diesen Vertrag ist gerade nichts zu tun.</EmptyState> : <ul className="open-points-list">
      {points.map((point, index) => {
        const className = `btn ${index === primary ? "btn-primary" : "btn-sm"}`;
        return <li key={point.key} className="open-point">
          <Signal tone={point.tone}>{point.word}</Signal>
          <div className="open-point-text"><strong>{point.title}</strong><span>{point.why}</span></div>
          {point.target
            ? <Link className={className} href={contractHref(contractId, point.target)} onClick={(event) => { event.preventDefault(); onOpen(point.target!); }}>{point.action}</Link>
            : point.anchor
              ? <a className={className} href={`#${point.anchor}`} onClick={(event) => { event.preventDefault(); const target = document.getElementById(point.anchor!); revealBox(target); target?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{point.action}</a>
              : null}
        </li>;
      })}
    </ul>}
  </section>;
}
