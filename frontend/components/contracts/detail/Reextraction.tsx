"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Button from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import InlineAlert from "@/components/ui/InlineAlert";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { MISSING_SEARCH, SEARCH_PARAM, baseFieldKey } from "@/lib/fix-targets";
import {
  applyReextraction,
  cancelReextraction,
  discardReextraction,
  getReextraction,
  getReextractionModels,
  startReextraction,
  type FactGroup,
  type FactRow,
  type ReextractionModel,
  type ReextractionMode,
  type ReextractionState,
} from "@/lib/domain-api/reextraction";

const POLL_MS = 4000;

type FieldOption = { key: string; label: string };

/** Vertragsdaten-Feld (Basisname, z. B. notice_period) → Angaben zum Suchen. */
export function fieldSearchMap(state: ReextractionState | null): Map<string, FieldOption[]> {
  const out = new Map<string, FieldOption[]>();
  for (const [key, options] of Object.entries(state?.field_search ?? {})) {
    const base = baseFieldKey(key);
    const known = out.get(base) ?? [];
    for (const option of options) if (!known.some((item) => item.key === option.key)) known.push(option);
    out.set(base, known);
  }
  return out;
}

/** „4“, „4-6“, „4, 7–8“ → Seitenzahlen; null bei ungültiger Eingabe. Höchstens 20 Seiten. */
export function parsePages(text: string): number[] | null {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const pages = new Set<number>();
  for (const part of trimmed.split(/[,;\s]+/).filter(Boolean)) {
    const match = /^(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?$/.exec(part);
    if (!match) return null;
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    if (from < 1 || to < from || to - from > 19) return null;
    for (let page = from; page <= to; page += 1) pages.add(page);
  }
  return pages.size > 20 ? null : [...pages].sort((a, b) => a - b);
}

function message(error: unknown, fallback: string) {
  return error instanceof ApiError && error.message ? error.message : fallback;
}

/** Stand der erneuten Erfassung; fragt nach, solange ein Lauf wartet oder läuft. */
export function useReextraction(contractId: string, orgSlug: string) {
  const [state, setState] = useState<ReextractionState | null>(null);
  const reload = useCallback(() => {
    getReextraction(orgSlug, contractId).then(setState).catch(() => setState(null));
  }, [contractId, orgSlug]);
  useEffect(reload, [reload]);
  const active = state?.run?.status === "queued" || state?.run?.status === "running";
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [active, reload]);
  return { state, reload };
}

/** Hinweis im Kopf der Vertragsakte: läuft gerade / Ergebnis liegt vor. */
export function ReextractionBanner({ state, onOpen }: { state: ReextractionState | null; onOpen: () => void }) {
  const run = state?.run;
  if (!run) return null;
  if (run.status === "queued" || run.status === "running") {
    return <InlineAlert tone="info" role="status" action={<Button size="sm" onClick={onOpen}>Anzeigen</Button>}>
      {run.status === "queued" ? "Erneute Erfassung wartet auf die lokale KI." : "Das Dokument wird erneut ausgewertet. Sie können weiterarbeiten."}
    </InlineAlert>;
  }
  if (run.status === "ready" && !run.stale) {
    const found = (run.summary.new ?? 0) + (run.summary.changed ?? 0);
    return <InlineAlert tone="info" role="status" action={<Button size="sm" onClick={onOpen}>Prüfen</Button>}>
      {found ? `Erneute Erfassung abgeschlossen: ${found} Angabe${found === 1 ? "" : "n"} zum Prüfen.` : "Erneute Erfassung abgeschlossen: keine zusätzlichen Angaben gefunden."}
    </InlineAlert>;
  }
  return null;
}

const GROUP_TITLE: Record<FactGroup, string> = {
  new: "Neu gefunden",
  changed: "Abweichend vom bisherigen Wert",
  missing_again: "Nicht erneut gefunden – der bisherige Wert bleibt",
  same: "Unverändert",
};

