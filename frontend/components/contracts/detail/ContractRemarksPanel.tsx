"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { addContractRemark, listContractRemarks, type ContractRemark } from "@/lib/domain-api/register";

const timestamp = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });

export default function ContractRemarksPanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [items, setItems] = useState<ContractRemark[] | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listContractRemarks(orgSlug, contractId)
      .then((data) => { if (!cancelled) setItems(data.items); })
      .catch(() => { if (!cancelled) { setItems([]); setError("Bemerkungen konnten nicht geladen werden."); } });
    return () => { cancelled = true; };
  }, [contractId, orgSlug]);

  async function submit() {
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const data = await addContractRemark(orgSlug, contractId, body);
      setItems(data.items);
      setBody("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bemerkung konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="cw-section" aria-labelledby="rg-remarks-heading">
    <div className="cw-section-head"><div><h2 id="rg-remarks-heading">Bemerkungen</h2><p>Chronologisches Journal. Einträge können nicht nachträglich geändert werden.</p></div></div>
    {editable ? <form className="rg-remark-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <label htmlFor="rg-remark-body">Neue Bemerkung</label>
      <textarea id="rg-remark-body" rows={3} maxLength={10000} value={body} onChange={(event) => setBody(event.target.value)} />
      <div className="rg-actions"><button type="submit" className="btn btn-primary" disabled={busy || !body.trim()}>{busy ? "Wird gespeichert…" : "Bemerkung hinzufügen"}</button></div>
    </form> : null}
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {items === null ? <p role="status">Bemerkungen werden geladen…</p> : items.length === 0 ? <p className="cw-muted">Noch keine Bemerkungen.</p> : <ol className="rg-remarks">
      {items.map((item) => <li key={item.id}>
        <div className="rg-remark-meta"><strong>{item.author_name ?? "Unbekannt"}</strong><time dateTime={item.created_at ?? undefined}>{item.created_at ? timestamp.format(new Date(item.created_at)) : ""}</time></div>
        <p>{item.body}</p>
      </li>)}
    </ol>}
  </section>;
}
