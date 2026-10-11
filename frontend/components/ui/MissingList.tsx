"use client";

import Link from "next/link";
import { Fragment } from "react";

export interface MissingItem {
  key: string;
  label: string;
  /** Ziel als Link (andere Seite oder anderer Reiter) … */
  href?: string;
  /** … oder als Aktion auf derselben Seite (z. B. Bearbeitung öffnen und Cursor setzen). */
  onSelect?: () => void;
}

interface Props {
  /** Einleitung, z. B. „Für „Gültig“ fehlen noch:“. */
  intro: string;
  items: MissingItem[];
  /** Verb für Screenreader, z. B. „erfassen“ → „Vertragsbeginn erfassen“. */
  verb?: string;
  className?: string;
}

// Fehlende Angaben als Liste von Sprungzielen: jedes Wort führt direkt dorthin, wo es erfasst wird.
// Ohne Ziel bleibt der Eintrag Text (z. B. ohne Bearbeitungsrecht und ohne Link).
export default function MissingList({ intro, items, verb = "erfassen", className }: Props) {
  if (!items.length) return null;
  return <p className={["missing-list", className].filter(Boolean).join(" ")}>
    {intro}{" "}
    {items.map((item, index) => <Fragment key={item.key}>
      {index > 0 ? ", " : null}
      {item.href
        ? <Link href={item.href} className="missing-link" aria-label={`${item.label} ${verb}`}>{item.label}</Link>
        : item.onSelect
          ? <button type="button" className="missing-link" aria-label={`${item.label} ${verb}`} onClick={item.onSelect}>{item.label}</button>
          : <span>{item.label}</span>}
    </Fragment>)}
    .
  </p>;
}
