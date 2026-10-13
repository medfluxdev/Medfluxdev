/**
 * Symbol + Kennfarbe für jede Karte im Programm, abgeleitet aus der Überschrift.
 * Genutzt von `CollapsibleSection` (ohne eigenes `icon`) und von `lib/box-collapse.ts` (alle übrigen Kästen).
 * Kennfarben zeigen die Art der Angabe, nie einen Zustand (Ruhe & Signal); Signalfarben bleiben Warnungen vorbehalten.
 * Neue Regel: oben einfügen, spezifischere Begriffe vor allgemeinen.
 */

export type CardTile = "type" | "partner" | "dept" | "cost" | "device" | "accent";

export interface CardIcon {
  /** Ein einziger SVG-Pfad (24 × 24, nur Striche). */
  path: string;
  tile: CardTile;
}

const P = {
  euro: "M17 6.5A6.5 6.5 0 1 0 17 17.5M4 10.5h9M4 13.5h9",
  calendar: "M6 5h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM8 3v4M16 3v4M4 10h16",
  bell: "M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15L6 16M10 20a2 2 0 0 0 4 0",
  document: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  clock: "M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 7v5l3 2",
  building: "M4 21V5l8-2v18M12 7l8 3v11M3 21h18M8 9h1M8 13h1M8 17h1M15 13h2M15 17h2",
  people: "M9 11a3.5 3.5 0 1 1 0-7a3.5 3.5 0 1 1 0 7zM3 20a6 6 0 0 1 12 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14a5 5 0 0 1 3 6",
  device: "M5 4h14a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM9 20h6M12 16v4",
  checklist: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2",
  shield: "M12 3l8 3v6c0 4.5-3.4 8.2-8 9c-4.6-.8-8-4.5-8-9V6z",
  search: "M11 4a7 7 0 1 1 0 14a7 7 0 1 1 0-14zM20 20l-4-4",
  chat: "M4 5h16v11H9l-5 4z",
  chart: "M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6",
  gear: "M12 9a3 3 0 1 1 0 6a3 3 0 1 1 0-6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  flag: "M5 21V4h11l-1.5 4L16 12H5",
  archive: "M4 4h16v4H4zM5 8v12h14V8M10 12h4",
  box: "M4 5h16v14H4zM4 10h16",
} as const;

// Reihenfolge zählt: erster Treffer gewinnt.
const RULES: [RegExp, CardIcon][] = [
  [/kosten|finanz|abrechnung|preis|budget|zahlung|rechnung|leistungskatalog|€/, { path: P.euro, tile: "cost" }],
  [/erinnerung|benachrichtigung|postfach|wiedervorlage/, { path: P.bell, tile: "dept" }],
  [/frist|termin|kündig|laufzeit|verlängerung|entscheidung|mein tag|heute/, { path: P.calendar, tile: "type" }],
  [/verlauf|historie|protokoll|aktivität|korrektur|bemerkungen zum verlauf/, { path: P.clock, tile: "device" }],
  [/aufbewahrung|löschung|archiv|löschantr/, { path: P.archive, tile: "device" }],
  [/sicherheit|datenschutz|zugriff|vertraulich|anmeldung|passwort/, { path: P.shield, tile: "accent" }],
  [/\bki\b|ki-|künstliche|analyse|vorschläge|intelligence|assistent|erfassen|erfassung/, { path: P.spark, tile: "accent" }],
  [/dokument|anlage|nachweis|import|datei|quelle|deckblatt/, { path: P.document, tile: "partner" }],
  [/rahmenvertrag|verknüpf|einzelvertr/, { path: P.link, tile: "partner" }],
  [/partner|lieferant/, { path: P.building, tile: "partner" }],
  [/gerät/, { path: P.device, tile: "device" }],
  [/abteilung|krankenhaus|organisation|benutzer|rolle|person|zuständig|verantwort|vertretung|team|mitglied/, { path: P.people, tile: "dept" }],
  [/regel|prüf|review|checkliste|einrichtung|offene punkte|zu erledigen|aufgabe|arbeitsvorrat/, { path: P.checklist, tile: "type" }],
  [/suche|filter|treffer/, { path: P.search, tile: "accent" }],
  [/bemerkung|notiz|kommentar|frage|zusammenarbeit/, { path: P.chat, tile: "partner" }],
  [/portfolio|übersicht|auswertung|bericht|kennzahl|vergleich|bereich/, { path: P.chart, tile: "cost" }],
  [/status/, { path: P.flag, tile: "accent" }],
  [/nummer|einstellung|verwaltung|system|job|verarbeitung|modell|konfiguration|entwickl/, { path: P.gear, tile: "device" }],
];

const DEFAULT_ICON: CardIcon = { path: P.box, tile: "accent" };

export function cardIcon(title: string): CardIcon {
  const text = title.toLocaleLowerCase("de-DE");
  return RULES.find(([pattern]) => pattern.test(text))?.[1] ?? DEFAULT_ICON;
}

/** CSS-Klasse der Kachel (`app/styles/components.css`). */
export function tileClass(tile: CardTile): string {
  return `section-tile--${tile}`;
}

/** SVG als Markup (für Kästen, die `lib/box-collapse.ts` per DOM erweitert); nur feste Pfade, keine Nutzerdaten. */
export function cardIconMarkup(icon: CardIcon): string {
  return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${icon.path}"/></svg>`;
}
