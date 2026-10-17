"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { reviewContractFact } from "@/lib/domain-api/contracts";
import type { FactReviewStateDto } from "@/lib/contract-detail-types";
import AiOrigin, { AiReviewContext } from "@/components/ui/AiOrigin";
import ActionMenu, { type ActionMenuItem } from "@/components/ui/ActionMenu";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { useSaveShortcut, useUnsavedChanges } from "@/components/ui/useFormGuards";

const OPEN_STATES = new Set(["unreviewed", "needs_review"]);
const MANUAL_NOTE = "In der Vertragsakte von Hand eingetragen.";
/** Trenner der Listen-Angaben (wie `LIST_SEPARATOR` im Backend). */
export const LIST_SEPARATOR = "; ";

export function splitList(value: string | null | undefined): string[] {
  return (value ?? "").split(";").map((item) => item.trim()).filter(Boolean);
}

/** Wirksamer Wert einer Prüf-Angabe: von einer Person bestätigt/korrigiert vor dem Wert aus dem Dokument. */
export function factValue(fact: FactReviewStateDto | undefined, documentValue: string | null | undefined): string | null {
  if ((fact?.state === "corrected" || fact?.state === "confirmed") && fact.effective_value != null && fact.effective_value !== "") return String(fact.effective_value);
  return documentValue ?? null;
}

/** Eine Angabe einer Karte, die über die Faktprüfung bestätigt oder von Hand geändert wird. */
export interface CardFactRow {
  factKey: string;
  label: string;
  fact: FactReviewStateDto | undefined;
  /** Wert, mit dem das Eingabefeld startet (leer = keiner). */
  current: string | null;
  /** Vorschlag der KI-Analyse (noch nicht von einer Person bestätigt). */
  suggestion?: string | null;
  /** Feste Auswahl (z. B. Enthalten/Ausgeschlossen); ohne = Freitext. */
  options?: readonly string[];
  /** Liste mehrerer Einträge (z. B. weitere Leistungen); gespeichert mit `LIST_SEPARATOR`. */
  list?: boolean;
}

/** Ein offener KI-Vorschlag: vorhanden und noch von keiner Person geprüft. */
export function openSuggestion(row: CardFactRow): string | null {
  const state = row.fact?.state ?? "unreviewed";
  return row.suggestion && OPEN_STATES.has(state) ? row.suggestion : null;
}

/**
 * Bearbeiten einer ganzen Karte wie in Vertragsdaten. Gespeichert wird in der Faktprüfung (`/fact-reviews`):
 * ein übernommener KI-Vorschlag als Bestätigung, ein eigener Wert als Korrektur – jeweils mit Prüfer und Verlauf.
 */
