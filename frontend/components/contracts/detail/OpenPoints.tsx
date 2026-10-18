"use client";

import { revealBox } from "@/lib/box-collapse";
import Link from "next/link";
import EmptyState from "@/components/ui/EmptyState";
import Signal, { type SignalTone } from "@/components/ui/Signal";
import type { DetailWarning } from "@/lib/contract-detail-types";
import { REEXTRACTION_TARGET, SCOPE_TARGET, SLA_TARGET, asFixTarget, contractHref, warningTarget, workItemTarget, type FixTarget } from "@/lib/fix-targets";
import { formatDate } from "@/lib/format";
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

const STEP_ACTION_LABEL: Record<string, string> = { term: "Laufzeit eintragen", status: "Status setzen", finance: "Kosten erfassen", documents: "Dokument hochladen" };

// Freigegebene Zuordnung (Plan Vertragsseite, Schritt 5): Reihenfolge Kritisch → Prüfen (Priorität hoch)
// → KI-Prüfung → Prüfen → Hinweis.
const RANK = { critical: 0, high: 1, ai: 2, warning: 3, info: 4 } as const;

function bySeverity(severity: string): { tone: SignalTone; word: string; rank: number; priority: boolean } {
  if (severity === "critical") return { tone: "critical", word: "Kritisch", rank: RANK.critical, priority: false };
  if (severity === "high") return { tone: "warning", word: "Prüfen", rank: RANK.high, priority: true };
  if (severity === "medium") return { tone: "warning", word: "Prüfen", rank: RANK.warning, priority: false };
  return { tone: "info", word: "Hinweis", rank: RANK.info, priority: false };
}

/** Abschnitt „Nachweise prüfen“: öffnet im Reiter Dokumente den geführten Modus. */
export const EVIDENCE_REVIEW_SECTION = "nachweise-pruefen";
export const EVIDENCE_REVIEW_TARGET: FixTarget = { tab: "documents", subtab: "evidence", section: EVIDENCE_REVIEW_SECTION };
/** Abschnitt „Vorschläge prüfen“: geführter Modus für die Vorschläge der letzten Analyse. */
export const PROPOSAL_REVIEW_SECTION = "vorschlaege-pruefen";

