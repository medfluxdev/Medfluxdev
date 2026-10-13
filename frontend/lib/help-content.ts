/**
 * Inhalte der Hilfe-Seite (/hilfe). Neues Thema: einen Eintrag in `HELP_SECTIONS` ergänzen –
 * Suche, Inhaltsverzeichnis und Sprungmarken (`/hilfe#<id>`) entstehen daraus.
 * Nur Aussagen, die das Programm wirklich einlöst; Links mit `href` führen direkt zur Stelle.
 */

export interface HelpEntry {
  /** Stabile Sprungmarke, z. B. `/hilfe#vertrag-importieren`. */
  id: string;
  question: string;
  /** Absätze. */
  answer: string[];
  /** Optionale Schritte als nummerierte Liste. */
  steps?: string[];
  links?: { label: string; href: string }[];
  /** Zusätzliche Suchbegriffe (Synonyme). */
  keywords?: string;
}

export interface HelpSection {
  id: string;
  title: string;
  description: string;
  entries: HelpEntry[];
}

export const HELP_SECTIONS: HelpSection[] = [
  {
    id: "erste-schritte",
    title: "Erste Schritte",
    description: "Wo Sie anfangen und wie ein Vertrag ins System kommt.",
    entries: [
      {
        id: "mein-tag",
        question: "Was zeigt „Mein Tag“?",
        answer: [
          "Die Startseite sammelt, was heute Aufmerksamkeit braucht: anstehende Fristen, offene Aufgaben und Verträge mit fehlenden Angaben. Jeder Punkt führt direkt zur Stelle, an der er erledigt wird.",
        ],
        links: [{ label: "Mein Tag öffnen", href: "/" }],
        keywords: "start dashboard übersicht",
      },
      {
        id: "vertrag-importieren",
        question: "Wie importiere ich einen Vertrag?",
        answer: [
          "Der Import führt in fünf Schritten durch: Ziel, Dateien, Erfassung, Prüfen & starten, Ergebnis. PDF- und Word-Dateien (DOCX) werden angenommen.",
          "Bei der Erfassung wählen Sie, ob die lokale KI die Angaben ausliest und eine Person sie prüft, ob die KI direkt übernimmt (nur wenn Ihre Organisation das erlaubt) oder ob Sie alles von Hand erfassen.",
        ],
        links: [{ label: "Vertrag importieren", href: "/import" }],
        keywords: "hochladen upload pdf docx dokument assistent",
      },
      {
        id: "vertrag-anlegen",
        question: "Kann ich einen Vertrag ohne Dokument anlegen?",
        answer: ["Ja. Unter „Vertrag anlegen“ erfassen Sie die Angaben von Hand. Das Dokument kann später unter Dokumente ergänzt werden."],
        links: [{ label: "Vertrag anlegen", href: "/contracts/new" }],
        keywords: "manuell neu",
      },
    ],
  },
  {
    id: "vertraege",
    title: "Verträge bearbeiten",
    description: "Vertragsliste, Vertragsakte und Zuständigkeit.",
    entries: [
      {
        id: "vertragsliste",
        question: "Wie finde ich Verträge in der Liste?",
        answer: [
          "Die Vertragsliste hat die Reiter Bestand, Zu prüfen und Archiv. Suche, Schnellfilter (Status, Vertragspartner, Abteilung) und „Weitere Filter“ wirken zusammen.",
          "Der Zustand der Liste steht in der Adresse – Sie können eine gefilterte Liste als Lesezeichen speichern oder weitergeben. Mit „Excel exportieren“ speichern Sie die aktuelle Auswahl als Tabelle.",
        ],
        links: [{ label: "Vertragsliste", href: "/register" }],
        keywords: "suchen filtern export excel register bestand",
      },
      {
        id: "inhaltssuche",
        question: "Wie finde ich Verträge mit einer bestimmten Regelung?",
        answer: [
          "Die Inhaltssuche durchsucht den Text aller Vertragsdokumente, zum Beispiel nach „Preisgleitklausel“ oder „Rufbereitschaft“. Jeder Treffer nennt Vertrag, Dokument und Seite.",
          "Aus Strg + K erreichen Sie sie mit „In allen Vertragsdokumenten suchen“.",
        ],
        links: [{ label: "Inhaltssuche", href: "/suche" }],
        keywords: "volltext klausel text dokument durchsuchen",
      },
      {
        id: "bearbeiten",
        question: "Wie bearbeite ich Vertragsdaten?",
        answer: [
          "Jeder Kasten in den Vertragsdaten hat einen eigenen Knopf „Bearbeiten“. Mehrere Kästen können gleichzeitig offen sein; „Speichern“ speichert alle offenen Änderungen.",
          "Schneller geht es mit der Tastatur: E öffnet das Bearbeiten im aktuellen Kasten, Strg + S speichert. Verlassen Sie die Seite mit ungespeicherten Änderungen, fragt MedFlux nach.",
        ],
        keywords: "ändern editieren speichern tastatur",
      },
      {
        id: "organisationszuordnung",
        question: "Was gehört in die Organisationszuordnung?",
        answer: [
          "Sie legt fest, wem der Vertrag gehört und wer ihn nutzt: Vertragstyp, Krankenhaus, verantwortliche und nutzende Abteilungen, Kostenstelle, Gerätearten und verantwortliche Personen.",
          "Im Kopf des Kastens sehen Sie, ob die Pflichtangaben vollständig sind (Vertragstyp, Krankenhaus, verantwortliche Abteilung, Kostenstelle, Hauptverantwortlich). Fehlt etwas, öffnet ein Klick auf den Hinweis das Bearbeiten.",
          "Das Krankenhaus lässt sich erst ändern, wenn keine Abteilungen mehr zugeordnet sind.",
        ],
        keywords: "zuständigkeit abteilung kostenstelle verantwortlich geräteart pflichtangaben",
      },
      {
        id: "status",
        question: "Welche Bearbeitungsstatus gibt es?",
        answer: [
          "Ein Vertrag beginnt „In Arbeit“. Sind alle nötigen Angaben da, setzen Sie ihn auf „Gültig“; später auf „Gekündigt“ oder „Beendet“. „Storniert“ markiert einen Vertrag als ungültig, die Daten bleiben erhalten.",
          "Was für „Gültig“ noch fehlt, steht direkt unter dem Status – jeder Eintrag springt zum Feld. Eine Stornierung kann die Administration aufheben; der Vertrag kehrt dann in seinen früheren Status zurück.",
        ],
        keywords: "gültig gekündigt beendet storniert in arbeit freigabe",
      },
      {
        id: "was-fehlt",
        question: "Wo sehe ich, was an einem Vertrag noch fehlt?",
        answer: ["Auf der Übersicht eines Vertrags zeigt „Was fehlt noch?“ alle Lücken. Jeder Hinweis führt direkt zu dem Feld, in dem er behoben wird; dieselbe Liste erreichen Sie über Strg + K."],
        keywords: "lücken fehlend offene punkte",
      },
      {
        id: "einklappen",
        question: "Kann ich Kästen einklappen?",
        answer: ["Ja: mit dem Pfeil links neben der Überschrift oder per Doppelklick auf eine freie Stelle im Kopf. MedFlux merkt sich eingeklappte Kästen in Ihrem Browser."],
        keywords: "zuklappen ausblenden kasten",
      },
    ],
  },
  {
    id: "ki",
    title: "KI und Prüfung",
    description: "Was die lokale KI tut – und was sie nicht tut.",
    entries: [
      {
        id: "ki-grundsatz",
        question: "Was macht die KI, was das System?",
        answer: [
          "Die KI liest Fakten aus dem Dokument, zum Beispiel Laufzeit, Kündigungsfrist oder Kosten. Fristen, Kosten, Warnungen und Vertragsregeln berechnet das System selbst – nachvollziehbar und ohne KI.",
          "Die KI läuft lokal auf Ihrem Server; Vertragsinhalte verlassen Ihr Haus nicht. Fehlt eine Angabe im Dokument, bleibt das Feld leer – es wird nichts erfunden.",
        ],
        links: [{ label: "Sicherheit & Datenschutz", href: "/sicherheit" }],
        keywords: "künstliche intelligenz lokal ollama datenschutz",
      },
      {
        id: "ki-werte-pruefen",
        question: "Wie prüfe ich Werte der KI?",
        answer: [
          "KI-Werte sind gekennzeichnet und nennen ihre Fundstelle im Dokument. Ein Klick zeigt die Stelle im PDF. Bestätigen oder korrigieren Sie den Wert; danach gilt er als von einer Person geprüft.",
          "Verträge mit offenen Prüfungen stehen in der Vertragsliste unter „Zu prüfen“.",
        ],
        links: [{ label: "Zu prüfen", href: "/register?ansicht=review" }],
        keywords: "bestätigen korrigieren fundstelle nachweis quelle",
      },
      {
        id: "erneut-erfassen",
        question: "Kann die KI ein Dokument erneut auslesen?",
        answer: [
          "Ja, unter Dokumente → Dokument: „Erneut aus dem Dokument erfassen“. Das Ergebnis ist zunächst nur ein Vorschlag; Sie wählen aus, welche Angaben übernommen werden. Von Personen gepflegte Werte werden nie überschrieben.",
          "Ohne KI können Sie einen Wert auch selbst aus dem Text übernehmen: Stelle im Text markieren – Seite und Zitat werden als Nachweis gespeichert.",
        ],
        keywords: "neu analysieren reanalyse vorschlag markieren text",
      },
    ],
  },
  {
    id: "fristen",
    title: "Fristen und Erinnerungen",
    description: "Wie Fristen entstehen und wer erinnert wird.",
    entries: [
      {
        id: "fristen-berechnung",
        question: "Woher kommen die Fristen?",
        answer: [
          "Aus den gepflegten Vertragsdaten: Laufzeitmodell, Beginn, Ende, Kündigungsfrist und Verlängerung. Daraus berechnet MedFlux „Kündbar bis“, das mögliche Vertragsende und die Erinnerung. Das Ergebnis steht im Streifen „Berechnet“ der Karte „Laufzeit, Fristen & Kündigung“; fehlt eine nötige Angabe, nennt er sie mit Link zum Feld.",
          "Alle Fristen und Aufgaben finden Sie unter „Fristen & Aufgaben“; „Nur meine“ zeigt Ihre persönliche Wiedervorlage.",
        ],
        links: [{ label: "Fristen & Aufgaben", href: "/fristen" }],
        keywords: "kündigung kündbar bis vertragsende laufzeit wiedervorlage",
      },
      {
        id: "erinnerung",
        question: "Wer bekommt eine Erinnerung?",
        answer: [
          "Die im Vertrag eingetragene Empfängerin bzw. der Empfänger. Ist niemand eingetragen, geht die Erinnerung an die hauptverantwortliche Person. Benachrichtigungen erscheinen in der Glocke oben rechts.",
          "Wann erinnert wird, legen Sie in den Vertragsdaten unter „Erinnerung & Verantwortung“ → „Erinnern“ fest, z. B. „4 Monate vorher“ und „12 Wochen vorher“. Jede Erinnerung erscheint als Termin unter „Fristen & Aufgaben“.",
        ],
        links: [{ label: "Benachrichtigungen", href: "/postfach" }],
        keywords: "benachrichtigung glocke e-mail empfänger erinnern vorher wochen monate",
      },
      {
        id: "kuendigungsentscheidung",
        question: "Wie bereite ich eine Kündigungsentscheidung vor?",
        answer: [
          "Im Vertrag unter Fristen & Aufgaben zeigt die Karte „Entscheidung“ „Kündbar bis“, das Vertragsende, die jährlichen Kosten und was ohne Handeln passiert. Fakten und Beträge sind berechnet; die Hinweise sind nur Beratung. Entscheiden Sie mit Verlängern, Neu verhandeln, Kündigen oder Beobachten, optional mit „Wirksam am“ und Notiz – frühere Entscheidungen stehen darunter.",
          "Alle anstehenden Entscheidungen aller Verträge stehen unter „Fristen & Aufgaben“ → „Kündigungsentscheidungen“.",
        ],
        links: [{ label: "Kündigungsentscheidungen", href: "/fristen?ansicht=entscheidungen" }],
        keywords: "verlängerung verlängern kündigen entscheidungsvorlage",
      },
    ],
  },
  {
    id: "dokumente",
    title: "Dokumente und Verknüpfungen",
    description: "Nachträge, Rahmenverträge und der Verlauf eines Vertrags.",
    entries: [
      {
        id: "nachtrag",
        question: "Wie füge ich einen Nachtrag oder eine Kündigung hinzu?",
        answer: [
          "Im Vertrag unter Dokumente → Anlagen: „Dokument hinzufügen“, Art wählen (z. B. Nachtrag oder Kündigung) und hochladen. Ein Dokument ist das Hauptdokument; es lässt sich erst entfernen, wenn ein anderes Hauptdokument festgelegt ist.",
          "Liest die KI einen Nachtrag aus, entstehen nur Vorschläge in den Vertragsdaten. Übernommen wird erst, was eine Person bestätigt.",
        ],
        keywords: "anlage nachtrag kündigungsschreiben hauptdokument hochladen",
      },
      {
        id: "rahmenvertrag",
        question: "Wie ordne ich einen Einzelvertrag seinem Rahmenvertrag zu?",
        answer: [
          "Im Vertrag unter Verknüpfungen → „Gehört zu Rahmenvertrag“. Am Rahmenvertrag sehen Sie umgekehrt alle zugeordneten Einzelverträge.",
          "Findet die KI im Dokument einen Verweis auf einen Rahmenvertrag, erscheint er als Vorschlag zum Bestätigen.",
        ],
        keywords: "verknüpfung rahmen einzelvertrag beziehung",
      },
      {
        id: "verlauf",
        question: "Wo sehe ich, wer was geändert hat?",
        answer: [
          "Im Vertrag unter Verlauf: alle Änderungen, Prüfungen, Dokumente und versendeten Erinnerungen, neueste zuerst. Automatische Änderungen (KI, berechnete Fristen, Erinnerungen) sind als „System“ gekennzeichnet.",
          "Für die ganze Organisation gibt es „Aktivitäten & Protokoll“ mit Filtern; Administration und Vertragsmanagement können es als CSV exportieren.",
        ],
        links: [{ label: "Aktivitäten & Protokoll", href: "/audit" }],
        keywords: "historie protokoll änderung audit wer wann csv",
      },
    ],
  },
  {
    id: "finanzen",
    title: "Kosten und Finanzen",
    description: "Wie Kosten erfasst und gerechnet werden.",
    entries: [
      {
        id: "finanzeintraege",
        question: "Wie erfasse ich die Kosten eines Vertrags?",
        answer: [
          "Im Vertrag unter Finanzen → Finanzeinträge: Betrag, Zeitraum und Gültigkeit. Ändert sich der Preis, legen Sie einen neuen Eintrag mit neuem Zeitraum an – so bleibt die Entwicklung nachvollziehbar.",
          "Einzelpreise wie Stundensätze, Reisekosten oder Pauschalen gehören in den Leistungskatalog.",
        ],
        keywords: "kosten preis betrag jahreskosten preiserhöhung stundensatz leistungskatalog",
      },
      {
        id: "kosten-berechnung",
        question: "Wie rechnet MedFlux die Kosten?",
        answer: [
          "Kalkulatorisch auf Basis ganzer Monate aus den gepflegten Finanzeinträgen: laufendes Jahr, bisher, bis zum Ende, gesamte Laufzeit und Jahreswert.",
          "Unbekannte Kosten zählen nie als 0. Summen zeigen deshalb, für wie viele Verträge Kosten bekannt sind. Ist das Vertragsende offen, bleibt „bis zum Ende“ leer.",
          "KI-Vorschläge aus dem Vertrag fließen erst ein, wenn Sie sie übernehmen.",
        ],
        keywords: "summe berechnung abdeckung unbekannt null jahreswert",
      },
      {
        id: "kostenstellen-aufteilung",
        question: "Kann ich Kosten auf mehrere Kostenstellen verteilen?",
        answer: ["Ja, unter Finanzen → Kostenstellen-Aufteilung; die Anteile müssen zusammen 100 % ergeben. Ohne Aufteilung gilt die Kostenstelle aus der Organisationszuordnung."],
        keywords: "kostenstelle verteilen prozent anteil",
      },
    ],
  },
  {
    id: "analysen",
    title: "Analysen",
    description: "Auswertungen über alle Verträge.",
    entries: [
      {
        id: "analysen-seite",
        question: "Was zeigt die Seite „Analysen“?",
        answer: [
          "Das Vertragsportfolio im Überblick, „Kosten nach Bereich“ (Krankenhaus → Abteilung → Verträge), „Gerätearten vergleichen“ und Hinweise aus der KI-Analyse. Gerechnet wird mit laufenden Verträgen; unbekannte Kosten zählen nicht als 0.",
          "Unter „Fragen an das Portfolio“ fragen Sie in eigenen Worten, z. B. „Welche Verträge enden?“; die Antwort nennt die passenden Verträge mit Link.",
        ],
        links: [{ label: "Analysen", href: "/analysen" }],
        keywords: "auswertung bericht portfolio drilldown geräteart vergleich frage",
      },
      {
        id: "excel-export",
        question: "Wie bekomme ich eine Liste für Excel?",
        answer: ["In der Vertragsliste Filter, Spalten und Sortierung einstellen und „Excel exportieren“ wählen. Exportiert wird die aktuelle Auswahl. Eine Einstellung, die Sie öfter brauchen, sichern Sie mit „Ansicht speichern“."],
        links: [{ label: "Vertragsliste", href: "/register" }],
        keywords: "export xlsx tabelle ansicht speichern bericht",
      },
    ],
  },
  {
    id: "farben",
    title: "Farben und Zeichen",
    description: "Was Farben, Formen und Symbole bedeuten.",
    entries: [
      {
        id: "signale",
        question: "Was bedeuten die farbigen Hinweise?",
        answer: [
          "Der Normalzustand ist grau. Braucht etwas Aufmerksamkeit, zeigt MedFlux immer Farbe, Form und Wort zusammen: Achteck = kritisch, Dreieck = prüfen, Kreis mit i = Information, Kreis mit Haken = erledigt, Funke = KI-Vorschlag.",
          "Grün erscheint nur für Bestätigtes oder Vollständiges.",
        ],
        keywords: "signal warnung kritisch grün rot gelb farbe",
      },
      {
        id: "kennfarben",
        question: "Warum haben Vertragstyp, Abteilung und Kostenstelle eigene Farben?",
        answer: ["Das sind Kennfarben: Sie zeigen, um welche Art von Angabe es sich handelt (Vertragstyp, Vertragspartner, Abteilung, Kostenstelle, Geräteart), jeweils mit eigenem Symbol. Sie sagen nichts über einen Zustand aus."],
        keywords: "kennfarbe chip symbol",
      },
    ],
  },
  {
    id: "daten",
    title: "Stammdaten und Verwaltung",
    description: "Grunddaten, Regeln und Rechte.",
    entries: [
      {
        id: "stammdaten",
        question: "Wo pflege ich Vertragspartner, Abteilungen und Kostenstellen?",
        answer: [
          "Alle Grunddaten liegen unter Stammdaten: Vertragspartner, Krankenhäuser, Abteilungen, Kostenstellen, Vertragstypen, Kategorien, Gerätearten und Auswahllisten. Viele Arten lassen sich als CSV importieren und exportieren.",
        ],
        links: [{ label: "Stammdaten", href: "/stammdaten" }],
        keywords: "csv import lieferant partner kostenstelle abteilung",
      },
      {
        id: "vertragsregeln",
        question: "Was sind Vertragsregeln?",
        answer: ["Eigene Prüfregeln Ihrer Organisation, zum Beispiel eine Mindest-Kündigungsfrist oder höchste Jahreskosten. MedFlux prüft jeden Vertrag dagegen; fehlt ein Wert, lautet das Ergebnis „unbekannt“ statt geraten."],
        links: [{ label: "Vertragsregeln", href: "/stammdaten/vertragsregeln" }],
        keywords: "regel playbook richtlinie prüfung",
      },
      {
        id: "rollen",
        question: "Wer darf was?",
        answer: ["Es gibt vier Rollen: Administrator, Vertragsmanager, Prüfer und Leser. Was jede Rolle darf, steht unter Rollen & Rechte. Vertrauliche Verträge sehen nur berechtigte Personen."],
        links: [{ label: "Rollen & Rechte", href: "/settings/roles" }],
        keywords: "rechte berechtigung admin vertraulich",
      },
    ],
  },
  {
    id: "darstellung",
    title: "Darstellung und Konto",
    description: "MedFlux an Ihre Arbeitsweise anpassen.",
    entries: [
      {
        id: "darstellung-anpassen",
        question: "Kann ich die Schrift vergrößern oder ein dunkles Design wählen?",
        answer: [
          "Ja, im Kontomenü oben rechts unter „Darstellung“: Design (Hell, Dunkel, Wie System), Textgröße (bis 125 %) und Dichte (Komfortabel oder Kompakt). Die Einstellungen werden mit Ihrem Konto gespeichert.",
          "Das Design wechseln Sie auch über Strg + K („Dunkles Design einschalten“).",
        ],
        keywords: "dunkel hell dark mode schriftgröße text größer kompakt dichte",
      },
      {
        id: "profil",
        question: "Wo ändere ich meinen Namen oder meine Kontaktdaten?",
        answer: ["Im Kontomenü unter „Mein Profil“: Name, Funktion, Abteilung, Telefon und Foto."],
        links: [{ label: "Mein Profil", href: "/profile" }],
        keywords: "konto name foto telefon kontakt",
      },
    ],
  },
  {
    id: "probleme",
    title: "Wenn etwas nicht klappt",
    description: "Häufige Fälle und was Sie tun können.",
    entries: [
      {
        id: "import-fehlgeschlagen",
        question: "Der Import oder die Analyse ist fehlgeschlagen.",
        answer: [
          "Das Original ist trotzdem gespeichert. Auf der Import-Seite stehen fehlgeschlagene Importe mit einer verständlichen Meldung; von dort starten Sie die Analyse erneut, zum Beispiel wenn die lokale KI wieder bereit ist.",
          "Klappt es weiterhin nicht, können Sie die Angaben von Hand erfassen.",
        ],
        links: [{ label: "Import", href: "/import" }],
        keywords: "fehler fehlgeschlagen analyse erneut versuchen ki nicht bereit",
      },
      {
        id: "wert-fehlt",
        question: "Die KI hat eine Angabe nicht gefunden.",
        answer: [
          "Dann bleibt das Feld leer – MedFlux rät nicht. Neben leeren Feldern und in „Was fehlt noch?“ startet „Im Dokument suchen“ eine gezielte Suche nach genau dieser Angabe.",
          "Sie können den Wert auch selbst eintragen oder ihn aus dem gelesenen Text übernehmen.",
        ],
        links: [{ label: "Erneut erfassen", href: "/hilfe#erneut-erfassen" }],
        keywords: "nicht gefunden leer fehlt im dokument suchen",
      },
      {
        id: "kein-bearbeiten",
        question: "Ich sehe keinen Knopf „Bearbeiten“.",
        answer: ["Ihre Rolle darf diese Angaben nur lesen: Sie sehen alle Daten, können sie aber nicht ändern. Wenden Sie sich an die Administration, wenn Sie mehr Rechte brauchen."],
        links: [{ label: "Rollen & Rechte", href: "/settings/roles" }],
        keywords: "leser lesen rechte gesperrt ändern nicht möglich",
      },
      {
        id: "vertrag-nicht-gefunden",
        question: "Ein Vertrag fehlt in der Liste.",
        answer: [
          "Prüfen Sie zuerst die Reiter: Archivierte Verträge stehen im Archiv. Suche und Filter wirken zusammen – „Alle zurücksetzen“ nimmt Suche und zusätzliche Filter wieder heraus.",
          "Vertrauliche Verträge sehen nur berechtigte Personen, gelöschte nur Administration und Vertragsmanagement.",
        ],
        links: [{ label: "Archiv", href: "/register?ansicht=archive" }],
        keywords: "fehlt nicht da verschwunden archiv gelöscht vertraulich filter",
      },
    ],
  },
];

/** Vergleich ohne Groß-/Kleinschreibung und Akzente („kundigung“ findet „Kündigung“). */
export function normalizeHelpText(text: string) {
  return text.toLocaleLowerCase("de-DE").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function entryText(section: HelpSection, entry: HelpEntry) {
  return normalizeHelpText(`${section.title} ${entry.question} ${entry.answer.join(" ")} ${(entry.steps ?? []).join(" ")} ${entry.keywords ?? ""}`);
}

/** Abschnitte mit den passenden Einträgen (auch über den Abschnittstitel); leere Suche = alles. */
export function searchHelp(query: string): HelpSection[] {
  const term = normalizeHelpText(query.trim());
  if (!term) return HELP_SECTIONS;
  return HELP_SECTIONS
    .map((section) => ({ ...section, entries: section.entries.filter((entry) => entryText(section, entry).includes(term)) }))
    .filter((section) => section.entries.length);
}

export function helpHref(entryId: string) {
  return `/hilfe#${entryId}`;
}