export function useFactCardEdit({ contractId, orgSlug, label, onSaved }: { contractId: string; orgSlug: string; label: string; onSaved: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const [initial, setInitial] = useState<Record<string, string>>({});
  const [confirmKeys, setConfirmKeys] = useState<Set<string>>(new Set());
  const [rows, setRows] = useState<CardFactRow[]>([]);
  const [busy, setBusy] = useState(false);
  const editing = draft !== null;
  const normalized = (row: CardFactRow) => {
    const raw = draft?.[row.factKey] ?? "";
    return row.list ? splitList(raw).join(LIST_SEPARATOR) : raw.trim();
  };
  const changed = rows.filter((row) => {
    const next = normalized(row);
    const start = initial[row.factKey] ?? "";
    if (next === start) return false;
    // Leeren ist nur bei Listen eine Änderung (alle Einträge entfernt); ein leeres Feld lässt den Wert stehen.
    return Boolean(next) || (row.list && Boolean(start));
  });
  const toConfirm = rows.filter((row) => confirmKeys.has(row.factKey) && openSuggestion(row) && !changed.includes(row));
  const dirty = changed.length > 0 || toConfirm.length > 0;
  useUnsavedChanges(dirty);

  /** Startet mit dem angezeigten Wert – auch einem noch nicht bestätigten KI-Wert. */
  function start(nextRows: CardFactRow[]) {
    const values = Object.fromEntries(nextRows.map((row) => [row.factKey, row.current ?? openSuggestion(row) ?? ""]));
    setRows(nextRows);
    setInitial(values);
    setDraft(values);
    setConfirmKeys(new Set());
  }

  async function post(row: CardFactRow, action: "confirmed" | "corrected" | "reopened", value?: string) {
    await reviewContractFact(contractId, orgSlug, {
      fact_key: row.factKey,
      action,
      ...(action === "corrected" ? { corrected_value: value, note: MANUAL_NOTE } : {}),
      expected_reviewed_at: row.fact?.reviewed_at ?? null,
    });
  }

  async function run(work: () => Promise<void>, success: string) {
    setBusy(true);
    try {
      await work();
      toast(success, "success");
      setDraft(null);
      onSaved();
    } catch (err) {
      const conflict = err instanceof ApiError && err.status === 409;
      toast(conflict ? "Eine Angabe wurde inzwischen geändert – Stand neu geladen." : "Die Angaben konnten nicht gespeichert werden.", "error");
      if (conflict) { setDraft(null); onSaved(); }
    } finally {
      setBusy(false);
    }
  }

  function save() {
    if (!dirty) { setDraft(null); return; }
    void run(async () => {
      for (const row of changed) {
        const next = normalized(row);
        // Wieder der KI-Wert = Bestätigung; alles andere ist ein eigener Wert.
        const asDocument = Boolean(row.fact?.present) && next === String(row.fact?.original_value ?? "");
        await post(row, asDocument ? "confirmed" : "corrected", next || "–");
      }
      for (const row of toConfirm) await post(row, "confirmed");
    }, `${label} gespeichert.`);
  }

  function confirm(row: CardFactRow) {
    void run(() => post(row, "confirmed"), `${row.label} bestätigt.`);
  }

  /** Entscheidung zurücknehmen: die Angabe ist in der Faktprüfung wieder offen. */
  function reopen(row: CardFactRow) {
    void run(() => post(row, "reopened"), `${row.label}: Prüfung zurückgenommen.`);
  }

  useSaveShortcut(editing, save);

  const openKeys = rows.filter((row) => openSuggestion(row)).map((row) => row.factKey);
  return {
    editing,
    busy,
    dirty,
    start,
    cancel: () => setDraft(null),
    save,
    confirm,
    reopen,
    value: (factKey: string) => draft?.[factKey] ?? "",
    set: (factKey: string, value: string) => setDraft((current) => (current ? { ...current, [factKey]: value } : current)),
    /** KI-Wert beim Speichern bestätigen (nur offene KI-Werte). */
    willConfirm: (factKey: string) => confirmKeys.has(factKey),
    toggleConfirm: (factKey: string, on: boolean) => setConfirmKeys((current) => {
      const next = new Set(current);
      if (on) next.add(factKey); else next.delete(factKey);
      return next;
    }),
    /** Alle offenen KI-Werte zum Bestätigen vormerken (gespeichert wird mit „Speichern“). */
    confirmAll: () => setConfirmKeys(new Set(openKeys)),
    hasOpenSuggestions: openKeys.some((key) => !confirmKeys.has(key)),
  };
}

export type FactCardEdit = ReturnType<typeof useFactCardEdit>;

/** Kopf-Aktion der Karte: „Bearbeiten“ bzw. im Bearbeiten „Abbrechen“. */
export function FactCardAction({ edit, title, rows, canEdit }: { edit: FactCardEdit; title: string; rows: CardFactRow[]; canEdit: boolean }) {
  if (edit.editing) return <button type="button" className="btn btn-sm btn-ghost" disabled={edit.busy} onClick={edit.cancel} aria-label={`Abbrechen (${title})`}>Abbrechen</button>;
  if (!canEdit) return null;
  return <button type="button" className="btn btn-sm" disabled={edit.busy} onClick={() => edit.start(rows)} aria-label={`${title} bearbeiten`} title="Bearbeiten">Bearbeiten</button>;
}

/** Unter dem Eingabefeld: offener KI-Wert mit „Bestätigen“ bzw. – nach einer Änderung – „KI-Wert wiederherstellen“. */
function SuggestionHint({ edit, row }: { edit: FactCardEdit; row: CardFactRow }) {
  const suggestion = openSuggestion(row);
  if (!suggestion) return null;
  const draft = edit.value(row.factKey);
  const same = row.list ? splitList(draft).join(LIST_SEPARATOR) === splitList(suggestion).join(LIST_SEPARATOR) : draft.trim() === suggestion;
  if (!same && row.list) {
    // Eigene Einträge bleiben; fehlende KI-Einträge lassen sich einzeln wieder aufnehmen.
    const present = new Set(splitList(draft).map((item) => item.toLocaleLowerCase("de")));
    const missing = splitList(suggestion).filter((item) => !present.has(item.toLocaleLowerCase("de")));
    if (!missing.length) return null;
    return <span className="card-fact-hint"><StaticAiOrigin />{missing.map((item) => <button key={item} type="button" className="rg-link" onClick={() => edit.set(row.factKey, [...splitList(draft), item].join(LIST_SEPARATOR))} aria-label={`${item} wieder aufnehmen`}>+ {item}</button>)}</span>;
  }
  if (!same) {
    return <span className="card-fact-hint"><StaticAiOrigin /><span>{row.list ? splitList(suggestion).join(", ") : suggestion}</span><button type="button" className="rg-link" onClick={() => edit.set(row.factKey, suggestion)} aria-label={`KI-Vorschlag für ${row.label} wiederherstellen`}>Wiederherstellen</button></span>;
  }
  return <label className="card-fact-hint"><input type="checkbox" checked={edit.willConfirm(row.factKey)} onChange={(event) => edit.toggleConfirm(row.factKey, event.target.checked)} /><StaticAiOrigin />bestätigen</label>;
}

/** Liste eigener Einträge: entfernen mit ✕, hinzufügen über das Eingabefeld. */
function ListEditor({ edit, row }: { edit: FactCardEdit; row: CardFactRow }) {
  const [entry, setEntry] = useState("");
  const items = splitList(edit.value(row.factKey));
  const write = (next: string[]) => edit.set(row.factKey, next.join(LIST_SEPARATOR));
  function add() {
    const value = entry.replace(/;/g, ",").trim();
    if (!value) return;
    if (!items.some((item) => item.toLocaleLowerCase("de") === value.toLocaleLowerCase("de"))) write([...items, value]);
    setEntry("");
  }
  return <span className="card-fact-list">
    {items.length ? <ul aria-label={row.label}>{items.map((item) => <li key={item}>{item}<button type="button" className="btn btn-icon btn-sm btn-ghost" onClick={() => write(items.filter((other) => other !== item))} aria-label={`${item} entfernen`}>✕</button></li>)}</ul> : null}
    <span className="card-fact-add">
      <input type="text" maxLength={120} value={entry} aria-label={`${row.label}: Eintrag hinzufügen`} placeholder="Leistung eintragen" onChange={(event) => setEntry(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); add(); } }} />
      <button type="button" className="btn btn-sm" onClick={add} disabled={!entry.trim()}>Hinzufügen</button>
    </span>
  </span>;
}

