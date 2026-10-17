import type { ReactNode } from "react";
import type { DeadlineDto } from "@/lib/domain-api/deadlines";

/** Typ eines Termins in Terminlisten (Zeitachse des Vertrags, Fristen-Seite, Mein Tag). */
export type TerminKind = "Aufgabe" | "Erinnerung" | "Frist" | "Wartung" | "Löschprüfung" | "KI-Prüfung";
export type TerminFilter = "aufgaben" | "erinnerungen" | "fristen";

const icon = (path: ReactNode) => <svg className="signal-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{path}</svg>;

// Kennfarbe je Typ (Identität, nicht Status) – immer mit Symbol und Wort. Farben: --color-termin-* in tokens.css.
export const TERMIN_KINDS: Record<TerminKind, { slug: string; icon: ReactNode; filter: TerminFilter }> = {
  Aufgabe: { slug: "aufgabe", filter: "aufgaben", icon: icon(<><rect x="4" y="4" width="16" height="16" rx="2" /><path d="m8 12 3 3 5-6" /></>) },
  Erinnerung: { slug: "erinnerung", filter: "erinnerungen", icon: icon(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></>) },
  Frist: { slug: "frist", filter: "fristen", icon: icon(<><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>) },
  Wartung: { slug: "wartung", filter: "fristen", icon: icon(<><path d="M14.7 6.3a4 4 0 0 0 5 5L13 18a2.1 2.1 0 0 1-3-3l6.7-6.7a4 4 0 0 0-2-2z" /><path d="m3 21 6-6" /></>) },
  Löschprüfung: { slug: "loeschung", filter: "fristen", icon: icon(<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />) },
  "KI-Prüfung": { slug: "ki", filter: "aufgaben", icon: icon(<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />) },
};
export const TERMIN_KIND_ORDER = Object.keys(TERMIN_KINDS) as TerminKind[];

/** Typ eines gespeicherten Termins: manuell = Aufgabe (bzw. Erinnerung); Systemtermine nach ihrem Schlüssel. */
export function deadlineKind(item: Pick<DeadlineDto, "source" | "system_key"> & { kind?: string }): TerminKind {
  // Eigene Erinnerung ohne Termin (Art „Erinnerung“) steht als eigene Zeile; alle anderen Erinnerungen hängen am Termin.
  if (item.source === "manual") return item.kind === "erinnerung" ? "Erinnerung" : "Aufgabe";
  if (item.system_key === "maintenance_due") return "Wartung";
  if (item.system_key === "retention_review") return "Löschprüfung";
  if (item.system_key === "set_ended") return "Aufgabe";
  return "Frist";
}

/** Typ-Chip: Symbol + Wort + Kennfarbe. */
export function KindChip({ kind }: { kind: TerminKind }) {
  return <span className={`signal signal--sm tl-kind-chip tl-kind-chip--${TERMIN_KINDS[kind].slug}`}>{TERMIN_KINDS[kind].icon}<span className="signal-label">{kind}</span></span>;
}