interface PanelProps {
  contractId: string;
  orgSlug: string;
  state: ReextractionState | null;
  reload: () => void;
  /** Nach der Übernahme: Vertragsakte neu laden. */
  onApplied: () => void;
  /** Quelle im Dokument zeigen (Seite). */
  onShowPage?: (page: number) => void;
  /** „Selbst erfassen“: zu den Vertragsdaten. */
  onEditManually?: () => void;
  /** „Stelle im Dokument markieren“: Angabe aus dem Text übernehmen. */
  onMarkInDocument?: () => void;
}

/** Abschnitt „Erneut aus dem Dokument erfassen“ (Dokumente → Dokument). */
export default function ReextractionPanel({ contractId, orgSlug, state, reload, onApplied, onShowPage, onEditManually, onMarkInDocument }: PanelProps) {
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchFor = searchParams?.get(SEARCH_PARAM) ?? null;
  const [dialog, setDialog] = useState<null | { advanced: boolean; fields?: FieldOption[] }>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = state?.run ?? null;
  const rows = useMemo(() => state?.rows ?? [], [state?.rows]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    setSelected(new Set(rows.filter((row) => row.preselected).map((row) => row.key)));
  }, [run?.id, rows]);

  // „Im Dokument suchen“ am leeren Feld: Dialog mit genau diesem Feld öffnen, Parameter danach entfernen.
  const handledSearch = useRef<string | null>(null);
  useEffect(() => {
    if (!searchFor || !state || handledSearch.current === searchFor) return;
    handledSearch.current = searchFor;
    const busyRun = state.run?.status === "queued" || state.run?.status === "running";
    if (state.can_start && !busyRun) {
      if (searchFor === MISSING_SEARCH) setDialog({ advanced: false });
      else {
        const fields = fieldSearchMap(state).get(baseFieldKey(searchFor));
        if (fields?.length) setDialog({ advanced: false, fields });
      }
    }
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.delete(SEARCH_PARAM);
    router.replace(`${pathname ?? ""}?${params.toString()}`, { scroll: false });
  }, [searchFor, state, pathname, router, searchParams]);

  if (!state || (!state.can_start && !run)) return null;

  async function act(work: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    try {
      await work();
      if (done) toast(done, "success");
      reload();
    } catch (err) {
      setError(message(err, "Die Aktion ist fehlgeschlagen."));
    } finally {
      setBusy(false);
    }
  }

  const active = run?.status === "queued" || run?.status === "running";
  const ready = run?.status === "ready";
  const selectable = rows.filter((row) => row.group === "new" || row.group === "changed");
  const toggle = (key: string) => setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return <section className="cw-section reextraction" aria-labelledby="rg-reextraction-heading">
    <div className="cw-section-head">
      <div>
        <h2 id="rg-reextraction-heading">{state.first_analysis ? "Mit der KI aus dem Dokument erfassen" : "Erneut aus dem Dokument erfassen"}</h2>
        <p>{state.first_analysis
          ? "Dieser Vertrag wurde von Hand erfasst. Die lokale KI kann das Dokument auswerten; Sie sehen jeden gefundenen Wert und übernehmen nur, was Sie auswählen. Von Hand eingetragene Werte bleiben."
          : "Hat die KI beim ersten Mal etwas übersehen? Lassen Sie das Dokument erneut auswerten. Ihre Vertragsdaten ändern sich erst, wenn Sie Ergebnisse übernehmen."}</p>
      </div>
      {!active && !ready && state.can_start ? <Button variant="primary" onClick={() => setDialog({ advanced: false })}>{state.first_analysis ? "Auswerten …" : "Erneut erfassen …"}</Button> : null}
    </div>

    {!state.can_start && state.blocked_reason && !run ? <p className="cw-muted">{state.blocked_reason}</p> : null}
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}

    {active ? <InlineAlert tone="info" role="status" action={<Button size="sm" loading={busy} onClick={() => act(() => cancelReextraction(orgSlug, contractId, run!.id), "Erneute Erfassung wird abgebrochen.")}>Abbrechen</Button>}>
      {run!.status === "queued"
        ? run!.queue_position > 0 ? `Wartet – ${run!.queue_position} Auswertung${run!.queue_position === 1 ? "" : "en"} vor dieser.` : "Wartet auf die lokale KI …"
        : "Das Dokument wird erneut ausgewertet. Das dauert je nach Umfang einige Minuten; Sie können weiterarbeiten."}
    </InlineAlert> : null}

    {run?.status === "failed" ? <InlineAlert tone="critical" role="alert" action={state.can_start ? <Button size="sm" onClick={() => setDialog({ advanced: true })}>Erneut versuchen</Button> : null}>
      {run.message ?? "Die erneute Erfassung ist fehlgeschlagen."}
    </InlineAlert> : null}

    {run?.status === "applied" ? <p className="cw-muted" role="status">Zuletzt übernommen: {run.applied_keys.length} Angabe{run.applied_keys.length === 1 ? "" : "n"}{run.finished_at ? ` (Auswertung vom ${new Date(run.finished_at).toLocaleDateString("de-DE")})` : ""}.</p> : null}

    {ready && run ? <Comparison
      rows={rows}
      selected={selected}
      onToggle={toggle}
      stale={run.stale}
      busy={busy}
      onSelectAllNew={() => setSelected(new Set(rows.filter((row) => row.group === "new").map((row) => row.key)))}
      onApply={() => act(async () => {
        const result = await applyReextraction(orgSlug, contractId, run.id, [...selected]);
        toast(`${result.message} Von Hand gepflegte Werte bleiben; abweichende Angaben erscheinen in den Vertragsdaten als Vorschlag.`, "success");
        onApplied();
      })}
      onDiscard={() => act(() => discardReextraction(orgSlug, contractId, run.id), "Ergebnis verworfen.")}
      onRetry={() => setDialog({ advanced: true })}
      onEditManually={onEditManually}
      onMarkInDocument={onMarkInDocument}
      onShowPage={onShowPage}
      nothingFound={selectable.length === 0}
    /> : null}

    {dialog ? <StartDialog
      contractId={contractId}
      orgSlug={orgSlug}
      state={state}
      advanced={dialog.advanced}
      preset={dialog.fields}
      onClose={() => setDialog(null)}
      onStarted={() => { setDialog(null); toast("Erneute Erfassung gestartet.", "info"); reload(); }}
    /> : null}
  </section>;
}

