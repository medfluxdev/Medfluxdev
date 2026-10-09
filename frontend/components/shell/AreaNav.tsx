"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export interface AreaNavItem {
  href: string;
  label: string;
}

export interface AreaNavGroup {
  title?: string;
  items: AreaNavItem[];
  /** Weitere Einträge, eingeklappt unter dieser Überschrift (z. B. Auswahllisten). */
  more?: { label: string; items: AreaNavItem[] };
}

function pathOf(href: string) {
  return href.split(/[?#]/)[0];
}

// Bereichsnavigation links neben dem Inhalt (Stammdaten, Verwaltung): gleiche Bedienung überall.
export function AreaNav({ label, groups }: { label: string; groups: AreaNavGroup[] }) {
  const pathname = usePathname() ?? "";

  function link(item: AreaNavItem) {
    const current = pathname === pathOf(item.href);
    return <li key={item.href}>
      <Link href={item.href} aria-current={current ? "page" : undefined} className={current ? "is-active" : undefined}>{item.label}</Link>
    </li>;
  }

  return <nav className="area-nav" aria-label={label}>
    {groups.filter((group) => group.items.length > 0 || group.more?.items.length).map((group, index) => <div key={group.title ?? index} className="area-nav-group">
      {group.title ? <h2>{group.title}</h2> : null}
      <ul>
        {group.items.map(link)}
        {group.more && group.more.items.length > 0 ? <li>
          <details open={group.more.items.some((item) => pathname === pathOf(item.href)) || undefined}>
            <summary>{group.more.label}</summary>
            <ul>{group.more.items.map(link)}</ul>
          </details>
        </li> : null}
      </ul>
    </div>)}
  </nav>;
}

// Rahmen eines Bereichs: Navigation links, Seite rechts (die Seite bringt ihren eigenen Kopf mit).
export function AreaLayout({ nav, children }: { nav: ReactNode; children: ReactNode }) {
  return <div className="page area-layout">
    {nav}
    <div className="area-content">{children}</div>
  </div>;
}
