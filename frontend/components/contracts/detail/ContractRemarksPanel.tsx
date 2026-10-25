"use client";

import CollapsibleSection from "@/components/ui/CollapsibleSection";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ActionMenu, { type ActionMenuItem } from "@/components/ui/ActionMenu";
import { useToast } from "@/components/ui/Toast";
import { addContractRemark, deleteContractRemark, editContractRemark, listContractRemarks, type ContractRemark } from "@/lib/domain-api/register";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });
const dayFormat = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const when = (iso: string | null | undefined) => (iso ? timestamp.format(new Date(iso)) : "");
const dayKey = (iso: string | null | undefined) => (iso ? dayFormat.format(new Date(iso)) : "Ohne Datum");
const clock = (iso: string | null | undefined) => (iso ? timeFormat.format(new Date(iso)) : "");
const initial = (name: string | null | undefined) => (name ?? "?").trim().charAt(0).toUpperCase() || "?";

const icon = (body: JSX.Element, className = "rg-remark-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const PEN = icon(<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" />);
const HISTORY = icon(<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" />);
const PLUS = icon(<path d="M12 5v14M5 12h14" />, "rg-remark-plus-icon");
const SEARCH = icon(<path d="M11 4a7 7 0 1 1 0 14a7 7 0 1 1 0-14zM20 20l-4-4" />);
const SORT = icon(<path d="M4 6h9M4 12h6M4 18h3M17 20V5M14 8l3-3 3 3" />);
const NOTEPAD = <svg viewBox="0 0 24 24" focusable="false"><path d="M6 4h12a1 1 0 0 1 1 1v11l-4 4H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM15 20v-4h4M8.5 9h7M8.5 12.5h5" /></svg>;
const INFO = icon(<path d="M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 11v6M12 7.5v.5" />);
const COPY = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 9h10v12H9zM5 15V3h10" /></svg>;
const TRASH = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>;
const HISTORY_MENU = <svg className="action-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" /></svg>;

type SortOrder = "newest" | "oldest";

/**
 * Notizen je Vertrag (`contract_remark`), nach Tagen gruppiert, durchsuchbar und sortierbar. Wer Notizen schreiben
 * darf, darf jede Notiz bearbeiten; jede frühere Fassung bleibt mit Verfasser und Zeit erhalten (`contract_remark_revision`).
 */
export default function ContractRemarksPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const toast = useToast();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [items, setItems] = useState<ContractRemark[] | null>(null);
  const [composing, setComposing] = useState(false);
  const [body, setBody] = useState("");
  const [editing, setEditing] = useState<{ id: string; body: string; version?: string } | null>(null);
  const [historyOpen, setHistoryOpen] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [order, setOrder] = useState<SortOrder>("newest");
  const [busy, setBusy] = useState(false);
  // Notiz, deren Löschen gerade bestätigt wird.
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    listContractRemarks(orgSlug, contractId)
      .then((data) => { if (!cancelled) setItems(data.items); })
      .catch(() => { if (!cancelled) { setItems([]); setError("Notizen konnten nicht geladen werden."); } });
    return () => { cancelled = true; };
  }, [contractId, orgSlug]);

  useEffect(() => { if (composing) composerRef.current?.focus(); }, [composing]);

  async function submit() {
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const data = await addContractRemark(orgSlug, contractId, body);
      setItems(data.items);
      setBody("");
      setComposing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Notiz konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit() {
    if (!editing || !editing.body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const data = await editContractRemark(orgSlug, contractId, editing.id, editing.body, editing.version);
      setItems(data.items);
      setEditing(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Änderung konnte nicht gespeichert werden.");
      // Bei einem Konflikt den aktuellen Stand zeigen; der eigene Text bleibt im Feld.
      listContractRemarks(orgSlug, contractId).then((data) => setItems(data.items)).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: ContractRemark) {
    setBusy(true);
    setError(null);
    try {
      const data = await deleteContractRemark(orgSlug, contractId, item.id, item.version);
      setItems(data.items);
      setConfirmDelete(null);
      toast("Notiz gelöscht.", "success");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Notiz konnte nicht gelöscht werden.");
      listContractRemarks(orgSlug, contractId).then((data) => setItems(data.items)).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  function toggleHistory(id: string) {
    setHistoryOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function cancelCompose() {
    setBody("");
    setComposing(false);
  }

  // Suche in Text und Verfasser; Sortierung nach Zeitpunkt; danach je Kalendertag gruppiert.
  const groups = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    const found = (items ?? []).filter((item) => !needle || item.body.toLocaleLowerCase("de-DE").includes(needle) || (item.author_name ?? "").toLocaleLowerCase("de-DE").includes(needle));
    const sorted = [...found].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? "") * (order === "newest" ? -1 : 1));
    const byDay: { day: string; items: ContractRemark[] }[] = [];
    for (const item of sorted) {
      const day = dayKey(item.created_at);
      const last = byDay[byDay.length - 1];
      if (last && last.day === day) last.items.push(item); else byDay.push({ day, items: [item] });
    }
    return byDay;
  }, [items, query, order]);
  const total = items?.length ?? 0;
  const shown = groups.reduce((sum, group) => sum + group.items.length, 0);

  function menuItems(item: ContractRemark): ActionMenuItem[] {
    const revisions = item.revisions ?? [];
    const entries: ActionMenuItem[] = [{
      label: "Text kopieren", icon: COPY,
      onSelect: () => { void navigator.clipboard?.writeText(item.body).then(() => toast("Notiz kopiert.", "success")).catch(() => undefined); },
    }];
    if (revisions.length) entries.push({ label: historyOpen.has(item.id) ? "Frühere Versionen ausblenden" : "Frühere Versionen anzeigen", icon: HISTORY_MENU, onSelect: () => toggleHistory(item.id) });
    if (editable) entries.push("separator", { label: "Notiz löschen", icon: TRASH, danger: true, onSelect: () => { setEditing(null); setConfirmDelete(item.id); } });
    return entries;
  }

  return <CollapsibleSection id="rg-remarks" className="rg-notes" title="Notizen" tone="accent" icon={NOTEPAD}
    description={<>Absprachen und Hinweise zum Vertrag.{total ? <span className="count-chip" aria-label={`${total} Notizen`}>{total}</span> : null}</>}
    actions={total ? <div className="rg-notes-tools">
        <label className="rg-notes-search">{SEARCH}<span className="visually-hidden">Notizen durchsuchen</span>
          <input type="search" placeholder="Notizen durchsuchen" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <label className="rg-notes-sort">{SORT}<span className="visually-hidden">Sortierung</span>
          <select value={order} onChange={(event) => setOrder(event.target.value as SortOrder)}>
            <option value="newest">Neueste zuerst</option>
            <option value="oldest">Älteste zuerst</option>
          </select>
        </label>
      </div> : undefined}>

    {editable ? (composing
      ? <form className="rg-notes-composer" aria-label="Neue Notiz" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <div className="rg-notes-who">
          <span className="rg-note-avatar" aria-hidden="true">{initial(account?.display_name)}</span>
          <span><strong>{account?.display_name ?? "Sie"}</strong><small>Neue Notiz</small></span>
        </div>
        <div className="rg-notes-write">
          <label className="visually-hidden" htmlFor="rg-remark-body">Neue Notiz</label>
          <textarea ref={composerRef} id="rg-remark-body" rows={3} maxLength={10000} value={body} placeholder="Was möchten Sie zu diesem Vertrag festhalten?"
            onChange={(event) => setBody(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void submit(); }
              if (event.key === "Escape") { event.preventDefault(); cancelCompose(); }
            }} />
          <div className="rg-notes-write-foot">
            <span>Nach dem Speichern im Notizverlauf sichtbar · <kbd>Strg</kbd> + <kbd>Enter</kbd> speichert</span>
            <span className="rg-actions">
              <button type="button" className="btn" onClick={cancelCompose}>Abbrechen</button>
              <button type="submit" className="btn btn-primary" disabled={busy || !body.trim()}>{busy && !editing ? "Wird gespeichert…" : "Notiz speichern"}</button>
            </span>
          </div>
        </div>
      </form>
      : <button type="button" className="rg-notes-new" onClick={() => setComposing(true)}><span className="rg-notes-new-plus" aria-hidden="true">{PLUS}</span>Neue Notiz schreiben …</button>) : null}

    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {items === null ? <p role="status">Notizen werden geladen…</p>
      : total === 0 ? <p className="cw-muted rg-notes-empty">Noch keine Notizen.</p>
        : shown === 0 ? <p className="cw-muted rg-notes-empty">Keine Notiz enthält „{query.trim()}“.</p>
          : groups.map((group) => <div key={group.day} className="rg-notes-day">
            <h3>{group.day}<span>{group.items.length} {group.items.length === 1 ? "Eintrag" : "Einträge"}</span></h3>
            <ol className="rg-remarks">
              {group.items.map((item) => {
                const revisions = item.revisions ?? [];
                const isEditing = editing?.id === item.id;
                const showHistory = historyOpen.has(item.id);
                return <li key={item.id} className="rg-note">
                  <span className="rg-note-avatar" aria-hidden="true">{initial(item.author_name)}</span>
                  <div className="rg-note-main">
                    <div className="rg-remark-meta">
                      <span className="rg-note-who">
                        <strong>{item.author_name ?? "Unbekannt"}</strong>
                        <time dateTime={item.created_at ?? undefined} title={when(item.created_at)}>{clock(item.created_at)}</time>
                        {item.edited_at ? <span className="rg-note-edited" title={`Bearbeitet von ${item.edited_by_name ?? "Unbekannt"} · ${when(item.edited_at)}`}>Bearbeitet<span className="visually-hidden"> von {item.edited_by_name ?? "Unbekannt"} · {when(item.edited_at)}</span></span> : null}
                      </span>
                      <span className="rg-remark-meta-end">
                        {editable && !isEditing ? <button type="button" className="rg-link" disabled={busy} aria-label={`Notiz von ${item.author_name ?? "Unbekannt"} vom ${when(item.created_at)} bearbeiten`} onClick={() => setEditing({ id: item.id, body: item.body, version: item.version })}>{PEN}Bearbeiten</button> : null}
                        <ActionMenu label={`Weitere Aktionen: Notiz vom ${when(item.created_at)}`} items={menuItems(item)} />
                      </span>
                    </div>
                    {isEditing && editing ? <form className="rg-remark-form rg-remark-edit" aria-label="Notiz bearbeiten" onSubmit={(event) => { event.preventDefault(); void saveEdit(); }}>
                      <label className="visually-hidden" htmlFor={`rg-remark-edit-${item.id}`}>Notiz</label>
                      <textarea id={`rg-remark-edit-${item.id}`} rows={3} maxLength={10000} value={editing.body} autoFocus
                        onChange={(event) => setEditing((current) => current && ({ ...current, body: event.target.value }))}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void saveEdit(); }
                          if (event.key === "Escape") { event.preventDefault(); setEditing(null); }
                        }} />
                      <div className="rg-actions">
                        <button type="button" className="btn" onClick={() => setEditing(null)}>Abbrechen</button>
                        <button type="submit" className="btn btn-primary" disabled={busy || !editing.body.trim() || editing.body.trim() === item.body}>{busy ? "Wird gespeichert…" : "Änderung speichern"}</button>
                      </div>
                    </form> : <p className="rg-note-body">{item.body}</p>}
                    {confirmDelete === item.id ? <div className="rg-note-confirm" role="group" aria-label="Löschen bestätigen">
                      <span>Diese Notiz löschen? Sie verschwindet aus der Liste; im Verlauf bleibt festgehalten, wer sie gelöscht hat.</span>
                      <span className="rg-actions">
                        <button type="button" className="btn" onClick={() => setConfirmDelete(null)}>Abbrechen</button>
                        <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void remove(item)}>{busy ? "Wird gelöscht…" : "Notiz löschen"}</button>
                      </span>
                    </div> : null}
                    {revisions.length ? <button type="button" className="rg-link rg-note-versions" aria-expanded={showHistory} aria-controls={`rg-remark-history-${item.id}`} onClick={() => toggleHistory(item.id)}>
                      {HISTORY}{showHistory ? "Frühere Versionen ausblenden" : `${revisions.length} ${revisions.length === 1 ? "frühere Version" : "frühere Versionen"}`}
                    </button> : null}
                    {showHistory && revisions.length ? <ol className="rg-remark-history" id={`rg-remark-history-${item.id}`} aria-label="Frühere Fassungen, neueste zuerst">
                      {revisions.map((revision, index) => <li key={`${revision.written_at}-${index}`}>
                        <div className="rg-remark-meta"><span>{revision.author_name ?? "Unbekannt"}</span><time dateTime={revision.written_at ?? undefined}>{when(revision.written_at)}</time></div>
                        <p>{revision.body}</p>
                      </li>)}
                    </ol> : null}
                  </div>
                </li>;
              })}
            </ol>
          </div>)}
    {total ? <p className="rg-notes-foot">{INFO}Frühere Versionen öffnen sich direkt unter dem jeweiligen Eintrag.</p> : null}
  </CollapsibleSection>;
}
