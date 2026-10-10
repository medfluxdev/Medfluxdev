import type { ReactNode } from "react";
import type { AccountRole } from "@/lib/auth-types";
import { MASTER_DATA_SECTIONS } from "@/lib/master-data";

// Einzige Quelle fuer Navigation, Seitentitel, Brotkrumen und Befehlspalette (UX-Plan U3).

export type IconName =
  | "home" | "inbox" | "contracts" | "partners" | "equipment" | "deadlines" | "renewal" | "tasks"
  | "import" | "review" | "evidence" | "archive" | "analytics" | "history" | "admin" | "settings" | "search" | "developer" | "masterdata";

export const ICONS: Record<IconName, ReactNode> = {
  home: <><path d="M4 11 12 4l8 7" /><path d="M6 10v10h12V10" /></>,
  inbox: <><path d="M4 13h4l2 3h4l2-3h4" /><path d="M4 13 6 5h12l2 8v6H4z" /></>,
  contracts: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5" /><path d="M9 13h6M9 17h6" /></>,
  partners: <><circle cx="9" cy="8" r="3" /><path d="M3 20a6 6 0 0 1 12 0" /><path d="M16 4a3 3 0 0 1 0 6M18 14a6 6 0 0 1 3 6" /></>,
  equipment: <><rect x="4" y="5" width="16" height="11" rx="2" /><path d="M9 20h6M12 16v4" /></>,
  deadlines: <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>,
  renewal: <><path d="M20 12a8 8 0 1 1-2.3-5.7" /><path d="M20 4v5h-5" /></>,
  tasks: <><path d="M9 6h11M9 12h11M9 18h11" /><path d="m4 6 1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" /></>,
  import: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M4 21h16" /></>,
  review: <><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /><path d="m8 10 1.5 1.5L12 9" /></>,
  evidence: <><path d="M4 5h16v14H4z" /><path d="M8 9h8M8 13h5" /></>,
  archive: <><path d="M4 8h16v12H4z" /><path d="M3 4h18v4H3z" /><path d="M10 12h4" /></>,
  analytics: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /><path d="M12 8v4l3 2" /></>,
  admin: <><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  developer: <><path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 4l-4 16" /></>,
  masterdata: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>,
};

export function Icon({ name }: { name: IconName }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="shell-icon">{ICONS[name]}</svg>;
}

