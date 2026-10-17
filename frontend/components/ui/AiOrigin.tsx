"use client";

import { createContext, useContext } from "react";

/** Zustand eines Werts aus der KI-Analyse: von einer Person bestätigt, noch offen oder automatisch übernommen. */
export type AiOriginState = "confirmed" | "unreviewed" | "auto";

const WORD: Record<AiOriginState, string> = { confirmed: "Bestätigt", unreviewed: "Ungeprüft", auto: "Automatisch" };
const TITLE: Record<AiOriginState, string> = {
  confirmed: "Von der KI übernommen und von einer Person bestätigt",
  unreviewed: "Von der KI übernommen, Bestätigung steht noch aus",
  auto: "Automatisch übernommen (Prüfmodus der Organisation), von keiner Person bestätigt",
};

const SPARK = <path d="M9.5 7Q10.8 13.2 17 14.5Q10.8 15.8 9.5 22Q8.2 15.8 2 14.5Q8.2 13.2 9.5 7zM18 2.5Q18.6 5.4 21.5 6Q18.6 6.6 18 9.5Q17.4 6.6 14.5 6Q17.4 5.4 18 2.5z" fill="currentColor" stroke="none" />;
const STATE_ICON: Record<AiOriginState, JSX.Element> = {
  confirmed: <><circle cx="12" cy="12" r="9" fill="currentColor" stroke="none" /><path className="ai-origin-check" d="m8 12.5 2.7 2.7L16 9.8" /></>,
  unreviewed: <><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 2" /></>,
  auto: <><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 2" /></>,
};
const SOURCE_ICON = <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6M14 3l5 5v4M14 3v5h5M8.5 10h3" /><path d="M12.5 17h8.5M18 14l3 3-3 3" /></>;

const svg = (body: JSX.Element, className: string) => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;

/** Wohin eine Plakette führt: Prüf-Angabe(n) des Werts, Bezeichnung und – falls bekannt – die Fundstelle. */
export interface AiOriginTarget {
  factKeys: string[];
  subject?: string;
  openSource?: (() => void) | null;
}

/**
 * Von der Vertragsseite bereitgestellt: öffnet Dokumente → Prüfung bei der Angabe, aus der der Wert stammt
 * (ohne passende Angabe die Fundstelle, sonst die Prüfung). Ohne Kontext öffnet die Plakette nur die Fundstelle.
 */
export const AiReviewContext = createContext<((target: AiOriginTarget) => void) | null>(null);

interface Props {
  state: AiOriginState;
  /** Fundstelle im Dokument (Ersatz, wenn es keine passende Prüf-Angabe gibt). */
  onOpenSource?: (() => void) | null;
  /** Schlüssel der Prüf-Angabe(n), aus denen der Wert stammt, z. B. „dates.start_date“. */
  factKey?: string | null | (string | null | undefined)[];
  /** Wofür (für Screenreader), z. B. „Wartungspauschale“. */
  subject?: string;
  /** Zusatz im Tooltip, z. B. wer bestätigt hat oder die KI-Sicherheit. */
  detail?: string | null;
  /** Wie `Signal`: „sm“ (22 px, Standard in Zeilen und Tabellen) oder „md“ (28 px, neben großen Signalen). */
  size?: "sm" | "md";
}

/**
 * Herkunft eines Werts aus der KI: „KI · Bestätigt“ (KI-Farbe, gefüllter Haken) bzw. „KI · Ungeprüft“
 * (Bernstein, Uhr) – Farbe + Form + Wort. Ein Klick führt zur Prüfung des Werts.
 */
export default function AiOrigin({ state, onOpenSource, factKey, subject, detail, size = "sm" }: Props) {
  const openReview = useContext(AiReviewContext);
  const factKeys = (Array.isArray(factKey) ? factKey : [factKey]).filter((key): key is string => Boolean(key));
  const open = openReview ? () => openReview({ factKeys, subject, openSource: onOpenSource }) : onOpenSource ?? null;
  const title = [TITLE[state], detail].filter(Boolean).join(" · ");
  const body = <>
    {/* Ein Text für Screenreader; die sichtbaren Teile (Symbole, Punkt) sind Dekoration. */}
    <span className="sr-only">KI · {WORD[state]}</span>
    {svg(SPARK, "ai-origin-spark")}
    <span aria-hidden="true">KI</span>
    <span className="ai-origin-dot" aria-hidden="true" />
    {svg(STATE_ICON[state], "ai-origin-state")}
    <span aria-hidden="true">{WORD[state]}</span>
  </>;
  const className = `ai-origin ai-origin--${state}${size === "sm" ? " ai-origin--sm" : ""}`;
  // Nur ohne Vertragsseite und ohne Fundstelle (z. B. Bausteine-Seite) gibt es nichts zu öffnen.
  if (!open) return <span className={className} title={title}>
    {body}
    <span className="ai-origin-src ai-origin-src--none" aria-hidden="true">{svg(SOURCE_ICON, "ai-origin-src-icon")}</span>
  </span>;
  const action = openReview ? "Prüfung öffnen" : "Quelle öffnen";
  const hint = openReview ? ["Wert, Fundstelle und Verlauf", detail].filter(Boolean).join(" · ") : detail;
  return <button type="button" className={`${className} ai-origin--source`} onClick={open}
    aria-label={`KI · ${WORD[state]}${subject ? ` (${subject})` : ""} – ${action}`} aria-description={title}>
    {body}
    <span className="ai-origin-src">{svg(SOURCE_ICON, "ai-origin-src-icon")}</span>
    {/* Dunkle Sprechblase bei Hover/Fokus; Details darunter. */}
    <span className="ai-origin-tip" aria-hidden="true"><strong>{action}</strong>{hint ? <small>{hint}</small> : null}</span>
  </button>;
}
