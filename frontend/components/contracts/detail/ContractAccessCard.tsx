"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ChipPicker from "@/components/ui/ChipPicker";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import InfoTip from "@/components/ui/InfoTip";
import Signal, { SignalIcon } from "@/components/ui/Signal";
import { PersonTag } from "@/components/ui/TagChip";
import { listContractDocuments } from "@/lib/domain-api/contractDocuments";
import type { AssigneeDto } from "@/lib/domain-api/ownership";
import type { ContractRegister } from "@/lib/domain-api/register";
import { contractHref } from "@/lib/fix-targets";

const DP_HELP = "Ja, wenn der Vertragspartner personenbezogene Daten verarbeitet (Auftragsverarbeitung nach Art. 28 DSGVO).";
const VISIBLE_FOR = "Administratoren, verantwortliche Person, Erinnerungsempfänger";

export const SHIELD_ICON = <svg viewBox="0 0 24 24" focusable="false"><path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" /></svg>;
const LOCK = <svg className="ac-lock" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>;

export type AccessChanges = {
  confidentiality?: { is_confidential: boolean; grant_account_ids: string[] };
  dataProtection?: boolean | null;
};

/**
 * Zugriff & Datenschutz: Vertraulichkeit (nur Administration ändert sie) und „Datenschutzrelevant (AVV erforderlich)“
 * (Registerfeld, KI-Erkennung als Vorschlag). Ohne hinterlegten AVV erscheint ein Hinweis mit Link zum Hochladen.
 */
