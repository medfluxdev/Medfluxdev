"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import { listEquipment } from "@/lib/domain-api/equipment";
import type { EquipmentSummary } from "@/lib/pr4-types";
import { identificationQualityLabel } from "@/lib/pr4-types";

export default function EquipmentPage() {
  const { organizationSlug } = useAuth();
  const [items, setItems] = useState<EquipmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    if (!organizationSlug) return;
    setLoading(true);
    setError(false);
    listEquipment(organizationSlug, { limit: 500 })
      .then((res) => setItems(res))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [organizationSlug]);

  useEffect(load, [load]);

  return (
    <div className="page">
      <PageHeader
        title="Geräte"
        description={`${items.length} ${items.length === 1 ? "sichtbares Gerät" : "sichtbare Geräte"} im aktuellen Arbeitsbereich`}
      />

      {error && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          Geräte konnten nicht geladen werden.
        </InlineAlert>
      )}

      {loading && <LoadingState>Geräte werden geladen…</LoadingState>}

      {!loading && !error && items.length === 0 && (
        <div className="state-box">
          <div className="state-icon">∅</div>
          <h3>Noch keine Geräte vorhanden</h3>
          <p>Im aktuellen Krankenhaus-/Abteilungsbereich sind noch keine Geräte sichtbar.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <section className="panel" aria-label="Geräteliste">
        <div className="table-wrap">
          <table className="contract-table">
            <caption className="sr-text">Geräte und zugehörige Verträge</caption>
            <thead>
              <tr>
                <th scope="col">Gerät</th>
                <th scope="col">Hersteller</th>
                <th scope="col">Modell</th>
                <th scope="col">Seriennr.</th>
                <th scope="col">Identität</th>
                <th scope="col" className="num">Verträge</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td><Link className="table-link" href={`/equipment/${e.id}`}>{e.device_name ?? "Gerät"}</Link></td>
                  <td>{e.manufacturer ?? "–"}</td>
                  <td>{e.model ?? "–"}</td>
                  <td>{e.serial_number ?? (e.inventory_number ?? "–")}</td>
                  <td>{identificationQualityLabel(e.identification_quality)}</td>
                  <td className="num">{e.contract_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </section>
      )}
    </div>
  );
}
