"use client";

import { useState } from "react";
import AiOrigin from "@/components/ui/AiOrigin";
import Badge from "@/components/ui/Badge";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import Button from "@/components/ui/Button";
import DataTable, { type Column } from "@/components/ui/DataTable";
import Dialog from "@/components/ui/Dialog";
import Drawer from "@/components/ui/Drawer";
import EmptyState from "@/components/ui/EmptyState";
import Field from "@/components/ui/Field";
import InlineAlert from "@/components/ui/InlineAlert";
import KpiTile from "@/components/ui/KpiTile";
import Signal from "@/components/ui/Signal";
import SectionCard from "@/components/ui/SectionCard";
import Skeleton from "@/components/ui/Skeleton";
import Tabs, { TabPanel } from "@/components/ui/Tabs";
import Tooltip from "@/components/ui/Tooltip";

// Lebende Referenz der Bausteine (docs/FRONTEND_CONVENTIONS.md). Alle Werte hier sind
// erkennbar Beispieltext fuer Entwickler, keine Vertragsdaten.

const TYPE_SCALE = [
  ["--text-display", "Anzeige – eine Überschrift je Seite"],
  ["--text-title-l", "Titel L – Seitentitel (24 px)"],
  ["--text-title-m", "Titel M – Panel und Dialog (20 px)"],
  ["--text-title-s", "Titel S – Abschnitt (18 px)"],
  ["--text-body", "Fließtext (16 px) – Standard"],
  ["--text-small", "Klein (14 px) – dichte Tabellen, Hilfetexte"],
  ["--text-caption", "Beschriftung (12 px) – nur Metadaten"],
] as const;

const COLOR_TOKENS = [
  "--color-bg", "--color-surface", "--color-surface-muted", "--color-text", "--color-text-muted", "--color-brand", "--color-accent", "--color-link", "--color-focus",
  "--color-success", "--color-warning", "--color-danger", "--color-info", "--color-ai",
] as const;

type Row = { name: string; count: number };
const ROWS: Row[] = [{ name: "Beispiel A", count: 3 }, { name: "Beispiel B", count: 12 }, { name: "Beispiel C", count: 7 }];
const COLUMNS: Column<Row>[] = [
  { key: "name", label: "Name", render: (row) => row.name, sortValue: (row) => row.name, rowHeader: true },
  { key: "count", label: "Anzahl", render: (row) => row.count, sortValue: (row) => row.count, numeric: true },
];

