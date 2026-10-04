"use client";

import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import SectionCard from "@/components/ui/SectionCard";
import StatusBadge from "@/components/ui/StatusBadge";

export default function ComponentReferencePage() {
  return (
    <div className="page">
      <PageHeader
        title="UI-Komponenten"
        description="Lokale Referenz für gemeinsame Medflux-Komponenten und Zustände."
      />

      <div className="stack-4">
        <SectionCard title="Buttons">
          <div className="page-actions">
            <Button variant="primary">Primäraktion</Button>
            <Button>Standard</Button>
            <Button variant="danger">Kritische Aktion</Button>
            <Button size="sm">Kompakt</Button>
            <Button disabled>Deaktiviert</Button>
            <Button loading>Speichern</Button>
          </div>
        </SectionCard>

        <SectionCard title="Formularfelder">
          <div className="stack-4 max-w-form">
            <Field label="Vertragsnummer" htmlFor="ref-contract" hint="Beispiel für einen Hilfetext.">
              <input id="ref-contract" defaultValue="MF-2026-001" />
            </Field>
            <Field label="Kostenstelle" htmlFor="ref-cost" error="Bitte eine gültige Kostenstelle wählen.">
              <select id="ref-cost" defaultValue="">
                <option value="" disabled>Bitte wählen</option>
                <option>Radiologie</option>
              </select>
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Status">
          <div className="page-actions">
            <StatusBadge label="Neutral" />
            <StatusBadge label="Information" tone="information" />
            <StatusBadge label="Aktiv" tone="success" />
            <StatusBadge label="Prüfung erforderlich" tone="review" />
            <StatusBadge label="Warnung" tone="warning" />
            <StatusBadge label="Kritisch" tone="critical" />
            <StatusBadge label="Veraltet" tone="stale" />
          </div>
        </SectionCard>

        <SectionCard title="Meldungen und Ladezustand">
          <div className="stack-3">
            <InlineAlert>Neutraler Hinweis</InlineAlert>
            <InlineAlert tone="info" role="status">Zusätzliche Information</InlineAlert>
            <InlineAlert tone="success" role="status">Änderung gespeichert</InlineAlert>
            <InlineAlert tone="warning" role="alert">Daten müssen geprüft werden</InlineAlert>
            <InlineAlert tone="critical" role="alert">Aktion konnte nicht abgeschlossen werden</InlineAlert>
            <LoadingState>Daten werden geladen…</LoadingState>
          </div>
        </SectionCard>

        <SectionCard title="Tabellendichte">
          <div className="table-scroll">
            <table className="contract-table table-density-comfortable">
              <thead><tr><th>Vertrag</th><th>Status</th><th>Verantwortlich</th></tr></thead>
              <tbody><tr><td>MF-2026-001</td><td>Aktiv</td><td>Max Mustermann</td></tr></tbody>
            </table>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
