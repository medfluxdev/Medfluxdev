"use client";

import type { ReactNode } from "react";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import Signal from "@/components/ui/Signal";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import { FactCardAction, FactInput, FactSaveBar, FactStatus, splitList, useFactCardEdit, type CardFactRow, type FactCardEdit } from "./CardFact";

export const SCOPE_CHOICES = ["Inklusive", "Exklusive"] as const;

const svgIcon = (body: ReactNode) => <svg viewBox="0 0 24 24" focusable="false">{body}</svg>;
const SCOPE_ICON = svgIcon(<path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" />);
const SLA_ICON = svgIcon(<><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>);

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

function ListValue({ value, empty }: { value: string | null; empty: string }) {
  const items = splitList(value);
  if (!items.length) return <span className="side-none">{empty}</span>;
  return <ul className="card-fact-items">{items.map((item) => <li key={item}>{item}</li>)}</ul>;
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

/** Leistungsumfang wie die Karten der Vertragsdaten; „Bearbeiten“ legt Leistungen fest und ergänzt eigene. */
export function ScopeCard({ rows, lists, counts, source, ...ctx }: CardContext & {
  rows: ScopeRow[];
  lists: ScopeList[];
  counts: { included: number; excluded: number; unknown: number };
  source: (evidence: EvidenceRef | null) => ReactNode;
}) {
  const title = "Leistungsumfang";
  const edit = useFactCardEdit({ contractId: ctx.contractId, orgSlug: ctx.orgSlug, label: title, onSaved: ctx.onSaved });
  const factRows: CardFactRow[] = rows.map((row) => ({
    factKey: `scope.${row.key}`,
    label: row.label,
    fact: row.fact,
    current: row.state.open || row.state.tone === "none" ? null : row.state.label,
    suggestion: row.suggestion,
    options: SCOPE_CHOICES,
  }));
  const listRows: CardFactRow[] = lists.map((list) => ({ factKey: `scope.${list.key}`, label: list.label, fact: list.fact, current: list.value, suggestion: list.suggestion, list: true }));
  const summary = <>{counts.included} inklusive · {counts.excluded} exklusive{counts.unknown ? <> · <Signal tone="warning" size="sm">{counts.unknown} zu prüfen</Signal></> : null}</>;
  return <CollapsibleSection
    id="leistungsumfang"
    title={title}
    description={edit.editing ? (edit.dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : "KI-Vorschläge bestätigen oder selbst festlegen – gilt als geprüft") : "Was der Vertrag abdeckt – laut Dokument"}
    summary={summary}
    icon={SCOPE_ICON}
    iconClassName="section-tile--device"
    actions={<FactCardAction edit={edit} title={title} rows={[...factRows, ...listRows]} canEdit={ctx.canEdit} />}
    forceOpen={edit.editing}
  >
    <div className="scope-summary">
      <Signal tone={counts.included > 0 ? "done" : "neutral"}>{counts.included} inklusive</Signal>
      <Signal tone="neutral">{counts.excluded} exklusive</Signal>
      <Signal tone={counts.unknown > 0 ? "warning" : "neutral"}>{counts.unknown} zu prüfen</Signal>
    </div>
    <dl className="rg-fields">
      {rows.map((row, index) => <Field key={row.key} edit={edit} row={factRows[index]} canEdit={ctx.canEdit} view={<>
        {row.state.tone === "none" ? <span className="side-none">{row.state.label}</span> : <span className="rg-value">{row.state.label}</span>}
        {source(row.state.evidence)}
      </>} />)}
      {lists.map((list, index) => <Field key={list.key} wide edit={edit} row={listRows[index]} canEdit={ctx.canEdit} view={<ListValue value={list.value} empty="Keine" />} />)}
    </dl>
    <FactSaveBar edit={edit} title={title} />
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

/** SLA wie die Karten der Vertragsdaten; „Bearbeiten“ übernimmt KI-Vorschläge oder trägt Werte selbst ein. */
export function SlaCard({ rows, ...ctx }: CardContext & { rows: SlaRow[] }) {
  const title = "SLA";
  const edit = useFactCardEdit({ contractId: ctx.contractId, orgSlug: ctx.orgSlug, label: title, onSaved: ctx.onSaved });
  const factRows: CardFactRow[] = rows.map((row) => ({ factKey: `sla.${row.key}`, label: row.label, fact: row.fact, current: row.value, suggestion: row.suggestion }));
  const summary = <>{rows.filter((row) => row.value && !row.wide).map((row) => `${row.label} ${row.value}`).join(" · ") || "Keine Angaben"}</>;
  return <CollapsibleSection
    id="sla"
    title={title}
    description={edit.editing ? (edit.dirty ? "Ungespeicherte Änderungen · Strg+S speichert" : "KI-Vorschläge bestätigen oder selbst eintragen – gilt als geprüft") : "Zugesagte Reaktions- und Servicezeiten"}
    summary={summary}
    icon={SLA_ICON}
    iconClassName="section-tile--type"
    actions={<FactCardAction edit={edit} title={title} rows={factRows} canEdit={ctx.canEdit} />}
    forceOpen={edit.editing}
  >
    <dl className="rg-fields">
      {rows.map((row, index) => <Field key={row.key} wide={row.wide} edit={edit} row={factRows[index]} canEdit={ctx.canEdit} view={
        row.value ? <span className="rg-value">{row.value}</span> : <span className="side-none">{row.empty}</span>
      } />)}
    </dl>
    <FactSaveBar edit={edit} title={title} />
  </CollapsibleSection>;
}