export default function ComponentReference() {
  const [tab, setTab] = useState<"one" | "two">("one");
  const [dialog, setDialog] = useState(false);
  const [drawer, setDrawer] = useState(false);

  return (
    <div className="stack-4">
        <p className="field-hint">Lebende Referenz für Tokens und gemeinsame Komponenten. Regeln: docs/FRONTEND_CONVENTIONS.md.</p>
        <SectionCard title="Hervorgehobener Seitenkopf">
          <p className="field-hint">PageHeader mit variant=&quot;highlight&quot; – nur für Einstiegs- und Übersichtsseiten, höchstens einer je Seite. In hell und dunkel gleich.</p>
          <div className="page-hero" role="presentation">
            <div><span className="page-hero-eyebrow">Bereich</span><strong>Seitentitel</strong><p>Kurze Beschreibung der Seite.</p></div>
            <div className="page-actions"><button type="button" className="btn">Aktion</button><button type="button" className="btn btn-primary">Hauptaktion</button></div>
          </div>
        </SectionCard>
        <SectionCard title="Schrift">
          <div className="stack-3">
            {TYPE_SCALE.map(([token, label]) => (
              <p key={token} className="sg-type" style={{ fontSize: `var(${token})` }}>
                {label} <code>{token}</code>
              </p>
            ))}
            <p className="sg-mono"><code>--font-mono</code> 000123 · 1.234,56 € · tabellarische Ziffern</p>
          </div>
        </SectionCard>

        <SectionCard title="Farben (semantisch)">
          <ul className="sg-swatches">
            {COLOR_TOKENS.map((token) => (
              <li key={token}><span className="sg-swatch" style={{ background: `var(${token})` }} aria-hidden="true" /><code>{token}</code></li>
            ))}
          </ul>
          <p className="field-hint">Keine Hex-Werte in Komponenten – stylelint verweigert sie. Dunkles Design über dieselben Tokens.</p>
        </SectionCard>

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
            <Field label="Kurzbezeichnung" htmlFor="ref-name" hint="Hilfetext unter dem Feld, nicht als Platzhalter.">
              <input id="ref-name" defaultValue="Beispieltext" />
            </Field>
            <Field label="Auswahl" htmlFor="ref-select" error="Fehlermeldung sagt, was zu tun ist.">
              <select id="ref-select" defaultValue="">
                <option value="" disabled>Bitte wählen</option>
                <option>Option 1</option>
              </select>
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Kennzeichen und Meldungen">
          <div className="stack-3">
            <div className="page-actions">
              <Badge>Neutral</Badge><Badge tone="info">Information</Badge><Badge tone="success">Erledigt</Badge>
              <Badge tone="warning">Prüfen</Badge><Badge tone="danger">Überfällig</Badge><Badge tone="ai">KI-Prüfung offen</Badge>
              <Tooltip text="Tooltips nur für Zusatzinfos, nie für Pflichtangaben."><Badge>Mit Tooltip</Badge></Tooltip>
            </div>
            <InlineAlert tone="info" role="status">Zusätzliche Information</InlineAlert>
            <InlineAlert tone="success" role="status">Änderung gespeichert</InlineAlert>
            <InlineAlert tone="warning" role="alert">Angaben müssen geprüft werden</InlineAlert>
            <InlineAlert tone="critical" role="alert">Aktion konnte nicht abgeschlossen werden</InlineAlert>
          </div>
        </SectionCard>

        <SectionCard title="Signale (Ruhe & Signal)">
          <p className="field-hint">Farbe + Form + Wort, nie Farbe allein. Normalzustand ist grau; Grün nur für Bestätigtes.</p>
          <div className="sg-row">
            <Signal tone="critical">Kritisch</Signal>
            <Signal tone="warning">Prüfen</Signal>
            <Signal tone="info">Hinweis</Signal>
            <Signal tone="done">Bestätigt</Signal>
            <Signal tone="ai">KI-Prüfung offen</Signal>
            <Signal tone="neutral">Ruhig</Signal>
          </div>
        </SectionCard>

        <SectionCard title="KI-Herkunft eines Werts">
          <p className="field-hint">Jeder Wert aus der KI trägt diese Plakette: „Bestätigt“ (von einer Person) oder „Ungeprüft“. Mit Fundstelle ist sie ein Knopf und öffnet die Quelle.</p>
          <div className="sg-row">
            <AiOrigin state="confirmed" />
            <AiOrigin state="unreviewed" />
            <AiOrigin state="confirmed" onOpenSource={() => {}} subject="Beispiel" />
            <AiOrigin state="unreviewed" onOpenSource={() => {}} subject="Beispiel" />
            <AiOrigin state="auto" />
          </div>
        </SectionCard>

        <SectionCard title="Zustände">
          <div className="sg-grid">
            <Skeleton lines={3} label="Beispiel lädt…" />
            <EmptyState title="Noch keine Einträge" action={<Button size="sm">Ersten Eintrag anlegen</Button>}>Leere Zustände nennen den nächsten Schritt.</EmptyState>
            <EmptyState variant="calm" title="Alles erledigt">Ruhige Variante für Übersichtskarten (grau, kein Grün).</EmptyState>
          </div>
        </SectionCard>

        <SectionCard title="Kennzahlen">
          <div className="sg-grid">
            <KpiTile label="Kennzahl" value="42" hint="Hinweis zur Herkunft" href="/developer/components" linkLabel="Ziel öffnen" />
            <KpiTile label="Ohne Daten" value={null} />
            <KpiTile label="Mit Signal" value={null} signal={{ tone: "warning", label: "Kosten fehlen bei 3 Verträgen" }} />
          </div>
        </SectionCard>

        <SectionCard title="Navigation">
          <div className="stack-3">
            <Breadcrumbs items={[{ label: "Start", href: "/" }, { label: "Bereich", href: "/developer" }, { label: "Aktuelle Seite" }]} />
            <Tabs label="Beispiel-Reiter" idPrefix="sg-tab" items={[{ key: "one", label: "Erster" }, { key: "two", label: "Zweiter", badge: 2 }]} active={tab} onChange={setTab} />
            <TabPanel idPrefix="sg-tab" active={tab}><p>Inhalt des Reiters „{tab === "one" ? "Erster" : "Zweiter"}“. Pfeiltasten wechseln den Reiter.</p></TabPanel>
          </div>
        </SectionCard>

        <SectionCard title="Tabelle">
          <DataTable caption="Sortierbare Beispieltabelle" columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} initialSort={{ key: "count", dir: "desc" }} />
        </SectionCard>

        <SectionCard title="Dialog und Seitenleiste">
          <div className="page-actions">
            <Button onClick={() => setDialog(true)}>Dialog öffnen</Button>
            <Button onClick={() => setDrawer(true)}>Seitenleiste öffnen</Button>
          </div>
          <Dialog open={dialog} title="Bestätigung" description="Dialoge nur für Entscheidungen, die den Ablauf unterbrechen müssen." onClose={() => setDialog(false)}
            actions={<><Button onClick={() => setDialog(false)}>Abbrechen</Button><Button variant="primary" onClick={() => setDialog(false)}>Bestätigen</Button></>} />
          <Drawer open={drawer} title="Vorschau" onClose={() => setDrawer(false)}><p>Seitenleisten für Vorschau und Details, ohne die Seite zu verlassen.</p></Drawer>
        </SectionCard>
    </div>
  );
}
