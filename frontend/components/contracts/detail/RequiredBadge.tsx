"use client";

import type { ReactNode } from "react";

/**
 * Einheitliche Plakette für den Stand der Pflichtangaben im Kartenkopf (Organisationszuordnung, Vertrag & Partner):
 * Ring-Symbol + Text, 28 px. Grün = vollständig, Bernstein = es fehlt etwas oder es gibt Widersprüche.
 */
export default function RequiredBadge({ tone, children, title }: { tone: "done" | "warning"; children: ReactNode; title?: string }) {
  return <span className={`cw-complete${tone === "warning" ? " cw-complete--warning" : ""}`} title={title}>
    <svg className="cw-complete-ring" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle className="cw-complete-track" cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="9" />
      {tone === "done" ? <path d="m8.5 12.3 2.3 2.3 4.7-4.8" /> : <path d="M12 8v5M12 16v.5" />}
    </svg>
    {children}
  </span>;
}