function Comparison({ rows, selected, onToggle, stale, busy, onSelectAllNew, onApply, onDiscard, onRetry, onEditManually, onMarkInDocument, onShowPage, nothingFound }: {
  rows: FactRow[];
  selected: Set<string>;
  onToggle: (key: string) => void;
  stale: boolean;
  busy: boolean;
  onSelectAllNew: () => void;
  onApply: () => void;
  onDiscard: () => void;
  onRetry: () => void;
  onEditManually?: () => void;
  onMarkInDocument?: () => void;
  onShowPage?: (page: number) => void;
  nothingFound: boolean;
}) {
  const groups = (["new", "changed", "missing_again", "same"] as FactGroup[])
    .map((group) => ({ group, items: rows.filter((row) => row.group === group) }))
    .filter((entry) => entry.items.length > 0);

  if (stale) {
    return <InlineAlert tone="warning" role="status" action={<><Button size="sm" onClick={onRetry}>Erneut erfassen …</Button> <Button size="sm" onClick={onDiscard} loading={busy}>Verwerfen</Button></>}>
      Die Vertragsdaten wurden inzwischen geändert. Dieses Ergebnis kann nicht mehr übernommen werden.
    </InlineAlert>;
  }
  if (nothingFound) {
    return <div className="reextraction-empty">
      <p><strong>Keine zusätzlichen Angaben gefunden.</strong> Die bisherigen Werte bleiben unverändert.</p>
      <div className="reextraction-actions">
        <Button size="sm" onClick={onRetry}>Mit anderen Einstellungen versuchen …</Button>
        {onMarkInDocument ? <Button size="sm" onClick={onMarkInDocument}>Stelle im Dokument markieren</Button> : null}
        {onEditManually ? <Button size="sm" onClick={onEditManually}>Selbst erfassen</Button> : null}
        <Button size="sm" onClick={onDiscard} loading={busy}>Verwerfen</Button>
      </div>
    </div>;
  }
  return <div className="reextraction-result">
    <p className="cw-muted">Angehakte Angaben werden übernommen. Neu gefundene Angaben mit Fundstelle sind vorausgewählt; Abweichungen wählen Sie selbst.</p>
    <table className="reextraction-table">
      <thead><tr><th scope="col"><span className="sr-only">Übernehmen</span></th><th scope="col">Angabe</th><th scope="col">Bisher</th><th scope="col">Neu</th><th scope="col">Fundstelle</th></tr></thead>
      {groups.map(({ group, items }) => <tbody key={group}>
        <tr className="reextraction-group"><th scope="rowgroup" colSpan={5}>{GROUP_TITLE[group]} ({items.length})</th></tr>
        {items.map((row) => {
          const choosable = row.group === "new" || row.group === "changed";
          return <tr key={row.key}>
            <td>{choosable ? <input type="checkbox" checked={selected.has(row.key)} onChange={() => onToggle(row.key)} aria-label={`${row.label} übernehmen`} /> : null}</td>
            <th scope="row">{row.label}</th>
            <td>{row.current ?? <span className="cw-muted">–</span>}</td>
            <td>{row.proposed ?? <span className="cw-muted">nicht gefunden</span>}</td>
            <td>{row.evidence.length ? row.evidence.slice(0, 1).map((item, index) => <span key={index} className="reextraction-evidence">
              {item.page && onShowPage ? <button type="button" className="rg-link" onClick={() => onShowPage(item.page!)}>S. {item.page}</button> : item.page ? `S. ${item.page}` : null}
              {item.quote ? <q>{item.quote.length > 140 ? `${item.quote.slice(0, 140)} …` : item.quote}</q> : null}
            </span>) : <span className="cw-muted">{row.proposed ? "ohne Fundstelle" : "–"}</span>}</td>
          </tr>;
        })}
      </tbody>)}
    </table>
    <div className="reextraction-actions">
      <Button variant="primary" onClick={onApply} loading={busy} loadingLabel="Wird übernommen…" disabled={selected.size === 0}>Ausgewählte übernehmen ({selected.size})</Button>
      <Button onClick={onSelectAllNew} disabled={busy}>Alle neu gefundenen auswählen</Button>
      <Button onClick={onDiscard} disabled={busy}>Verwerfen</Button>
    </div>
  </div>;
}

