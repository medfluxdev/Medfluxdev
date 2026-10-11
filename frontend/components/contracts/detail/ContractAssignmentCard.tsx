"use client";

import Link from "next/link";
import type { ContractAssignment } from "@/lib/contract-detail-types";
import { contractHref } from "@/lib/fix-targets";

/**
 * Übersicht: wem der Vertrag gehört – Krankenhaus, Abteilungen, Kostenstelle, Verantwortliche.
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
    : <span className="cw-muted">Nicht festgelegt</span>;
  const departments = [...(a?.beneficiary_departments ?? []), ...(a?.other_departments ?? [])];
  const people = a?.further_responsible ?? [];

  return <section className="cw-section contract-assignment" aria-labelledby="assignment-heading">
    <div className="cw-section-head">
      <div><h2 id="assignment-heading">Organisation &amp; Zuständigkeit</h2><p>Wem der Vertrag zugeordnet ist und wer ihn verantwortet.</p></div>
      {canEdit ? <Link className="btn btn-sm" href={href}>Zuordnung ändern</Link> : null}
    </div>
    <dl className="contract-assignment-grid">
      <div><dt>Krankenhaus</dt><dd>{a?.hospital ?? (a ? "Organisationsweit" : missing("Krankenhaus"))}</dd></div>
      <div><dt>Verantwortliche Abteilung</dt><dd>{a?.responsible_department ?? missing("Verantwortliche Abteilung")}</dd></div>
      <div><dt>Nutzende Abteilungen</dt><dd>{departments.length ? departments.join(", ") : <span className="cw-muted">Keine</span>}</dd></div>
      <div><dt>Kostenstelle</dt><dd>{a?.cost_center ? `${a.cost_center.code} · ${a.cost_center.name}` : missing("Kostenstelle")}</dd></div>
      <div><dt>Hauptverantwortlich</dt><dd>{a?.responsible ?? missing("Verantwortliche Person")}</dd></div>
      <div><dt>Weitere Verantwortliche</dt><dd>{people.length ? people.join(", ") : <span className="cw-muted">Keine</span>}</dd></div>
    </dl>
  </section>;
}
