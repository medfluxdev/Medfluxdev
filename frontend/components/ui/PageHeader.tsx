"use client";

import { useEffect } from "react";

interface Props {
  title: string;
  titleMain?: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  narrow?: boolean;
}

// Einheitliche Seitenkopfzeile: setzt einen aussagekräftigen document.title
// (Route-Announcement) und stellt das einzige H1 je Seite sicher.
export default function PageHeader({
  title,
  description,
  actions,
  narrow,
}: Props) {
  useEffect(() => {
    const base = "Medflux";
    document.title = title === base ? base : `${title} · ${base}`;
  }, [title]);

  return (
    <header className={`page-header${narrow ? " page-narrow" : ""}`}>
      <h1>{title}</h1>
      {description && <p className="page-sub">{description}</p>}
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}