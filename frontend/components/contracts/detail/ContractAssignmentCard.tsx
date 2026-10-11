"use client";

import Link from "next/link";
import type { ContractAssignment } from "@/lib/contract-detail-types";
import { contractHref } from "@/lib/fix-targets";

/**
 * Übersicht, Seitenleiste: wem der Vertrag gehört – Krankenhaus, Abteilungen, Kostenstelle, Hauptverantwortliche.
 * Weitere Verantwortliche stehen nur in der Organisationszuordnung (Entscheidung 2026-10-11).
 * Für alle Rollen lesbar; mit Bearbeitungsrecht führt „Ändern“ bzw. „Festlegen“ zur Organisationszuordnung.
 */
export default function ContractAssignmentCard({ contractId, assignment, canEdit }: {
  contractId: string;
  assignment: ContractAssignment | null | undefined;
  canEdit: boolean;
}) {
  const href = contractHref(contractId, { tab: "register", section: "ownership" });
  const a = assignment ?? null;
  const missing = (label: string) => canEdit
    ? <Link href={href} aria-label={`${label} festlegen`}>Festlegen</Link>
    : <span className="side-none">Nicht festgelegt</span>;
  const none = <span className="side-none">Keine</span>;
  const departments = [...(a?.beneficiary_departments ?? []), ...(a?.other_departments ?? [])];

  return <section className="cw-section contract-assignment" aria-labelledby="assignment-heading">
    <div className="cw-section-head">
      <div><h2 id="assignment-heading">Zuständigkeit</h2></div>
      {canEdit ? <Link className="btn btn-sm" href={href} aria-label="Zuordnung ändern">Ändern</Link> : null}
    </div>
    <dl className="side-dl">
      <div><dt>Vertragstyp</dt><dd>{a?.contract_type ? <>{a.contract_type}{a.contract_category ? ` · ${a.contract_category}` : ""}</> : missing("Vertragstyp")}</dd></div>
      <div><dt>Gerätearten</dt><dd>{a?.device_types?.length ? a.device_types.join(", ") : canEdit ? <Link href={contractHref(contractId, { tab: "relations" })} aria-label="Gerätearten festlegen">Festlegen</Link> : none}</dd></div>
      <div><dt>Krankenhaus</dt><dd>{a?.hospital ?? (a ? "Organisationsweit" : missing("Krankenhaus"))}</dd></div>
      <div><dt>Verantwortliche Abteilung</dt><dd>{a?.responsible_department ?? missing("Verantwortliche Abteilung")}</dd></div>
      <div><dt>Hauptverantwortlich</dt><dd>{a?.responsible ?? missing("Verantwortliche Person")}</dd></div>
      <div><dt>Kostenstelle</dt><dd>{a?.cost_center ? <><span className="mono">{a.cost_center.code}</span> · {a.cost_center.name}</> : missing("Kostenstelle")}</dd></div>
      <div><dt>Nutzende Abteilungen</dt><dd>{departments.length ? departments.join(", ") : none}</dd></div>
    </dl>
  </section>;
}
