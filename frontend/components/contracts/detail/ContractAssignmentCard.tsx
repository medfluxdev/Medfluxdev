"use client";

import Link from "next/link";
import type { ContractAssignment } from "@/lib/contract-detail-types";
import { contractHref } from "@/lib/fix-targets";

/**
 * Übersicht, Seitenleiste: wem der Vertrag gehört – Krankenhaus, Abteilungen, Kostenstelle, Verantwortliche.
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
  const people = a?.further_responsible ?? [];

  return <section className="cw-section contract-assignment" aria-labelledby="assignment-heading">
    <div className="cw-section-head">
      <div><h2 id="assignment-heading">Zuständigkeit</h2></div>
      {canEdit ? <Link className="btn btn-sm" href={href} aria-label="Zuordnung ändern">Ändern</Link> : null}
    </div>
    <dl className="side-dl">
      <div><dt>Krankenhaus</dt><dd>{a?.hospital ?? (a ? "Organisationsweit" : missing("Krankenhaus"))}</dd></div>
      <div><dt>Verantwortliche Abteilung</dt><dd>{a?.responsible_department ?? missing("Verantwortliche Abteilung")}</dd></div>
      <div><dt>Hauptverantwortlich</dt><dd>{a?.responsible ?? missing("Verantwortliche Person")}</dd></div>
      <div><dt>Kostenstelle</dt><dd>{a?.cost_center ? <><span className="mono">{a.cost_center.code}</span> · {a.cost_center.name}</> : missing("Kostenstelle")}</dd></div>
      <div><dt>Weitere Verantwortliche</dt><dd>{people.length ? people.join(", ") : none}</dd></div>
      <div><dt>Nutzende Abteilungen</dt><dd>{departments.length ? departments.join(", ") : none}</dd></div>
    </dl>
  </section>;
}