export function buildOpenPoints({ gaps, tasks, warnings, scopeToCheck, scopeTotal, slaToCheck = 0, reviewOpen = 0, evidenceOpen = 0, cancelByUnknown = false, decision = null, decisionStep = null, analysis = null }: {
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
  /** Nachweise ohne Ergebnis der Nachweisprüfung. */
  evidenceOpen?: number;
  /** Kündbar-bis lässt sich nicht berechnen (Kopf zeigt „Nicht berechenbar“). */
  cancelByUnknown?: boolean;
  /** Keine Entscheidung zum nächsten Termin erfasst (`pendingDecision`), sonst null. */
  decision?: { due: string; byCancel: boolean; urgency: string } | null;
  /** Erster offener Umsetzungsschritt der gültigen Entscheidung (Backend), mit Stichtag `today`. */
  decisionStep?: { label: string; title: string; detail: string; due: string | null; target: Record<string, string> | null; done: number; total: number; today: string } | null;
  /** Erneute Erfassung: fertige Analyse mit offenen Vorschlägen; neues Hauptdokument (Dateiname, "" ohne Namen) seit der letzten Analyse. */
  analysis?: { number: number | null; open: number; newDocument: string | null } | null;
}): OpenPoint[] {
  const points: OpenPoint[] = [];
  if (decisionStep) {
    const days = decisionStep.due ? Math.round((Date.parse(`${decisionStep.due}T00:00:00Z`) - Date.parse(`${decisionStep.today}T00:00:00Z`)) / 86_400_000) : null;
    const level = days != null && days < 0 ? { tone: "critical" as const, word: "Kritisch", rank: RANK.critical }
      : days != null && days <= 14 ? { tone: "warning" as const, word: "Prüfen", rank: RANK.high }
        : { tone: "info" as const, word: "Hinweis", rank: RANK.info };
    const target = asFixTarget(decisionStep.target);
    const when = days == null ? "" : days < 0 ? ` Überfällig seit ${formatDate(decisionStep.due)}.` : ` Bis ${formatDate(decisionStep.due)}.`;
    points.push({
      key: "decision-step", ...level, title: `${decisionStep.label}: ${decisionStep.title}`,
      why: `Schritt ${decisionStep.done + 1} von ${decisionStep.total}.${when} ${decisionStep.detail}`,
      action: target ? STEP_ACTION_LABEL[target.tab === "register" ? (target.section === "status" ? "status" : "term") : target.tab] ?? "Öffnen" : "Umsetzung ansehen",
      target: target ?? { tab: "deadlines", section: "decision" },
    });
  }
  if (decision) {
    const level = decision.urgency === "missed" ? { tone: "critical" as const, word: "Kritisch", rank: RANK.critical }
      : decision.urgency === "critical" ? { tone: "warning" as const, word: "Prüfen", rank: RANK.high }
        : { tone: "info" as const, word: "Hinweis", rank: RANK.info };
    points.push({
      key: "decision", ...level, title: "Entscheidung treffen",
      why: `${decision.urgency === "missed" ? "Kündigungsfrist verstrichen" : `Bis ${formatDate(decision.due)} entscheiden`}: verlängern, neu verhandeln, kündigen oder beobachten${decision.byCancel ? "" : " (Vertrag endet dann)"}.`,
      action: "Entscheiden", target: { tab: "deadlines", section: "decision" },
    });
  }
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
  if (analysis?.number != null && analysis.open > 0) {
    points.push({ key: "analysis", tone: "ai", word: "KI-Prüfung", title: `Analyse #${analysis.number} fertig`, why: `${analysis.open} ${analysis.open === 1 ? "Vorschlag prüfen" : "Vorschläge prüfen"} – die Vertragsdaten ändern sich erst, wenn Sie übernehmen.`, action: "Vorschläge prüfen", target: { tab: "documents", subtab: "document", section: PROPOSAL_REVIEW_SECTION }, rank: RANK.ai });
  }
  if (analysis?.newDocument != null) {
    points.push({ key: "analysis-new-document", tone: "info", word: "Hinweis", title: "Neues Dokument – Ergänzen starten?", why: `${analysis.newDocument ? `„${analysis.newDocument}“` : "Ein neues Vertragsdokument"} wurde nach der letzten Analyse hinterlegt. „Ergänzen“ sucht nur, was noch fehlt.`, action: "Ergänzen starten", target: REEXTRACTION_TARGET, rank: RANK.info });
  }
  if (evidenceOpen > 0) {
    points.push({ key: "evidence-review", tone: "ai", word: "KI-Prüfung", title: "Nachweise prüfen", why: `${evidenceOpen} ${evidenceOpen === 1 ? "Nachweis ist" : "Nachweise sind"} noch nicht mit dem Dokument abgeglichen.`, action: "Nachweise prüfen", target: EVIDENCE_REVIEW_TARGET, rank: RANK.ai });
  }
  if (scopeToCheck > 0) {
    points.push({ key: "scope", tone: "warning", word: "Prüfen", title: "Leistungsumfang ungeklärt", why: `${scopeToCheck} von ${scopeTotal} Leistungen aus dem Dokument ${scopeToCheck === 1 ? "ist" : "sind"} noch nicht bestätigt.`, action: "Leistungen", target: SCOPE_TARGET, rank: RANK.warning });
  }
  if (slaToCheck > 0) {
    points.push({ key: "sla-check", tone: "warning", word: "Prüfen", title: "SLA-Werte bestätigen", why: `${slaToCheck} ${slaToCheck === 1 ? "SLA-Wert aus dem Dokument ist" : "SLA-Werte aus dem Dokument sind"} noch nicht bestätigt.`, action: "SLA", target: SLA_TARGET, rank: RANK.warning });
  }
  return points.map((point, index) => ({ point, index })).sort((a, b) => a.point.rank - b.point.rank || a.index - b.index).map(({ point }) => point);
}

/** Liste mit Punkten (dekorativ). */
const OPEN_POINTS_ART = <><rect x="11" y="7" width="26" height="34" rx="3" /><circle cx="18" cy="17" r="1.6" /><circle cx="18" cy="24" r="1.6" /><circle cx="18" cy="31" r="1.6" /><path d="M23 17h8M23 24h8M23 31h8" /></>;

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
        <p>Nach Dringlichkeit sortiert.</p>
      </div>
      {searchHref ? <Link className="btn btn-sm" href={searchHref}>Fehlende Angaben im Dokument suchen</Link> : null}
    </div>
    {points === null ? <p className="cw-muted" role="status">Wird geladen…</p> : points.length === 0 ? <EmptyState variant="illustrated" illustration={OPEN_POINTS_ART} title="Keine offenen Punkte">Jeder Punkt führt direkt zur passenden Stelle im Vertrag.</EmptyState> : <ul className="open-points-list">
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
    <Link className="card-foot-link" href={contractHref(contractId, { tab: "deadlines" })} onClick={(event) => { event.preventDefault(); onOpen({ tab: "deadlines" }); }}>
      Fristen &amp; Aufgaben anzeigen<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m9 6 6 6-6 6" /></svg>
    </Link>
    <p className="card-foot-note">
      <svg className="signal-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.5M11 10h.5M15 10h.5M8 14h8" /></svg>
      Schnellzugriff <kbd>Strg</kbd> + <kbd>K</kbd>
    </p>
  </section>;
}