function StartDialog({ contractId, orgSlug, state, advanced, preset, onClose, onStarted }: {
  contractId: string;
  orgSlug: string;
  state: ReextractionState;
  advanced: boolean;
  /** Vorausgewählte Angaben (z. B. aus „Im Dokument suchen“ am Feld). */
  preset?: FieldOption[];
  onClose: () => void;
  onStarted: () => void;
}) {
  // Auswahlliste: fehlende Angaben plus die vorausgewählten (auch wenn sie nicht als fehlend gelten).
  const options = useMemo(() => {
    const list = [...state.missing];
    for (const item of preset ?? []) if (!list.some((known) => known.key === item.key)) list.push(item);
    return list;
  }, [preset, state.missing]);
  const hasMissing = options.length > 0;
  const [mode, setMode] = useState<ReextractionMode>(hasMissing ? "missing_fields" : "full");
  const [fields, setFields] = useState<Set<string>>(new Set((preset?.length ? preset : state.missing).map((item) => item.key)));
  const [pagesText, setPagesText] = useState("");
  const pages = parsePages(pagesText);
  const [reread, setReread] = useState(state.reread_suggested);
  const [models, setModels] = useState<ReextractionModel[] | null>(null);
  const [model, setModel] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getReextractionModels(orgSlug, contractId)
      .then((result) => { if (alive) { setModels(result.models); setModel(result.current_model ?? ""); } })
      .catch(() => { if (alive) setModels([]); });
    return () => { alive = false; };
  }, [contractId, orgSlug]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await startReextraction(orgSlug, contractId, {
        mode,
        fields: mode === "missing_fields" ? [...fields] : [],
        page_hint: pages ?? [],
        reread_document: reread,
        model_id: model || null,
      });
      onStarted();
    } catch (err) {
      setError(message(err, "Die erneute Erfassung konnte nicht gestartet werden."));
    } finally {
      setBusy(false);
    }
  }

  const invalid = (mode === "missing_fields" && fields.size === 0) || pages === null;
  return <Dialog
    open
    title="Erneut aus dem Dokument erfassen"
    description="Die lokale KI wertet das Vertragsdokument erneut aus. Ihre Vertragsdaten bleiben unverändert, bis Sie Ergebnisse übernehmen."
    onClose={onClose}
    actions={<>
      <Button onClick={onClose} disabled={busy}>Abbrechen</Button>
      <Button variant="primary" onClick={submit} loading={busy} loadingLabel="Wird gestartet…" disabled={invalid}>Auswertung starten</Button>
    </>}
  >
    <fieldset className="reextraction-scope">
      <legend>Umfang</legend>
      <label className="md-check"><input type="radio" name="reextraction-mode" checked={mode === "missing_fields"} disabled={!hasMissing} onChange={() => setMode("missing_fields")} /> Nur fehlende Angaben suchen</label>
      {mode === "missing_fields" ? <ul className="reextraction-fields">
        {options.map((item) => <li key={item.key}><label className="md-check"><input type="checkbox" checked={fields.has(item.key)} onChange={() => setFields((prev) => {
          const next = new Set(prev);
          if (next.has(item.key)) next.delete(item.key); else next.add(item.key);
          return next;
        })} /> {item.label}</label></li>)}
      </ul> : null}
      {!hasMissing ? <p className="field-hint">Für die Fristberechnung und „Gültig“ fehlt nichts.</p> : null}
      <label className="md-check"><input type="radio" name="reextraction-mode" checked={mode === "full"} onChange={() => setMode("full")} /> Ganzes Dokument neu auswerten</label>
    </fieldset>
    <div className="field reextraction-pages">
      <label htmlFor="reextraction-pages" className="field-label">Wo steht es? (optional)</label>
      <input id="reextraction-pages" type="text" inputMode="numeric" value={pagesText} onChange={(event) => setPagesText(event.target.value)} placeholder="z. B. 4 oder 4–6" aria-invalid={pages === null} aria-describedby="reextraction-pages-hint" />
      <span id="reextraction-pages-hint" className="field-hint">{pages === null ? "Bitte Seiten wie „4“, „4–6“ oder „4, 7“ angeben (höchstens 20)." : "Die KI liest diese Seiten zuerst und genauer – auch als Bild."}</span>
    </div>
    <details className="reextraction-advanced" open={advanced || state.reread_suggested}>
      <summary>Erweitert</summary>
      <label className="md-check"><input type="checkbox" checked={reread} onChange={(event) => setReread(event.target.checked)} /> Dokument neu lesen (Texterkennung)</label>
      {state.reread_suggested ? <p className="field-hint">Empfohlen: Das Dokument wurde bisher ohne Texterkennung gelesen.</p> : null}
      <label className="field">
        <span className="field-label">Modell</span>
        <select value={model} onChange={(event) => setModel(event.target.value)} disabled={models === null}>
          {models === null ? <option value="">Wird geladen…</option> : null}
          {models?.map((item) => <option key={item.model_id} value={item.model_id}>{item.label}{item.parameter_size ? ` · ${item.parameter_size}` : ""}{item.vision ? " · liest Bilder" : ""}{item.current ? " (aktuell)" : ""}</option>)}
        </select>
      </label>
      <p className="field-hint">Ein anderes installiertes Modell gilt nur für diese Auswertung.</p>
    </details>
    <p className="field-hint">Dauert je nach Umfang einige Minuten. Sie können währenddessen weiterarbeiten.</p>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
  </Dialog>;
}
