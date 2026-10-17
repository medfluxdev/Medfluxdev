"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { clearSelection, isHeadDoubleClick } from "@/lib/box-collapse";
import { cardIcon, tileClass } from "@/lib/card-icons";

const STORAGE_KEY = "medflux.collapsed-sections";
// Kästen, die anfangs zu sind (`defaultCollapsed`), merken sich das Aufklappen.
const EXPANDED_KEY = "medflux.expanded-sections";

/** Kennfarbe der Kachel: Art des Inhalts, nie Zustand. */
export type SectionTone = "cost" | "unit" | "department" | "accent" | "ai" | "neutral";
const TONE_CLASS: Record<SectionTone, string> = {
  cost: "section-tile--cost",
  unit: "section-tile--unit",
  department: "section-tile--dept",
  accent: "section-tile--tool",
  ai: "section-tile--ai",
  neutral: "",
};

function readIds(key: string): Set<string> {
  try {
    const raw = window.localStorage.getItem(key);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function writeIds(key: string, ids: Set<string>) {
  try {
    window.localStorage.setItem(key, JSON.stringify([...ids]));
  } catch {
    // Nur Komfort: ohne Speicher gilt der Ausgangszustand.
  }
}

const readCollapsed = () => readIds(STORAGE_KEY);
const writeCollapsed = (ids: Set<string>) => writeIds(STORAGE_KEY, ids);

interface Props {
  /** Stabile Kennung (Überschrift-ID `<id>-heading`, gemerkter Zustand). */
  id: string;
  title: string;
  description?: ReactNode;
  /** Kurzfassung (2–3 Werte, Fehlendes als Signal); ersetzt im eingeklappten Zustand die Beschreibung (ohne Kurzfassung bleibt die Beschreibung). */
  summary?: ReactNode;
  /** Kachel 40 × 40 zwischen Einklappen und Überschrift (Kennfarbe des Inhalts, dekorativ). */
  icon?: ReactNode;
  /** Kennfarbe der Kachel, z. B. `section-tile--type`. */
  iconClassName?: string;
  /** Kennfarbe als Art (statt `iconClassName`): cost, unit, department, accent, ai, neutral. */
  tone?: SectionTone;
  /** Anfangs eingeklappt (z. B. Nachschlage-Angaben); das Aufklappen merkt sich der Browser. */
  defaultCollapsed?: boolean;
  /** Aktionen oben rechts neben dem Einklappen (z. B. Bearbeiten / Speichern). */
  actions?: ReactNode;
  /** Von außen aufklappen (z. B. Sprung zu einem Feld in diesem Kasten). */
  forceOpen?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Kasten mit Einklappen-Knopf links (40 × 40), Überschrift, Beschreibung bzw. eingeklappt der
 * Kurzfassung und Aktionen rechts. Nur der Knopf klappt (plus Doppelklick auf freie Kopffläche),
 * damit Aktionen im Kopf bedienbar bleiben. Eingeklappte Kästen merkt sich der Browser (je Kennung).
 */
export default function CollapsibleSection({ id, title, description, summary, icon, iconClassName, tone, defaultCollapsed = false, actions, forceOpen = false, className, children }: Props) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  useEffect(() => { setCollapsed(defaultCollapsed ? !readIds(EXPANDED_KEY).has(id) : readCollapsed().has(id)); }, [defaultCollapsed, id]);

  const remember = useCallback((next: boolean) => {
    if (defaultCollapsed) {
      const ids = readIds(EXPANDED_KEY);
      if (next) ids.delete(id); else ids.add(id);
      writeIds(EXPANDED_KEY, ids);
      return;
    }
    const ids = readCollapsed();
    if (next) ids.add(id); else ids.delete(id);
    writeCollapsed(ids);
  }, [defaultCollapsed, id]);

  useEffect(() => {
    if (!forceOpen || !collapsed) return;
    setCollapsed(false);
    remember(false);
  }, [collapsed, forceOpen, remember]);

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    remember(next);
  }

  const bodyId = `${id}-body`;
  // Jede Karte hat eine Kachel: eigenes Symbol oder eines aus der Überschrift (lib/card-icons.ts).
  const auto = cardIcon(title);
  const tileClassName = tone ? TONE_CLASS[tone] : icon ? iconClassName ?? "" : tileClass(auto.tile);
  return <section className={["cw-section collapsible", collapsed ? "is-collapsed" : "", className ?? ""].filter(Boolean).join(" ")} aria-labelledby={`${id}-heading`} data-tone={tone}>
    <div className="cw-section-head collapsible-head has-icon" onDoubleClick={(event) => { if (!isHeadDoubleClick(event, event.currentTarget)) return; clearSelection(); toggle(); }}>
      <button type="button" className="collapsible-toggle" aria-expanded={!collapsed} aria-controls={bodyId} onClick={toggle} aria-label={`${title} ${collapsed ? "aufklappen" : "einklappen"}`} title={collapsed ? "Aufklappen" : "Einklappen"}>
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <span className={`collapsible-icon ${tileClassName}`.trim()} aria-hidden="true">{icon ?? <svg viewBox="0 0 24 24" focusable="false"><path d={auto.path} /></svg>}</span>
      <div className="collapsible-title">
        <h2 id={`${id}-heading`}>{title}</h2>
        {collapsed
          ? summary ? <div className="collapsible-summary">{summary}</div> : description ? <p>{description}</p> : null
          : description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="collapsible-corner">{actions}</div> : null}
    </div>
    <div id={bodyId} hidden={collapsed}>{children}</div>
  </section>;
}
