"use client";

import { useEffect, useState } from "react";
import { getPermissionMatrix, type PermissionMatrix } from "@/lib/domain-api/access";

export default function PermissionMatrixView({ organizationSlug }: { organizationSlug: string }) {
  const [data, setData] = useState<PermissionMatrix | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPermissionMatrix(organizationSlug)
      .then((result) => { if (!cancelled) setData(result); })
      .catch(() => { if (!cancelled) setError("Die Rechte-Matrix konnte nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [organizationSlug]);

  if (error) return <p role="alert" className="rg-error">{error}</p>;
  if (!data) return <p role="status">Rechte werden geladen…</p>;

  const areas = Array.from(new Set(data.permissions.map((item) => item.area)));
  const ownRole = data.roles.find((item) => item.key === data.role)?.label ?? (data.role === "developer" ? "Entwicklung (alle Rechte)" : data.role);

  return <div className="rg-panel">
    <p className="cw-muted">Ihre Rolle: <strong>{ownRole}</strong> · {data.granted.length} von {data.permissions.length} Rechten.</p>
    <section className="cw-section">
      <table className="rg-table">
        <caption className="visually-hidden">Rechte je Rolle</caption>
        <thead><tr><th scope="col">Recht</th>{data.roles.map((role) => <th key={role.key} scope="col">{role.label}</th>)}</tr></thead>
        {areas.map((area) => <tbody key={area}>
          <tr><th scope="colgroup" colSpan={data.roles.length + 1}>{area}</th></tr>
          {data.permissions.filter((item) => item.area === area).map((item) => <tr key={item.key}>
            <th scope="row">{item.label}{data.granted.includes(item.key) ? <span className="cw-badge badge--info rg-own">Ihr Recht</span> : null}</th>
            {data.roles.map((role) => <td key={role.key}>{item.roles.includes(role.key) ? <span aria-label="erlaubt">✓</span> : <span aria-label="nicht erlaubt" className="cw-muted">–</span>}</td>)}
          </tr>)}
        </tbody>)}
      </table>
    </section>
    <p className="cw-muted">Vertrauliche Verträge sehen nur Administratoren, die verantwortliche Person, die Erinnerungsempfänger und ausdrücklich freigegebene Benutzer.</p>
  </div>;
}
