"use client";

import { useEffect } from "react";

interface Props {
  title: string;
  titleMain?: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  narrow?: boolean;
  /** "highlight": dunkler Markenbanner fuer Einstiegs- und Uebersichtsseiten. */
  variant?: "default" | "highlight";
  /** Kleine Zeile ueber dem Titel, nur im Banner. */
  eyebrow?: string;
  className?: string;
  /** Browser-Titel, falls er vom sichtbaren Titel abweichen soll. */
  documentTitle?: string;
}

// Einheitliche Seitenkopfzeile: setzt einen aussagekräftigen document.title
// (Route-Announcement) und stellt das einzige H1 je Seite sicher.
export default function PageHeader({
  title,
  description,
  actions,
  narrow,
  variant = "default",
  eyebrow,
  className,
  documentTitle,
}: Props) {
  const pageTitle = documentTitle ?? title;
  useEffect(() => {
    const base = "Medflux";
    document.title = pageTitle === base ? base : `${pageTitle} · ${base}`;
  }, [pageTitle]);

  if (variant === "highlight") {
    return (
      <header className={`page-hero${className ? ` ${className}` : ""}`}>
        <div>
          {eyebrow && <span className="page-hero-eyebrow">{eyebrow}</span>}
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="page-actions">{actions}</div>}
      </header>
    );
  }

  return (
    <header className={`page-header${narrow ? " page-narrow" : ""}${className ? ` ${className}` : ""}`}>
      <h1>{title}</h1>
      {description && <p className="page-sub">{description}</p>}
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}