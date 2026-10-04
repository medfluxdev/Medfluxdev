"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Badge from "@/components/ui/Badge";
import Skeleton from "@/components/ui/Skeleton";
import { getSetupStatus, type SetupStatus } from "@/lib/domain-api/adminSetup";

const STATUS_LABEL = { ok: "Erledigt", todo: "Offen", optional: "Optional" } as const;
const STATUS_TONE = { ok: "success", todo: "warning", optional: "neutral" } as const;

// U5: zeigt Administratoren, was fuer den Betrieb noch eingerichtet werden muss.
export default function SetupChecklist({ organizationSlug }: { organizationSlug: string }) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    getSetupStatus(organizationSlug).then(setStatus).catch(() => setFailed(true));
  }, [organizationSlug]);

  useEffect(load, [load]);

  return (
    <section className="card card-pad setup-checklist" aria-labelledby="setup-heading">
      <div className="section-head">
        <div>
          <h2 id="setup-heading">Einrichtung</h2>
          <p>{status ? (status.required_open === 0 ? "Alle notwendigen Schritte sind erledigt." : `${status.required_open} notwendige Schritte offen · ${status.done} von ${status.total} erledigt`) : "Was für den Betrieb eingerichtet sein sollte"}</p>
        </div>
      </div>
      {failed ? <p className="alert alert--critical" role="alert">Der Einrichtungsstand konnte nicht geladen werden. <button type="button" className="btn btn-sm" onClick={load}>Erneut laden</button></p> : null}
      {!status && !failed ? <Skeleton lines={5} label="Einrichtungsstand wird geladen…" /> : null}
      {status ? (
        <ol className="setup-list">
          {status.items.map((item) => (
            <li key={item.key} className={`setup-item is-${item.status}`}>
              <span className="setup-mark" aria-hidden="true">{item.status === "ok" ? "✓" : item.status === "todo" ? "!" : "○"}</span>
              <div><Link href={item.href}>{item.label}</Link><small>{item.detail}</small></div>
              <Badge tone={STATUS_TONE[item.status]}>{STATUS_LABEL[item.status]}</Badge>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