/** Eingabe einer Angabe im Bearbeiten, mit KI-Vorschlag darunter. */
export function FactInput({ edit, row }: { edit: FactCardEdit; row: CardFactRow }) {
  const id = `card-fact-${row.factKey.replace(/\W/g, "-")}`;
  let control: ReactNode;
  if (row.list) {
    control = <ListEditor edit={edit} row={row} />;
  } else if (row.options) {
    control = <select id={id} className="card-fact-input" aria-label={row.label} value={edit.value(row.factKey)} onChange={(event) => edit.set(row.factKey, event.target.value)}>
      <option value="">Nicht festgelegt</option>
      {row.options.map((option) => <option key={option} value={option}>{option}</option>)}
    </select>;
  } else {
    control = <input id={id} type="text" className="card-fact-input" aria-label={row.label} maxLength={300} placeholder="Selbst eintragen" value={edit.value(row.factKey)} onChange={(event) => edit.set(row.factKey, event.target.value)} />;
  }
  return <span className="card-fact-field">{control}<SuggestionHint edit={edit} row={row} /></span>;
}

/** Öffnet die Fundstelle einer Angabe (von der Vertragsseite bereitgestellt); ohne Fundstelle null. */
/** Im Bearbeiten: Plakette ohne Sprung (sonst gingen Eingaben verloren). */
const StaticAiOrigin = () => <AiReviewContext.Provider value={null}><AiOrigin state="unreviewed" /></AiReviewContext.Provider>;

export const FactSourceContext = createContext<((fact: FactReviewStateDto | undefined) => (() => void) | null) | null>(null);

