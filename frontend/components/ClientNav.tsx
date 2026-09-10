"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

type Icon = React.ReactNode;

const ic: Record<string, Icon> = {
  dashboard: <path d="M4 12h5l3-7 3 14 2-7h3" />,
  contracts: (
    <>
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v5h5" />
    </>
  ),
  workQueue: (
    <>
      <path d="M5 5h14v14H5z" />
      <path d="M8 9h8M8 13h5" />
    </>
  ),
  equipment: <path d="M8 3h8v5h5v8h-5v5H8v-5H3V8h5z" />,
  import: <path d="M12 3v18M3 12h18" />,
  review: (
    <>
      <circle cx="10" cy="10" r="6" />
      <path d="m15 15 5 5" />
    </>
  ),
  evidence: (
    <>
      <path d="M4 5h16v14H4z" />
      <path d="M8 9h8M8 13h5" />
    </>
  ),
  audit: (
    <>
      <path d="M5 20V4h14v16z" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </>
  ),
  archive: (
    <>
      <path d="M4 8h16v12H4z" />
      <path d="M7 8V4h10v4" />
      <path d="M9 12h6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4L5 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4L19 13a7 7 0 0 0 0-1z" />
    </>
  ),
};

const GROUPS: { label: string; items: { label: string; href: string; icon: keyof typeof ic }[] }[] =
  [
    {
      label: "Arbeitsbereich",
      items: [
        { label: "Übersicht", href: "/", icon: "dashboard" },
        { label: "Verträge", href: "/contracts", icon: "contracts" },
        { label: "Arbeitsliste", href: "/work-queue", icon: "workQueue" },
        { label: "Geräte", href: "/equipment", icon: "equipment" },
        { label: "Import", href: "/import", icon: "import" },
      ],
    },
    {
      label: "Kontrolle",
      items: [
        { label: "Prüfungen", href: "/review", icon: "review" },
        { label: "Nachweise", href: "/nachweise", icon: "evidence" },
        { label: "Audit", href: "/audit", icon: "audit" },
        { label: "Archiv", href: "/archiv", icon: "archive" },
      ],
    },
    {
      label: "System",
      items: [{ label: "Einstellungen", href: "/settings", icon: "settings" }],
    },
  ];

export const NAV_ITEMS: { label: string; href: string; icon: keyof typeof ic }[] = [
  { label: "Übersicht", href: "/", icon: "dashboard" },
  { label: "Verträge", href: "/contracts", icon: "contracts" },
  { label: "Arbeitsliste", href: "/work-queue", icon: "workQueue" },
  { label: "Geräte", href: "/equipment", icon: "equipment" },
  { label: "Import", href: "/import", icon: "import" },
  { label: "Einstellungen", href: "/settings", icon: "settings" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function titleForPath(pathname: string): string {
  if (pathname === "/") return "Übersicht";
  if (pathname.startsWith("/contracts/")) return "Vertrag 360";
  if (pathname === "/contracts") return "Verträge";
  if (pathname === "/work-queue") return "Arbeitsliste";
  if (pathname.startsWith("/equipment")) return pathname === "/equipment" ? "Geräte" : "Gerät";
  if (pathname === "/import") return "Import";
  if (pathname === "/review") return "Prüfungen";
  if (pathname === "/nachweise") return "Nachweise";
  if (pathname === "/audit") return "Audit";
  if (pathname === "/archiv") return "Archiv";
  if (pathname === "/settings") return "Einstellungen";
  return "Medflux";
}

function Sidebar() {
  const pathname = usePathname();
  const [healthy, setHealthy] = useState<boolean | null>(null);
  useEffect(() => {
    let mounted = true;
    apiGet<{ status: string }>("/health")
      .then((h) => mounted && setHealthy(h.status === "ok"))
      .catch(() => mounted && setHealthy(false));
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <aside className="sidebar">
      <Link href="/" className="brand">
        <span className="logo" aria-hidden="true" />
        <span>
          <strong>Medflux</strong>
          <small>Contract Intelligence</small>
        </span>
      </Link>
      <nav className="side-nav-root" aria-label="Hauptnavigation">
        {GROUPS.map((group) => (
          <div key={group.label}>
            <div className="nav-label">{group.label}</div>
            <nav className="side-nav" aria-label={group.label}>
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`nav-item${active ? " active" : ""}`}
                    aria-current={active ? "page" : undefined}
                  >
                    <span className="ico">
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        {ic[item.icon]}
                      </svg>
                    </span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}
      </nav>
      <div className="side-bottom">
        <div className="side-ai">
          <div className="side-ai-top">
            <b>Lokale KI</b>
            <div className="health">
              <span className="health-dot" aria-hidden="true" />
              {healthy === null ? "Prüfe…" : healthy ? "Gesund" : "Offline"}
            </div>
          </div>
          <p>
            Lokale Verarbeitung
            <br />
            Keine externen Modellaufrufe
          </p>
        </div>
        <div className="org-card">
          <span className="org-avatar" aria-hidden="true">
            K
          </span>
          <div>
            <b>Krankenhaus</b>
            <small>Arbeitsbereich {ORG_SLUG}</small>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const term = q.trim();
    router.push(term ? `/contracts?q=${encodeURIComponent(term)}` : "/contracts");
  }

  return (
    <header className="topbar">
      <div className="page-title">
        <h1>{titleForPath(pathname)}</h1>
      </div>
      <div className="top-actions">
        <form className="search" onSubmit={onSubmit} role="search">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10" cy="10" r="6" />
            <path d="m15 15 5 5" />
          </svg>
          <input
            type="search"
            aria-label="Globale Suche"
            placeholder="Vertragsnummer, Lieferant, Gerät …"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </form>
        <Link className="import-btn" href="/import">
          Vertrag importieren
        </Link>
      </div>
    </header>
  );
}

export default function ClientNav({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <Sidebar />
      <main className="main" id="main-content">
        <Topbar />
        {children}
      </main>
    </div>
  );
}