"use client";

import Link from "next/link";
import StatusBadge from "@/components/ui/StatusBadge";
import type { ContractRegister } from "@/lib/domain-api/register";

// Auf einen Blick: was die KI aus dem Dokument übernommen hat und was davon noch zu prüfen ist.
export default function AiFillSummary({ register, contractId }: { register: ContractRegister; contractId: string }) {
  if (!register.has_ai_analysis) return null;
  const fields = Object.values(register.fields);
  const open = fields.filter((field) => field.origin === "ai");
  const confirmed = fields.filter((field) => field.origin === "ai_confirmed").length;
  const corrected = fields.filter((field) => field.origin === "ai_corrected").length;
  const proposals = fields.filter((field) => field.ai_proposed_value != null).length;
  const filled = open.length + confirmed + corrected;
  const parts = [
    open.length ? `${open.length} noch nicht bestätigt` : null,
    confirmed ? `${confirmed} bestätigt` : null,
    corrected ? `${corrected} korrigiert` : null,
    proposals ? `${proposals} neue Vorschläge` : null,
  ].filter(Boolean);

  return <section className="cw-section ai-fill" aria-labelledby="ai-fill-heading">
    <div className="ai-fill-row">
      <span className="ai-fill-icon" aria-hidden="true">✦</span>
      <div className="ai-fill-text">
        <h2 id="ai-fill-heading">{filled === 1 ? "KI hat 1 Angabe aus dem Dokument übernommen" : `KI hat ${filled} Angaben aus dem Dokument übernommen`}</h2>
        {parts.length ? <p>{parts.join(" · ")}</p> : null}
      </div>
      <StatusBadge label={register.review_pending ? "Prüfung offen" : "Geprüft"} tone={register.review_pending ? "review" : "success"} />
      {register.review_pending ? <Link className="btn btn-primary btn-sm" href={`/contracts/${contractId}?tab=documents&subtab=review`}>Jetzt prüfen</Link> : null}
    </div>
    {open.length > 0 ? <details className="ai-fill-details">
      <summary>Noch nicht bestätigte Angaben anzeigen</summary>
      <ul>{open.map((field) => <li key={field.label}>{field.label}</li>)}</ul>
    </details> : null}
  </section>;
}