/** Herkunft wie in Vertragsdaten: „KI · Vorschlag“ (mit „Bestätigen“), „KI · bestätigt“, „KI · korrigiert“, „Manuell“. */
export function FactStatus({ edit, row, canEdit, compact = false }: { edit: FactCardEdit; row: CardFactRow; canEdit: boolean; /** Nur die Plakette; Bestätigen/Zurücknehmen stehen dann im „⋯“-Menü (`FactMenu`). */ compact?: boolean }) {
  const state = row.fact?.state ?? "unreviewed";
  const who = row.fact?.reviewer_display_name;
  const fromDocument = row.fact?.original_value != null && row.fact.original_value !== "";
  // Jede Entscheidung bleibt änderbar: „Zurücknehmen“ öffnet die Angabe wieder (ein eigener Wert ohne KI-Wert entfällt dann).
  const openSource = useContext(FactSourceContext)?.(row.fact) ?? null;
  const undo = canEdit && !compact ? <button type="button" className="rg-link" disabled={edit.busy} onClick={() => edit.reopen(row)} aria-label={`${row.label}: Prüfung zurücknehmen`} title={fromDocument ? "Wieder als KI-Vorschlag offen" : "Eigenen Wert entfernen"}>Zurücknehmen</button> : null;
  if (state === "auto_accepted") {
    return <><AiOrigin state="auto" onOpenSource={openSource} factKey={row.factKey} subject={row.label} />{undo}</>;
  }
  if (state === "confirmed") {
    return <><AiOrigin state="confirmed" onOpenSource={openSource} factKey={row.factKey} subject={row.label} detail={who ? `bestätigt von ${who}` : null} />{undo}</>;
  }
  if (state === "corrected") {
    return <><span className={`rg-origin ${fromDocument ? "rg-origin-ai_corrected" : "rg-origin-manual"}`} title={who ? `Eingetragen von ${who}` : undefined}>{fromDocument ? "KI · korrigiert" : "Manuell"}</span>{undo}</>;
  }
  if (!row.fact?.present || !OPEN_STATES.has(state)) return null;
  return <>
    <AiOrigin state="unreviewed" onOpenSource={openSource} factKey={row.factKey} subject={row.label} detail={row.fact.ai_confidence != null ? `KI-Sicherheit ${Math.round(row.fact.ai_confidence * 100)} %` : row.fact.found_by_rule ? "von festen Regeln wörtlich gefunden" : null} />
    {canEdit && !compact ? <button type="button" className="rg-link" disabled={edit.busy} onClick={() => edit.confirm(row)} aria-label={`${row.label} bestätigen`}>Bestätigen</button> : null}
  </>;
}

const MENU_ICON = {
  source: <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4" /></svg>,
  confirm: <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>,
  undo: <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3" /></svg>,
};

/** „⋯“ je Angabe: Quelle öffnen, Bestätigen (offener KI-Wert) bzw. Bestätigung zurücknehmen. Ohne Aktion nichts. */
export function FactMenu({ edit, row, canEdit }: { edit: FactCardEdit; row: CardFactRow; canEdit: boolean }) {
  const openSource = useContext(FactSourceContext)?.(row.fact) ?? null;
  const state = row.fact?.state ?? "unreviewed";
  const items: ActionMenuItem[] = [];
  if (openSource) items.push({ label: "Quelle öffnen", icon: MENU_ICON.source, onSelect: openSource });
  if (canEdit && row.fact?.present && OPEN_STATES.has(state)) items.push({ label: "Bestätigen", icon: MENU_ICON.confirm, onSelect: () => void edit.confirm(row), disabled: edit.busy });
  if (canEdit && (state === "confirmed" || state === "corrected" || state === "auto_accepted")) {
    items.push({ label: state === "corrected" && !(row.fact?.original_value != null && row.fact.original_value !== "") ? "Eigenen Wert entfernen" : "Bestätigung zurücknehmen", icon: MENU_ICON.undo, onSelect: () => void edit.reopen(row), disabled: edit.busy });
  }
  return items.length ? <ActionMenu label={`Weitere Aktionen: ${row.label}`} items={items} /> : null;
}

/** Speicherleiste unter der Karte (wie in Vertragsdaten), mit „Alle KI-Vorschläge übernehmen“. */
export function FactSaveBar({ edit, title }: { edit: FactCardEdit; title: string }) {
  if (!edit.editing) return null;
  return <div className="cw-savebar" role="region" aria-label={`${title} speichern`}>
    <div className="cw-savebar-msg">
      {edit.dirty ? <><Signal tone="info" size="sm">Ungespeicherte Änderungen</Signal><span><kbd>Strg</kbd> + <kbd>S</kbd> speichert</span></> : <span>Keine Änderungen</span>}
      {edit.hasOpenSuggestions ? <button type="button" className="rg-link" onClick={edit.confirmAll}>Alle KI-Vorschläge bestätigen</button> : null}
    </div>
    <div className="cw-savebar-actions">
      <button type="button" className="btn btn-ghost" disabled={edit.busy} onClick={edit.cancel}>Verwerfen</button>
      <button type="button" className="btn btn-primary" disabled={edit.busy} onClick={edit.save} aria-keyshortcuts="Control+S">{edit.busy ? "Wird gespeichert…" : "Speichern"}</button>
    </div>
  </div>;
}
