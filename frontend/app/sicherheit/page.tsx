"use client";

import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";

// Für IT, Datenschutz und Einkauf: wie MedFlux mit Vertragsdaten umgeht. Nur belegbare Aussagen.
export default function SecurityPage() {
  return <div className="page page-narrow security-page">
    <PageHeader
      title="Sicherheit & Datenschutz"
      description="Wie MedFlux mit Ihren Verträgen umgeht – für IT, Datenschutz und Einkauf."
    />

    <section className="card card-pad" aria-labelledby="sec-data">
      <h2 id="sec-data" className="card-title">Ihre Daten bleiben in Ihrem Haus</h2>
      <ul>
        <li>Verträge, Dokumente und Analyseergebnisse liegen auf dem Server Ihrer Einrichtung (PostgreSQL-Datenbank und Dateiablage).</li>
        <li>MedFlux sendet keine Vertragsinhalte an externe Dienste – auch nicht an KI-Anbieter in der Cloud.</li>
        <li>Steht die Datenbank auf einem anderen Rechner, ist im Pilot- und Produktivbetrieb eine verschlüsselte Verbindung (TLS) Pflicht.</li>
      </ul>
    </section>

    <section className="card card-pad" aria-labelledby="sec-ai">
      <h2 id="sec-ai" className="card-title">KI ohne Cloud</h2>
      <ul>
        <li>Die KI-Analyse läuft über einen lokalen Modelldienst (z. B. Ollama), standardmäßig auf demselben Rechner. Dienst und Modell legt die Administration unter <Link href="/settings">Einstellungen → Lokale KI</Link> fest.</li>
        <li>Die KI liest nur Fakten aus. Fristen, Kosten, Warnungen und Vertragsregeln berechnet das System selbst.</li>
        <li>Jeder KI-Wert nennt seine Fundstelle im Dokument und ist als Vorschlag gekennzeichnet, bis ihn eine Person bestätigt. Fehlt eine Angabe, bleibt sie leer – es wird nichts erfunden.</li>
      </ul>
    </section>

    <section className="card card-pad" aria-labelledby="sec-access">
      <h2 id="sec-access" className="card-title">Zugriff</h2>
      <ul>
        <li>Anmeldung mit persönlichem Konto; Passwörter werden nur als Hash gespeichert (PBKDF2-SHA256).</li>
        <li>Vier Rollen mit festgelegten Rechten – siehe <Link href="/settings/roles">Rollen & Rechte</Link>. Konten können auf ein Krankenhaus oder eine Abteilung beschränkt werden.</li>
        <li>Vertrauliche Verträge sehen nur Administration, verantwortliche Person, Erinnerungsempfänger und ausdrücklich freigegebene Konten.</li>
      </ul>
    </section>

    <section className="card card-pad" aria-labelledby="sec-audit">
      <h2 id="sec-audit" className="card-title">Nachvollziehbarkeit</h2>
      <ul>
        <li>Die <Link href="/audit">Historie</Link> zeigt, wer wann was geändert hat; automatische Änderungen sind als „System“ gekennzeichnet.</li>
        <li>Löschen ist zweistufig: Verträge werden zuerst nur als gelöscht markiert und bleiben wiederherstellbar.</li>
      </ul>
    </section>

    <section className="card card-pad" aria-labelledby="sec-yours">
      <h2 id="sec-yours" className="card-title">Was Ihre IT sicherstellt</h2>
      <ul>
        <li>Verschlüsselung der Datenträger bzw. der Dateiablage (z. B. BitLocker) – MedFlux verschlüsselt die Ablage nicht selbst.</li>
        <li>Regelmäßige Datensicherung von Datenbank und Dateiablage.</li>
        <li>Erreichbarkeit nur im Kliniknetz bzw. über den Zugang Ihrer Einrichtung.</li>
      </ul>
    </section>
  </div>;
}
