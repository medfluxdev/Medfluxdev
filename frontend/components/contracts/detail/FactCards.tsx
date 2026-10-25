"use client";

import { useContext, useState, type ReactNode } from "react";
import AiOrigin, { AiReviewContext } from "@/components/ui/AiOrigin";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Signal, { SignalIcon } from "@/components/ui/Signal";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { groupServices } from "@/lib/service-groups";
import { FactCardAction, FactInput, FactMenu, FactSaveBar, FactSourceContext, FactStatus, splitList, useFactCardEdit, type CardFactRow, type FactCardEdit } from "./CardFact";

export const SCOPE_CHOICES = ["Inklusive", "Exklusive"] as const;

const svgIcon = (body: ReactNode) => <svg viewBox="0 0 24 24" focusable="false">{body}</svg>;
const SCOPE_ICON = svgIcon(<path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" />);
const SLA_ICON = svgIcon(<><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>);
const inlineIcon = (body: ReactNode) => <svg className="svc-inline-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const HISTORY_ICON = inlineIcon(<path d="M5 20V10M10 20V4M15 20v-7M20 20v-4" />);
const PEN_ICON = inlineIcon(<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" />);
const CHEVRON_ICON = inlineIcon(<path d="m6 9 6 6 6-6" />);

interface CardContext {
  contractId: string;
  orgSlug: string;
  canEdit: boolean;
  onSaved: () => void;
}

/** Ein Feld im Raster der Vertragsdaten: Bezeichnung oben, Wert mit Herkunft darunter. */
function Field({ edit, row, canEdit, wide, view }: { edit: FactCardEdit; row: CardFactRow; canEdit: boolean; wide?: boolean; view: ReactNode }) {
  return <div className={wide ? "rg-field rg-field--wide" : "rg-field"}>
    <dt>{row.label}</dt>
    <dd>{edit.editing ? <FactInput edit={edit} row={row} /> : <>{view}<FactStatus edit={edit} row={row} canEdit={canEdit} /></>}</dd>
  </div>;
}

export interface ScopeRow {
  key: string;
  label: string;
  /** tone: yes = inklusive, no = exklusive, none = keine Angabe; open = KI-Wert, noch nicht bestätigt. */
  state: { label: string; tone: string; evidence: EvidenceRef | null; open: boolean };
  /** Ja/Nein der KI-Analyse, wenn der Text es nicht eindeutig belegt. */
  suggestion: string | null;
  fact: FactReviewStateDto | undefined;
}

export interface ScopeList {
  key: "other_included" | "other_excluded";
  label: string;
  value: string | null;
  suggestion: string | null;
  fact: FactReviewStateDto | undefined;
}

const QUESTION_ICON = <svg className="signal-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" /><path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5M12 16.5v.5" /></svg>;
const LIST_ICON = svgIcon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />);
const EXCLUDED_ICON = svgIcon(<><circle cx="12" cy="12" r="8" /><path d="m6.5 17.5 11-11" /></>);
const SLA_ROW_ICONS: Record<string, ReactNode> = {
  service_hours: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>,
  response_time: <path d="M13 3 5 13h6l-1 8 8-10h-6z" />,
  resolution_time: <path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9" />,
  emergency_availability: <><path d="M12 3.5 22 20H2z" /><path d="M12 10v4M12 17v.5" /></>,
  sla_notes: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></>,
};
// Reihenfolge der SLA-Zeilen wie im Entwurf: Servicezeiten zuerst.
const SLA_ORDER = ["service_hours", "response_time", "resolution_time", "emergency_availability", "sla_notes"];

/** Vertragsstatus einer Leistung: Farbe + Form + Wort (Inklusive ✓, Exklusive –, Nicht angegeben ?). */
function ScopeStatus({ row }: { row: ScopeRow }) {
  if (row.state.tone === "yes") return <Signal tone="done" size="sm">{row.state.label}</Signal>;
  if (row.state.tone === "no") return <Signal tone="neutral" size="sm">{row.state.label}</Signal>;
  if (row.state.tone === "none") return <Signal tone="neutral" size="sm" icon={QUESTION_ICON}>{row.state.label}</Signal>;
  return <Signal tone="warning" size="sm">{row.state.label}</Signal>;
}

/** Legende unter einer Karte: die bestätigte Plakette und was ein Klick tut. */
function OriginLegend() {
  return <span className="svc-legend"><AiReviewContext.Provider value={null}><AiOrigin state="confirmed" /></AiReviewContext.Provider><span>= von einer Person geprüft · Klick öffnet die Prüfung mit Fundstelle.</span></span>;
}

type ScopeFilter = "all" | "yes" | "no" | "none" | "open";

/**
 * Leistungsumfang: Filter (Alle / Inklusive / Exklusive / Nicht angegeben), Tabelle Leistung · Abdeckung · Herkunft · „⋯“.
 * „Bearbeiten“ legt die Leistungen fest (gleiche Faktprüfung wie bisher).
 */
export function ScopeCard({ rows, historyHref, ...ctx }: CardContext & {
  rows: ScopeRow[];
  /** Prüfverlauf der KI-Werte (Dokumente → Historie). */
  historyHref: string;
}) {
  const title = "Leistungsumfang";
  const edit = useFactCardEdit({ contractId: ctx.contractId, orgSlug: ctx.orgSlug, label: title, onSaved: ctx.onSaved });
  const [filter, setFilter] = useState<ScopeFilter>("all");
  const factRows: CardFactRow[] = rows.map((row) => ({
    factKey: `scope.${row.key}`,
    label: row.label,
    fact: row.fact,
    current: row.state.open || row.state.tone === "none" ? null : row.state.label,
    suggestion: row.suggestion,
    options: SCOPE_CHOICES,
  }));
  const counts = {
    included: rows.filter((row) => row.state.tone === "yes").length,
    excluded: rows.filter((row) => row.state.tone === "no").length,
    missing: rows.filter((row) => row.state.tone === "none").length,
    open: rows.filter((row) => row.state.open).length,
  };
  const filters: { key: ScopeFilter; label: string; count: number; icon?: ReactNode }[] = [
    { key: "all", label: "Alle", count: rows.length },
    { key: "yes", label: "Inklusive", count: counts.included, icon: <SignalIcon tone="done" /> },
    { key: "no", label: "Exklusive", count: counts.excluded, icon: <SignalIcon tone="neutral" /> },
    { key: "none", label: "Nicht angegeben", count: counts.missing, icon: QUESTION_ICON },
    ...(counts.open ? [{ key: "open" as const, label: "Zu prüfen", count: counts.open, icon: <SignalIcon tone="warning" /> }] : []),
  ];
  const shown = rows.map((row, index) => ({ row, index })).filter(({ row }) => filter === "all" || (filter === "open" ? row.state.open : row.state.tone === filter && !row.state.open));
  const summary = <>{counts.included} inklusive · {counts.excluded} exklusive{counts.open ? <> · <Signal tone="warning" size="sm">{counts.open} zu prüfen</Signal></> : null}</>;
  return <CollapsibleSection
    id="leistungsumfang"
    title={title}
    description={edit.editing ? (edit.dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : "KI-Vorschläge bestätigen oder selbst festlegen – gilt als geprüft") : undefined}
    summary={summary}
    icon={SCOPE_ICON}
    iconClassName="section-tile--device"
    actions={<FactCardAction edit={edit} title={title} rows={factRows} canEdit={ctx.canEdit} />}
    forceOpen={edit.editing}
  >
    {edit.editing
      ? <dl className="rg-fields">
        {rows.map((row, index) => <Field key={row.key} edit={edit} row={factRows[index]} canEdit={ctx.canEdit} view={null} />)}
      </dl>
      : <>
        <div className="svc-filters" role="group" aria-label="Leistungen filtern">
          {filters.map((item) => <button key={item.key} type="button" className="svc-filter" aria-pressed={filter === item.key} onClick={() => setFilter(item.key)}>
            {item.icon ? <span className="svc-filter-icon" aria-hidden="true">{item.icon}</span> : null}{item.label}<span className="svc-filter-count">{item.count}</span>
          </button>)}
        </div>
        <table className="scope-table">
          <thead><tr><th scope="col">Leistung</th><th scope="col">Abdeckung</th><th scope="col">Herkunft</th><th scope="col"><span className="sr-only">Aktionen</span></th></tr></thead>
          <tbody>
            {shown.map(({ row, index }) => <tr key={row.key}>
              <th scope="row">{row.label}</th>
              <td><ScopeStatus row={row} /></td>
              <td>{row.state.tone === "none" && !row.fact?.present ? <span className="side-none" aria-label="Keine Herkunft">—</span> : <FactStatus edit={edit} row={factRows[index]} canEdit={ctx.canEdit} compact />}</td>
              <td className="svc-menu"><FactMenu edit={edit} row={factRows[index]} canEdit={ctx.canEdit} /></td>
            </tr>)}
            {shown.length === 0 ? <tr><td colSpan={4} className="side-none">Keine Leistung in dieser Auswahl.</td></tr> : null}
          </tbody>
        </table>
      </>}
    <FactSaveBar edit={edit} title={title} />
    {!edit.editing ? <p className="scope-foot">
      {counts.open ? <Signal tone="ai" size="sm">{counts.open} KI-Werte noch nicht bestätigt</Signal> : <OriginLegend />}
      <a className="rg-link svc-history" href={historyHref}>{HISTORY_ICON}Analyse-Historie</a>
    </p> : null}
  </CollapsibleSection>;
}

/**
 * Thematische Gruppe der weiteren Leistungen, einklappbar. Alle Gruppen stammen aus einer Prüf-Angabe (Optional ›
 * „Weitere inklusive Leistungen“); jede Gruppe zeigt deshalb, woher sie kommt (Seite) und führt mit „Prüfen“ dorthin.
 */
function ServiceGroup({ label, items, fact, factKey, listLabel }: { label: string; items: string[]; fact: FactReviewStateDto | undefined; factKey: string; listLabel: string }) {
  const openSource = useContext(FactSourceContext)?.(fact) ?? null;
  const page = fact?.linked_evidence?.find((entry) => entry.page != null)?.page ?? null;
  const state = fact?.state;
  const origin = state === "confirmed" ? "confirmed" : state === "auto_accepted" ? "auto" : fact?.present && (state === "unreviewed" || state === "needs_review" || state === undefined) ? "unreviewed" : null;
  return <details className="svc-group" open>
    <summary>
      <span className="svc-group-chevron" aria-hidden="true">{CHEVRON_ICON}</span>
      <span className="svc-group-title">{label}</span>
      <span className="svc-group-src">
        {page != null ? <button type="button" className="cw-source-button svc-group-page" onClick={(event) => { event.preventDefault(); openSource?.(); }} disabled={!openSource} aria-label={`Fundstelle zu ${label}: Seite ${page}`}>Seite {page}</button> : null}
        {origin ? <AiOrigin state={origin} onOpenSource={openSource} factKey={factKey} subject={`${listLabel}: ${label}`} /> : null}
      </span>
      <span className="svc-group-count">{items.length} {items.length === 1 ? "Punkt" : "Punkte"}</span>
    </summary>
    <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
  </details>;
}

/**
 * „Weitere inklusive Leistungen“ (thematisch zusammengefasst) bzw. „Exklusive Leistungen“ (warme Karte – kosten extra):
 * Liste aus dem Dokument, von Hand ergänzbar (Faktprüfung `scope.other_*`).
 */
export function ScopeListCard({ list, ...ctx }: CardContext & { list: ScopeList }) {
  const excluded = list.key === "other_excluded";
  const edit = useFactCardEdit({ contractId: ctx.contractId, orgSlug: ctx.orgSlug, label: list.label, onSaved: ctx.onSaved });
  const row: CardFactRow = { factKey: `scope.${list.key}`, label: list.label, fact: list.fact, current: list.value, suggestion: list.suggestion, list: true };
  const items = splitList(list.value);
  const groups = groupServices(items);
  const grouped = !excluded && items.length > 3 && groups.length > 1;
  return <CollapsibleSection
    id={excluded ? "exklusive-leistungen" : "weitere-leistungen"}
    title={list.label}
    description={edit.editing ? (edit.dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : "Je Zeile eine Leistung") : excluded ? undefined : grouped ? "Thematisch zusammengefasst · vollständiger Wortlaut in der Quelle" : "Zusätzlich zum Leistungsumfang vereinbart"}
    summary={items.length ? `${items.length} ${items.length === 1 ? "Leistung" : "Leistungen"}` : "Keine"}
    icon={excluded ? EXCLUDED_ICON : LIST_ICON}
    iconClassName={excluded ? "section-tile--unit" : "section-tile--device"}
    className={excluded ? "scope-list-card scope-list-card--excluded" : "scope-list-card"}
    actions={<FactCardAction edit={edit} title={list.label} rows={[row]} canEdit={ctx.canEdit} />}
    forceOpen={edit.editing}
  >
    {edit.editing
      ? <dl className="rg-fields"><Field wide edit={edit} row={row} canEdit={ctx.canEdit} view={null} /></dl>
      : <>
        {items.length === 0 ? <p className="side-none">Keine angegeben</p>
          : excluded ? <div className="svc-excluded-text">{items.map((item) => <p key={item}>{item}</p>)}</div>
            : grouped ? <div className="svc-groups">{groups.map((group) => <ServiceGroup key={group.label} label={group.label} items={group.items} fact={list.fact} factKey={row.factKey} listLabel={list.label} />)}</div>
              : <ul className="scope-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>}
        <div className="svc-card-foot">
          <span className="svc-card-origin"><FactStatus edit={edit} row={row} canEdit={ctx.canEdit} compact />{!excluded && list.fact?.state === "confirmed" ? <span className="svc-legend-text">= von einer Person geprüft · Klick öffnet die Prüfung mit Fundstelle.</span> : null}</span>
          <FactMenu edit={edit} row={row} canEdit={ctx.canEdit} />
        </div>
      </>}
    <FactSaveBar edit={edit} title={list.label} />
  </CollapsibleSection>;
}

export interface SlaRow {
  key: string;
  label: string;
  value: string | null;
  suggestion: string | null;
  empty: string;
  wide?: boolean;
  fact: FactReviewStateDto | undefined;
}

/** Service-Level (SLA): je Angabe eine Zeile mit Symbol, Servicezeiten groß; „Angaben ergänzen“ öffnet das Bearbeiten. */
export function SlaCard({ rows, ...ctx }: CardContext & { rows: SlaRow[] }) {
  const title = "Service-Level (SLA)";
  const edit = useFactCardEdit({ contractId: ctx.contractId, orgSlug: ctx.orgSlug, label: title, onSaved: ctx.onSaved });
  const ordered = [...rows].sort((x, y) => SLA_ORDER.indexOf(x.key) - SLA_ORDER.indexOf(y.key))
    // „Weitere SLA-Angaben“ nur zeigen, wenn es welche gibt (oder beim Bearbeiten).
    .filter((row) => row.key !== "sla_notes" || row.value || edit.editing);
  const factRows: CardFactRow[] = ordered.map((row) => ({ factKey: `sla.${row.key}`, label: row.label, fact: row.fact, current: row.value, suggestion: row.suggestion }));
  const missing = ordered.filter((row) => !row.value).length;
  const summary = <>{ordered.filter((row) => row.value && !row.wide).map((row) => `${row.label} ${row.value}`).join(" · ") || "Keine Angaben"}</>;
  return <CollapsibleSection
    id="sla"
    title={title}
    description={edit.editing ? (edit.dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : "KI-Vorschläge bestätigen oder selbst eintragen – gilt als geprüft") : undefined}
    summary={summary}
    icon={SLA_ICON}
    iconClassName="section-tile--type"
    actions={<FactCardAction edit={edit} title={title} rows={factRows} canEdit={ctx.canEdit} />}
    forceOpen={edit.editing}
  >
    {edit.editing
      ? <dl className="rg-fields">{ordered.map((row, index) => <Field key={row.key} wide={row.wide} edit={edit} row={factRows[index]} canEdit={ctx.canEdit} view={null} />)}</dl>
      : <dl className="sla-list">
        {ordered.map((row, index) => <div key={row.key} className={`sla-row${row.key === "service_hours" && row.value ? " sla-row--lead" : ""}`}>
          <span className="sla-row-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">{SLA_ROW_ICONS[row.key]}</svg></span>
          <dt>{row.label}</dt>
          <dd>
            <span className="sla-row-value">{row.value ? <span className="sla-value">{row.value}</span> : <span className="sla-empty">{row.empty}</span>}</span>
            <FactStatus edit={edit} row={factRows[index]} canEdit={ctx.canEdit} compact />
          </dd>
          <span className="svc-menu"><FactMenu edit={edit} row={factRows[index]} canEdit={ctx.canEdit} /></span>
        </div>)}
      </dl>}
    <FactSaveBar edit={edit} title={title} />
    {!edit.editing && missing > 0 ? (ctx.canEdit
      ? <p className="sla-foot"><button type="button" className="rg-link svc-complete" onClick={() => edit.start(factRows)}>{PEN_ICON}Angaben ergänzen</button></p>
      : <p className="sla-note"><SignalIcon tone="info" />Fehlende Angaben können ergänzt werden, sobald weitere Vertragsinformationen vorliegen.</p>) : null}
  </CollapsibleSection>;
}