export default function ContractAccessCard({ register, contractId, orgSlug, assignees, isAdmin, canEditData, busy, onSave, onConfirm, editRequest }: {
  register: ContractRegister;
  contractId: string;
  orgSlug: string;
  assignees: AssigneeDto[];
  /** Vertraulichkeit ändern (wie bisher: nur Administration). */
  isAdmin: boolean;
  /** Datenschutzrelevant ändern (Vertragsdaten-Recht). */
  canEditData: boolean;
  busy: boolean;
  onSave: (changes: AccessChanges) => Promise<boolean>;
  /** KI-Wert „Datenschutzrelevant“ bestätigen. */
  onConfirm?: () => void;
  editRequest?: number;
}) {
  const conf = register.confidentiality;
  const dp = register.fields.data_protection_relevant;
  const dpValue = dp?.value == null ? null : Boolean(dp.value);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<{ is_confidential: boolean; grants: string[]; dp: boolean | null }>({ is_confidential: false, grants: [], dp: null });
  const [hasAvv, setHasAvv] = useState<boolean | null>(null);
  const firstControl = useRef<HTMLDivElement>(null);
  const canEdit = isAdmin || canEditData;

  useEffect(() => {
    if (dpValue !== true) { setHasAvv(null); return; }
    let cancelled = false;
    listContractDocuments(orgSlug, contractId)
      .then((data) => { if (!cancelled) setHasAvv((data.items ?? []).some((item) => item.attachment_type === "avv")); })
      .catch(() => { if (!cancelled) setHasAvv(null); });
    return () => { cancelled = true; };
  }, [contractId, orgSlug, dpValue]);

  function open() {
    setDraft({ is_confidential: conf.is_confidential, grants: conf.grants.map((item) => item.account_id), dp: dpValue });
    setEditing(true);
  }
  useEffect(() => { if (editRequest && canEdit) open(); }, [editRequest]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (editing) firstControl.current?.querySelector<HTMLElement>("input:not(:disabled), button")?.focus();
  }, [editing]);

  async function save() {
    const changes: AccessChanges = {};
    const grantsBefore = conf.grants.map((item) => item.account_id).sort().join();
    if (isAdmin && (draft.is_confidential !== conf.is_confidential || [...draft.grants].sort().join() !== grantsBefore)) {
      changes.confidentiality = { is_confidential: draft.is_confidential, grant_account_ids: draft.grants };
    }
    if (canEditData && draft.dp !== dpValue) changes.dataProtection = draft.dp;
    if (!changes.confidentiality && changes.dataProtection === undefined) { setEditing(false); return; }
    if (await onSave(changes)) setEditing(false);
  }

  const aiOrigin = dp?.origin === "ai" || dp?.origin === "ai_confirmed";
  const quote = aiOrigin && dp?.source_field?.startsWith("Dokumenttext") ? dp.source_field : null;
  const badge = dp?.origin === "ai"
    ? <span className="rg-origin rg-origin-ai"><SignalIcon tone="ai" />KI · Vorschlag</span>
    : dp?.origin === "ai_confirmed" ? <span className="rg-origin rg-origin-ai_confirmed"><SignalIcon tone="done" />KI · bestätigt</span> : null;
  const confidentialText = conf.effective ? (conf.type_confidential && !conf.is_confidential ? "Ja (über Vertragstyp)" : "Ja") : "Nein";
  const grantName = (id: string) => assignees.find((item) => item.id === id)?.display_name ?? conf.grants.find((item) => item.account_id === id)?.display_name ?? "Unbekannte Person";

  const actions = editing || !canEdit ? null
    : <button type="button" className="btn btn-sm" disabled={busy} onClick={open} aria-label="Zugriff & Datenschutz bearbeiten" data-shortcut="edit" aria-keyshortcuts="E" title="Bearbeiten (E)">Bearbeiten</button>;

  return <CollapsibleSection
    id="rg-access"
    title="Zugriff & Datenschutz"
    description="Wer den Vertrag sehen darf und ob personenbezogene Daten betroffen sind"
    summary={<><span>Vertraulich: <b>{confidentialText}</b></span><span className="sep" aria-hidden="true">·</span><span>Datenschutzrelevant: <b>{dpValue == null ? "nicht erfasst" : dpValue ? "Ja" : "Nein"}</b></span>{dpValue && hasAvv === false ? <Signal tone="warning" size="sm">Kein AVV hinterlegt</Signal> : null}</>}
    icon={SHIELD_ICON}
    iconClassName="section-tile--accent"
    actions={actions}
    forceOpen={editing}
  >
    {editing ? <form className="ac-edit" aria-label="Zugriff & Datenschutz bearbeiten" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <div ref={firstControl} className="ac-edit-fields">
        {isAdmin ? <>
          <div className="ac-f">
            <label className="rg-check ac-check">
              <input type="checkbox" checked={draft.is_confidential || conf.type_confidential} disabled={conf.type_confidential} onChange={(event) => setDraft((form) => ({ ...form, is_confidential: event.target.checked }))} />
              <span>Vertrag als vertraulich kennzeichnen<span className="ac-note">{conf.type_confidential ? "Der Vertragstyp ist bereits vertraulich. Der Vertrag bleibt deshalb auch ohne Kennzeichen geschützt." : `Sichtbar bleiben: ${VISIBLE_FOR}.`}</span></span>
            </label>
          </div>
          <div className="ac-f">
            <span className="ac-label" id="ac-grants-label">Zusätzlich freigeben für</span>
            <ChipPicker
              labelId="ac-grants-label"
              items={draft.grants.map((id) => ({ id, label: grantName(id) }))}
              onRemove={(id) => setDraft((form) => ({ ...form, grants: form.grants.filter((value) => value !== id) }))}
              groups={[{ label: "Benutzer der Organisation", options: assignees.filter((item) => !draft.grants.includes(item.id)).map((item) => ({ value: item.id, label: item.display_name })) }]}
              onAdd={(id) => setDraft((form) => form.grants.includes(id) ? form : ({ ...form, grants: [...form.grants, id] }))}
              addLabel="Person"
              addAriaLabel="Person freigeben"
              disabledHint={assignees.length === 0 ? "Keine Benutzer verfügbar." : null}
            />
          </div>
        </> : null}
        {canEditData ? <div className="ac-f">
          <span className="ac-label" id="ac-dp-label">Datenschutzrelevant (AVV erforderlich) <InfoTip label="Erläuterung zu Datenschutzrelevant" text={DP_HELP} /></span>
          <div className="ac-seg" role="group" aria-labelledby="ac-dp-label">
            <button type="button" aria-pressed={draft.dp === true} onClick={() => setDraft((form) => ({ ...form, dp: true }))}>Ja</button>
            <button type="button" aria-pressed={draft.dp === false} onClick={() => setDraft((form) => ({ ...form, dp: false }))}>Nein</button>
          </div>
          {dp?.origin === "ai" ? <span className="ac-note">Vorschlag der KI: {dpValue ? "Ja" : "Nein"}{quote ? ` – ${quote}.` : "."}</span> : null}
        </div> : null}
      </div>
      <div className="ac-acts"><button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Wird gespeichert…" : "Speichern"}</button></div>
    </form> : <dl className="ac-rows">
      <div className="ac-row">
        <dt>Vertraulich</dt>
        <dd>
          <span className="ac-val">{conf.effective ? LOCK : null}{confidentialText}</span>
          {conf.effective ? <>
            <span className="ac-sub">Sichtbar für: {VISIBLE_FOR}</span>
            {conf.grants.length ? <><span className="ac-sub">Zusätzlich freigegeben für</span><span className="ac-people">{conf.grants.map((item) => <PersonTag key={item.account_id} name={item.display_name} />)}</span></> : null}
          </> : null}
        </dd>
      </div>
      <div className="ac-row" id="rg-field-data_protection_relevant">
        <dt>Datenschutzrelevant (AVV erforderlich) <InfoTip label="Erläuterung zu Datenschutzrelevant" text={DP_HELP} /></dt>
        <dd>
          <span className="ac-val">{dpValue == null ? <span className="ac-none">Nicht erfasst</span> : dpValue ? "Ja" : "Nein"}{badge}{dp?.origin === "ai" && canEditData && onConfirm ? <button type="button" className="rg-link" disabled={busy} onClick={onConfirm}>Bestätigen</button> : null}</span>
          {quote ? <span className="ac-quote">{quote}</span> : null}
          {dpValue && hasAvv === false ? <span className="ac-hint" role="note">
            <SignalIcon tone="warning" />Kein AVV hinterlegt
            {canEditData ? <Link className="rg-link" href={`${contractHref(contractId, { tab: "documents", subtab: "attachments" })}&dokumentart=avv`}>AVV hochladen</Link> : null}
          </span> : null}
        </dd>
      </div>
    </dl>}
  </CollapsibleSection>;
}
