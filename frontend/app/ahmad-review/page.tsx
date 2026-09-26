"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

type ReviewArea = { title: string; capability: string; status: string; next: string };
const AREAS: ReviewArea[] = [
  { title: "Dokumentenimport und lokale Analyse", capability: "PDF/DOCX-Import, Ergebnisse pro Dokument und Review-Link sind vorhanden.", status: "Vorhanden · reale Vertragsabnahme ausstehend", next: "Neunseitigen Frankfurt-Vertrag einschließlich Original-PDF-Quellenbezug end-to-end prüfen." },
  { title: "Zielabteilung und Erfassungsmethode", capability: "Arbeitsbereich ist vorhanden. In dieser Testversion bestätigt der Importdialog den aktuellen Bereich und den nutzbaren KI-Review-Pfad.", status: "Teilweise · manueller und direkter KI-Pfad geplant", next: "Drei echte Workflows mit serverseitiger Modus-/Abteilungswahl und Audit finalisieren." },
  { title: "Kostenberechnung und Vertragsfristen", capability: "Bestehende Berechnungs- und Review-Module; gezielte isolierte Finanztests bestanden.", status: "Vorhanden · vollständige fachliche Abnahme ausstehend", next: "Steuern, Preisstaffelung, Zahlungszeitpunkte, Kündigungsfrist und Verlängerung an Krankenhausbeispielen vergleichen." },
  { title: "Vertrags- und Risikobenachrichtigungen", capability: "Benachrichtigungs-/Aufgaben-APIs und UI sind im bestehenden Projekt angelegt.", status: "Teilweise · institutionelle E-Mail-Zustellung nicht abgenommen", next: "Eskalation, Empfängerwahl, E-Mail-Adapter und Fristentests mit Ahmad spezifizieren." },
  { title: "Kostenstellennummer-Suche", capability: "Scoped-Stammdaten aus der bestehenden Kostenstellen-API sind durchsuchbar.", status: "Neue Testansicht · keine verifizierten Budgetzahlen", next: "Finanzhistorie und geprüfte Kostenzuordnungen bereitstellen." },
  { title: "Monats-/Jahresvergleich und Prognosen", capability: "Erweiterte Analyse und Prognosemethodik sind dokumentiert, aber nicht als klinisch reale Finanzdaten verifiziert.", status: "Geplant · nicht als betriebsbereit ausgeben", next: "24 Monate oder verfügbare Perioden freigegebener Finanzdaten, Backtesting und Szenario-Review." },
  { title: "Rollen, Sicherheit und Datenschutz", capability: "Bereichsabhängige Endpunkte und Authentisierung sind vorhanden.", status: "Vorhanden · Freigabetests offen", next: "Berechtigungsmatrix mit dem Krankenhaus abstimmen; Pilot ohne echte sensible Dokumente beginnen." },
];

export default function AhmadReviewPage() {
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [decisions, setDecisions] = useState<Record<number, string>>({});
  const [copied, setCopied] = useState(false);
  const summary = useMemo(() => AREAS.map((item, i) =>
    [item.title, "Stand: " + item.status, "Ahmad: " + (decisions[i] || "Offen"),
     "Notizen: " + (notes[i]?.trim() || "—"), "Nächster Schritt: " + item.next].join("\n")
  ).join("\n\n"), [notes, decisions]);
  return (
    <div className="page">
      <header className="entity-header"><h1>Ahmad · Krankenhaus-Pilotprüfung</h1>
        <p className="page-sub">Ehrliche Bestandsaufnahme: übernehmen, ergänzen oder reduzieren. Kein offizieller Freigabebericht ohne fachliche Prüfung.</p>
      </header>
      <section className="card card-pad">
        <h2>Wie soll Ahmad vorgehen?</h2>
        <p>Für jede Funktion entscheiden: übernehmen, ändern, entfernen oder zunächst offenlassen. Fehlende Praxisabläufe und Dokumente können ohne echte Patientendaten beschrieben werden.</p>
        <p><Link href="/import">Vertragsimport testen</Link> · <Link href="/kostenstellen-suche">Kostenstelle suchen</Link> · <Link href="/analysen">Bestehende Analysen</Link></p>
      </section>
      {AREAS.map((item, i) => (
        <section className="card card-pad" key={item.title}>
          <h2>{i + 1}. {item.title}</h2>
          <p>{item.capability}</p><p><strong>Status: {item.status}</strong></p>
          <p className="muted small">Offene Arbeit: {item.next}</p>
          <label htmlFor={`ahmad-decision-${i}`}>Bewertung durch Ahmad</label>
          <select id={`ahmad-decision-${i}`} value={decisions[i] || ""} onChange={(e) => setDecisions((old) => ({ ...old, [i]: e.target.value }))}>
            <option value="">Noch nicht bewertet</option>
            <option>Übernehmen</option><option>Ändern</option><option>Nicht benötigt</option><option>Später prüfen</option>
          </select>
          <label htmlFor={`ahmad-note-${i}`}>Praxisablauf / fehlende oder überflüssige Funktion</label>
          <textarea id={`ahmad-note-${i}`} rows={3} value={notes[i] || ""} onChange={(e) => setNotes((old) => ({ ...old, [i]: e.target.value }))} placeholder="Ahmads Beobachtungen …" />
        </section>
      ))}
      <section className="card card-pad">
        <h2>Rückmeldung exportieren</h2>
        <p>Notizen werden in dieser frühen Pilotversion <strong>nicht automatisch gespeichert</strong>. Vor dem Verlassen bitte den Bericht kopieren.</p>
        <button className="btn btn-primary" onClick={async () => { try { await navigator.clipboard.writeText(summary); setCopied(true); } catch { setCopied(false); } }}>
          Bericht in Zwischenablage kopieren
        </button>
        <textarea aria-label="Berichtstext zum manuellen Kopieren" readOnly value={summary} rows={9} />
        {copied ? <p role="status">Bericht kopiert.</p> : null}
      </section>
    </div>
  );
}
