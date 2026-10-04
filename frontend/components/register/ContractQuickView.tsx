"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Drawer from "@/components/ui/Drawer";
import Skeleton from "@/components/ui/Skeleton";
import { BUSINESS_STATUS_LABEL, TERM_MODEL_LABEL, getContractRegister, type ContractRegister, type TermModel } from "@/lib/domain-api/register";
import { formatDate } from "@/lib/format";

// Schnellansicht aus der Vertragsliste: Kernfakten ohne die Liste zu verlassen.
export default function ContractQuickView({ organizationSlug, contractId, onClose }: { organizationSlug: string; contractId: string | null; onClose: () => void }) {
  const [data, setData] = useState<ContractRegister | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!contractId) return;
    let cancelled = false;
    setData(null);
    setError(null);
    getContractRegister(organizationSlug, contractId)
      .then((result) => { if (!cancelled) setData(result); })
      .catch(() => { if (!cancelled) setError("Der Vertrag konnte nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [contractId, organizationSlug]);

  const field = (key: string) => data?.fields[key]?.display ?? (data?.fields[key]?.value == null || data?.fields[key]?.value === "" ? "–" : String(data?.fields[key]?.value));

  return (
    <Drawer
      open={Boolean(contractId)}
      title={data ? `Vertrag ${data.register_number ?? ""}`.trim() : "Vertrag"}
      onClose={onClose}
      actions={contractId ? <Link href={`/contracts/${contractId}`} className="btn btn-primary btn-sm">Öffnen</Link> : null}
    >
      {error ? <p role="alert" className="field-error">{error}</p> : null}
      {!data && !error ? <Skeleton lines={6} label="Vertrag wird geladen…" /> : null}
      {data ? (
        <div className="stack-4">
          <div>
            <h3>{String(data.fields.short_description?.value ?? "Ohne Kurzbeschreibung")}</h3>
            <p className="field-hint">{BUSINESS_STATUS_LABEL[data.business_status]} · {field("partner_id")}</p>
          </div>
          <dl className="quick-facts">
            <div><dt>Vertragsart</dt><dd>{data.fields.term_model?.value ? TERM_MODEL_LABEL[data.fields.term_model.value as TermModel] : "–"}</dd></div>
            <div><dt>Kündbar bis</dt><dd>{formatDate(data.terms.cancel_by)}</dd></div>
            <div><dt>Mögliches Ende</dt><dd>{formatDate(data.terms.actual_end ?? data.terms.possible_end)}</dd></div>
            <div><dt>Erinnerung am</dt><dd>{formatDate(data.terms.reminder_date)}</dd></div>
            <div><dt>Erinnerung an</dt><dd>{field("reminder_recipient_account_id")}</dd></div>
            <div><dt>Vertragstyp</dt><dd>{field("contract_type_id")}</dd></div>
            <div><dt>Löschen ab</dt><dd>{formatDate(data.retention.deletion_from)}</dd></div>
            <div><dt>Vertraulich</dt><dd>{data.confidentiality.effective ? "Ja" : "Nein"}</dd></div>
          </dl>
          {data.review_pending ? <p className="alert alert--warning">KI-Werte sind noch nicht vollständig geprüft.</p> : null}
          <div className="btn-group">
            <Link href={`/contracts/${contractId}?tab=register`} className="btn btn-sm">Stammdaten</Link>
            <Link href={`/contracts/${contractId}?tab=deadlines`} className="btn btn-sm">Fristen & Entscheidung</Link>
            <Link href={`/contracts/${contractId}?tab=finance`} className="btn btn-sm">Finanzen</Link>
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