export interface NavItem {
  label: string;
  href: string;
  icon: IconName;
  roles?: AccountRole[];
  developerOnly?: boolean;
  keywords?: string;
  shortcut?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

const EDITORS: AccountRole[] = ["admin", "contract_manager"];
const REVIEWERS: AccountRole[] = ["admin", "contract_manager", "reviewer"];

// Restructure (Plan §5): Arbeit zuerst, Daten und Verwaltung nach Rechten. Prüfung, Archiv und Import sind
// Reiter bzw. Aktionen der Vertragsliste; Benachrichtigungen erreicht man über die Glocke.
export const NAV_GROUPS: NavGroup[] = [
  { label: "Arbeit", items: [
    { label: "Mein Tag", href: "/", icon: "home", keywords: "übersicht dashboard start", shortcut: "g s" },
    { label: "Verträge", href: "/register", icon: "contracts", keywords: "verträge register liste bestand zu prüfen prüfungen archiv", shortcut: "g v" },
    { label: "Fristen & Aufgaben", href: "/fristen", icon: "deadlines", keywords: "termine fristen wiedervorlage kündigung verlängerung entscheidung aufgaben to-dos", shortcut: "g t" },
    { label: "Geräte", href: "/equipment", icon: "equipment", keywords: "medizintechnik anlagen" },
    { label: "Analysen", href: "/analysen", icon: "analytics", keywords: "kosten berichte portfolio" },
    { label: "Nachweise", href: "/nachweise", icon: "evidence", keywords: "quellen belege" },
  ] },
  { label: "Daten & Verwaltung", items: [
    { label: "Stammdaten", href: "/stammdaten", icon: "masterdata", keywords: "vertragspartner lieferanten abteilungen kostenstellen krankenhäuser kataloge auswahllisten", shortcut: "g d" },
    { label: "Historie", href: "/audit", icon: "history", roles: EDITORS, keywords: "audit protokoll änderungen" },
    { label: "Verwaltung", href: "/admin", icon: "admin", roles: ["admin"], keywords: "admin benutzer rollen einstellungen nummernkreis löschung" },
    { label: "Entwicklung", href: "/developer", icon: "developer", developerOnly: true, keywords: "developer diagnose" },
  ] },
];

// Seiten, die nicht in der Seitenleiste stehen (fuer Titel, Brotkrumen und Suche).
export const EXTRA_PAGES: NavItem[] = [
  { label: "Verträge – Zu prüfen", href: "/register?ansicht=review", icon: "review", roles: REVIEWERS, keywords: "prüfungen ki werte bestätigen" },
  { label: "Verträge – Archiv", href: "/register?ansicht=archive", icon: "archive", roles: EDITORS, keywords: "archiviert wiederherstellen" },
  { label: "Vertrag importieren", href: "/import", icon: "import", roles: EDITORS, keywords: "import hochladen pdf docx dokument" },
  { label: "Benachrichtigungen", href: "/postfach", icon: "inbox", keywords: "postfach erinnerungen eskalationen glocke" },
  { label: "Inhaltssuche", href: "/suche", icon: "search", keywords: "volltext dokumente klausel" },
  { label: "Vertrag anlegen", href: "/contracts/new", icon: "contracts", roles: EDITORS },
  { label: "Einstellungen", href: "/settings", icon: "settings", roles: ["admin"] },
  { label: "Mein Profil", href: "/profile", icon: "settings" },
  { label: "Benutzer", href: "/settings/users", icon: "admin", roles: ["admin"] },
  { label: "Sicherheit & Datenschutz", href: "/sicherheit", icon: "admin", keywords: "datenschutz dsgvo it sicherheit verschlüsselung ki lokal" },
  { label: "Nummernkreis", href: "/settings/nummernkreis", icon: "admin", roles: ["admin"], keywords: "vertragsnummer nummern" },
  { label: "Rollen & Rechte", href: "/settings/roles", icon: "admin" },
  { label: "Vertragslöschung", href: "/admin/deletion", icon: "admin", roles: ["admin"] },
  { label: "UI-Komponenten", href: "/developer/components", icon: "developer", developerOnly: true },
  { label: "Organisationen", href: "/system/organizations", icon: "developer", developerOnly: true },
  ...MASTER_DATA_SECTIONS.map((section): NavItem => ({
    label: section.label,
    href: section.href,
    icon: section.kind === "partner" ? "partners" : "masterdata",
    keywords: `stammdaten ${section.group.toLowerCase()} ${section.description.toLowerCase()}`,
  })),
];

export function visibleGroups(role: AccountRole | null | undefined, isDeveloper: boolean): NavGroup[] {
  return NAV_GROUPS
    .map((group) => ({ ...group, items: group.items.filter((item) => allowed(item, role, isDeveloper)) }))
    .filter((group) => group.items.length > 0);
}

export function allowed(item: NavItem, role: AccountRole | null | undefined, isDeveloper: boolean) {
  if (item.developerOnly) return isDeveloper;
  if (!item.roles) return true;
  return isDeveloper || (role ? item.roles.includes(role) : false);
}

// Seiten, die zu einem Menüpunkt gehören, ohne unter dessen Pfad zu liegen (Vertragsakte, Import, alte Adressen).
const ACTIVE_ALIASES: Record<string, string[]> = {
  "/register": ["/contracts", "/import", "/review", "/archiv"],
  "/fristen": ["/termine", "/verlaengerungen", "/work-queue", "/postfach"],
};

export function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  const prefixes = [href, ...(ACTIVE_ALIASES[href] ?? [])];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export interface PageInfo {
  title: string;
  group?: NavGroup;
  item?: NavItem;
}

export function pageFor(pathname: string): PageInfo {
  if (pathname.startsWith("/contracts/") && pathname !== "/contracts/new") {
    const group = NAV_GROUPS.find((entry) => entry.items.some((item) => item.href === "/register"));
    return { title: "Vertrag", group, item: group?.items.find((item) => item.href === "/register") };
  }
  const all = [...NAV_GROUPS.flatMap((group) => group.items.map((item) => ({ group, item }))), ...EXTRA_PAGES.map((item) => ({ group: undefined, item }))];
  const exact = all.find(({ item }) => item.href === pathname);
  const match = exact ?? all.filter(({ item }) => item.href !== "/" && pathname.startsWith(`${item.href}/`)).sort((a, b) => b.item.href.length - a.item.href.length)[0];
  return match ? { title: match.item.label, group: match.group, item: match.item } : { title: "MedFlux" };
}
