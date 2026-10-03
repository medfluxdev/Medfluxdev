"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import {
  addWorkItemComment,
  getWorkItemCollaboration,
  updateWorkItemCollaboration,
  type WorkItemCollaboration,
} from "@/lib/domain-api/workQueueCollaboration";
import { listUsers } from "@/lib/domain-api/users";

interface Props {
  workItemId: string;
  onClose: () => void;
}

type Assignee = { id: string; display_name?: string; email?: string; is_active?: boolean };

const EMPTY: WorkItemCollaboration = {
  assignee_account_id: null,
  owner_note: null,
  remind_at: null,
  escalation_level: 0,
  comments: [],
};

export default function WorkItemCollaborationPanel({ workItemId, onClose }: Props) {
  const { organizationSlug } = useAuth();
  const contextVersion = useRef(0);
  const savingRef = useRef(false);
  const [state, setState] = useState<WorkItemCollaboration>(EMPTY);
  const [users, setUsers] = useState<Assignee[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  useEffect(() => {
    let active = true;
    contextVersion.current += 1;
    savingRef.current = false;
    setState(EMPTY);
    setUsers([]);
    setComment("");
    setError(null);
    setSaving(false);
    if (!organizationSlug) {
      setLoading(false);
      return () => { active = false; contextVersion.current += 1; };
    }
    setLoading(true);
    Promise.all([
      getWorkItemCollaboration(organizationSlug, workItemId),
      listUsers(organizationSlug),
    ])
      .then(([collaboration, userResponse]) => {
        if (!active) return;
        setState({ ...EMPTY, ...collaboration, comments: collaboration.comments ?? [] });
        const raw = Array.isArray(userResponse) ? userResponse : (userResponse as { items?: Assignee[] }).items ?? [];
        setUsers(raw as Assignee[]);
      })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "Zusammenarbeit konnte nicht geladen werden."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; contextVersion.current += 1; };
  }, [organizationSlug, workItemId]);

  async function save() {
    if (!organizationSlug || savingRef.current || loading) return;
    const version = contextVersion.current;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateWorkItemCollaboration(organizationSlug, workItemId, {
        assignee_account_id: state.assignee_account_id,
        owner_note: state.owner_note,
        remind_at: state.remind_at,
        escalation_level: state.escalation_level,
      });
      if (version === contextVersion.current) setState((current) => ({ ...current, ...updated }));
    } catch (err) {
      if (version === contextVersion.current) setError(err instanceof Error ? err.message : "Zusammenarbeit konnte nicht gespeichert werden.");
    } finally {
      if (version === contextVersion.current) { savingRef.current = false; setSaving(false); }
    }
  }

  async function submitComment(event: FormEvent) {
    event.preventDefault();
    if (!organizationSlug || !comment.trim() || savingRef.current || loading) return;
    const version = contextVersion.current;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const created = await addWorkItemComment(organizationSlug, workItemId, comment.trim());
      if (version === contextVersion.current) {
        setState((current) => ({ ...current, comments: [...(current.comments ?? []), created] }));
        setComment("");
      }
    } catch (err) {
      if (version === contextVersion.current) setError(err instanceof Error ? err.message : "Kommentar konnte nicht gespeichert werden.");
    } finally {
      if (version === contextVersion.current) { savingRef.current = false; setSaving(false); }
    }
  }

  return (
    <section className="panel work-collaboration-panel" aria-label="Aufgabe organisieren">
      <div className="panel-head"><div><h2>Aufgabe organisieren</h2><p className="muted">Zuständigkeit, Erinnerung, Eskalation und Kommentare.</p></div><Button size="sm" onClick={onClose}>Schließen</Button></div>
      {loading ? <LoadingState>Aufgabendetails werden geladen…</LoadingState> : null}
      {error ? <InlineAlert tone="warning" role="alert">{error}</InlineAlert> : null}
      {!loading ? <div className="form-grid">
        <label>Zuständig<select value={state.assignee_account_id ?? ""} onChange={(event) => setState((current) => ({ ...current, assignee_account_id: event.target.value || null }))}><option value="">Nicht zugewiesen</option>{users.filter((user) => user.is_active !== false).map((user) => <option key={user.id} value={user.id}>{user.display_name ?? user.email ?? user.id}</option>)}</select></label>
        <label>Erinnerung<input type="datetime-local" value={state.remind_at ? state.remind_at.slice(0, 16) : ""} onChange={(event) => setState((current) => ({ ...current, remind_at: event.target.value ? new Date(event.target.value).toISOString() : null }))} /></label>
        <label>Eskalation<select value={state.escalation_level} onChange={(event) => setState((current) => ({ ...current, escalation_level: Number(event.target.value) }))}>{[0,1,2,3,4,5].map((level) => <option key={level} value={level}>{level === 0 ? "Keine" : `Stufe ${level}`}</option>)}</select></label>
        <label className="form-field-wide">Interne Notiz<textarea rows={3} value={state.owner_note ?? ""} onChange={(event) => setState((current) => ({ ...current, owner_note: event.target.value || null }))} /></label>
        <div><Button variant="primary" disabled={saving} onClick={() => void save()}>Speichern</Button></div>
      </div> : null}
      {!loading ? <div className="work-comments"><h3>Kommentare</h3>{(state.comments ?? []).length === 0 ? <p className="muted">Noch keine Kommentare.</p> : <ul>{(state.comments ?? []).map((entry) => <li key={entry.id}><strong>{entry.display_name}</strong><p>{entry.body}</p>{entry.created_at ? <small>{new Date(entry.created_at).toLocaleString("de-DE")}</small> : null}</li>)}</ul>}<form onSubmit={submitComment}><label>Kommentar<textarea rows={2} value={comment} onChange={(event) => setComment(event.target.value)} /></label><Button type="submit" size="sm" disabled={saving || !comment.trim()}>Kommentar hinzufügen</Button></form></div> : null}
    </section>
  );
}
