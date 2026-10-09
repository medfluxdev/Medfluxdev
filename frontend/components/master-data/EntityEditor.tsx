"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { useSaveShortcut, useUnsavedChanges } from "@/components/ui/useFormGuards";
import EntityForm, { missingRequired } from "./EntityForm";
import EntityHistory from "./EntityHistory";
import type { EntityDefinition, FormValues } from "./types";

interface Props<T, C> {
  definition: EntityDefinition<T, C>;
  context: C;
  organizationSlug: string;
  row: T | null;
  preset?: FormValues;
  canEdit: boolean;
  editorsHint?: string;
  canSeeHistory: boolean;
  /** undefined = wird geladen/unbekannt, null = fuer diese Art nicht erfasst. */
  usageCount?: number | null;
  registerHref?: string | null;
  onSaved: (result: { id: string; created: boolean; label: string }) => void;
  onCancel: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

// Anlegen/Bearbeiten eines Eintrags: Formular, Verwendung, Aktiv-Status, Verlauf.
export default function EntityEditor<T, C>({
  definition, context, organizationSlug, row, preset, canEdit, editorsHint, canSeeHistory,
  usageCount, registerHref, onSaved, onCancel, onDirtyChange,
}: Props<T, C>) {
  const initial = useMemo(
    () => (row ? definition.toForm(row, context) : definition.emptyForm(context, preset)),
    // Nur beim Oeffnen eines anderen Eintrags neu aufsetzen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [row],
  );
  const [values, setValues] = useState<FormValues>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [similar, setSimilar] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    setValues(initial);
    setErrors({});
    setMessage(null);
    setSimilar([]);
    setConfirmDeactivate(false);
  }, [initial]);

  const dirty = JSON.stringify(values) !== JSON.stringify(initial);
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useUnsavedChanges(dirty);
  useSaveShortcut(canEdit && dirty && !saving, () => void save(false));

  const fields = definition.fields(context, values, row);
  const editing = row !== null;
  const active = row ? definition.active(row) : true;

  function change(key: string, value: string | boolean | string[]) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  async function save(force: boolean) {
    if (!canEdit || saving) return;
    const missing = missingRequired(fields, values, editing);
    setErrors(missing);
    if (Object.keys(missing).length > 0) {
      setMessage("Bitte die markierten Pflichtfelder ausfüllen.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      if (row) {
        await definition.update(organizationSlug, row, values);
        onSaved({ id: definition.id(row), created: false, label: definition.label(row) });
      } else {
        const created = await definition.create(organizationSlug, values, { force });
        onSaved({ id: created.id, created: true, label: definition.formLabel(values) || definition.singular });
      }
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 409 && !row && !force && definition.findSimilar) {
        const found = await definition.findSimilar(organizationSlug, values).catch(() => [] as string[]);
        setSimilar(found);
      }
      setMessage(errorText(error, "Speichern fehlgeschlagen. Bitte erneut versuchen."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive() {
    if (!row) return;
    if (active && usageCount && !confirmDeactivate) {
      setConfirmDeactivate(true);
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await definition.setActive(organizationSlug, row, !active);
      onSaved({ id: definition.id(row), created: false, label: definition.label(row) });
    } catch (error) {
      setMessage(errorText(error, "Der Status konnte nicht geändert werden."));
      setConfirmDeactivate(false);
    } finally {
      setSaving(false);
    }
  }

  return <form
    className="md-editor"
    noValidate
    aria-label={editing ? `${definition.singular} bearbeiten` : `${definition.singular} anlegen`}
    onSubmit={(event) => { event.preventDefault(); void save(false); }}
  >
    {!canEdit ? <InlineAlert tone="info">Nur ansehen: {definition.plural} pflegt {editorsHint ?? "die Administration"}.</InlineAlert> : null}
    {editing && !active ? <InlineAlert tone="warning">Deaktiviert: steht bei neuen Verträgen nicht mehr zur Auswahl.</InlineAlert> : null}
    {message ? <InlineAlert tone="critical" role="alert">{message}</InlineAlert> : null}
    {similar.length > 0 ? <InlineAlert
      tone="warning"
      role="status"
      action={<Button size="sm" onClick={() => void save(true)} disabled={saving}>Trotzdem anlegen</Button>}
    >
      Ähnliche Einträge gibt es bereits: {similar.join(", ")}. Bitte prüfen, ob es derselbe ist.
    </InlineAlert> : null}

    <EntityForm fields={fields} values={values} onChange={change} readOnly={!canEdit} editing={editing} errors={errors} />

    {editing ? <section className="md-usage" aria-label="Verwendung">
      <h3>Verwendung</h3>
      {usageCount === undefined ? <p className="state-loading">Wird ermittelt…</p>
        : usageCount === null ? <p className="field-hint">Für diese Liste wird die Verwendung in Verträgen nicht erfasst.</p>
          : <p>
            {usageCount === 0 ? "In keinem Vertrag verwendet." : `In ${usageCount} ${usageCount === 1 ? "Vertrag" : "Verträgen"} verwendet.`}
            {usageCount > 0 && registerHref ? <> <Link href={registerHref}>In der Vertragsliste anzeigen</Link></> : null}
          </p>}
    </section> : null}

    {editing && canEdit ? <section className="md-status" aria-label="Status">
      <h3>Status</h3>
      {confirmDeactivate ? <InlineAlert
        tone="warning"
        role="alert"
        action={<span className="btn-group">
          <Button size="sm" variant="danger" onClick={() => void toggleActive()} disabled={saving}>Trotzdem deaktivieren</Button>
          <Button size="sm" onClick={() => setConfirmDeactivate(false)}>Abbrechen</Button>
        </span>}
      >
        Wird in {usageCount} {usageCount === 1 ? "Vertrag" : "Verträgen"} verwendet. Dort bleibt der Eintrag erhalten, er ist aber nicht mehr neu auswählbar.
      </InlineAlert> : <p className="md-status-row">
        <span>{active ? "Aktiv – steht zur Auswahl." : "Deaktiviert."}</span>
        <Button size="sm" onClick={() => void toggleActive()} disabled={saving}>{active ? "Deaktivieren" : "Wieder aktivieren"}</Button>
      </p>}
    </section> : null}

    {editing && canSeeHistory && row ? <details className="md-history-box" onToggle={(event) => setHistoryOpen((event.target as HTMLDetailsElement).open)}>
      <summary>Änderungsverlauf</summary>
      {historyOpen ? <EntityHistory organizationSlug={organizationSlug} objectType={definition.objectType} objectId={definition.id(row)} /> : null}
    </details> : null}

    <div className="form-actions md-editor-actions">
      <Button onClick={onCancel}>{canEdit ? "Abbrechen" : "Schließen"}</Button>
      {canEdit ? <Button type="submit" variant="primary" loading={saving} loadingLabel="Wird gespeichert…" disabled={editing && !dirty}>
        {editing ? "Speichern" : "Anlegen"}
      </Button> : null}
    </div>
    {canEdit && dirty ? <p className="field-hint md-shortcut">Speichern mit Strg+S</p> : null}
  </form>;
}
