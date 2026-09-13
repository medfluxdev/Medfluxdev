"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import SectionCard from "@/components/ui/SectionCard";
import StatusBadge from "@/components/ui/StatusBadge";
import DefinitionList from "@/components/ui/DefinitionList";
import { useAuth } from "@/components/auth/AuthProvider";
import { getEquipment } from "@/lib/domain-api/equipment";
import type { EquipmentDetail } from "@/lib/pr4-types";
import {
  identificationQualityLabel,
  relationshipQualityLabel,
} from "@/lib/pr4-types";

export default function EquipmentDetailPage() {
  const params = useParams<{ "equipment-id": string }>();
  const equipmentId = params?.["equipment-id"] ?? "";
  const { organizationSlug } = useAuth();

  const [data, setData] = useState<EquipmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    if (!equipmentId || !organizationSlug) return;
    setLoading(true);
    setError(false);
    getEquipment(equipmentId, organizationSlug)
      .then((res) => setData(res))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [equipmentId, organizationSlug]);

  useEffect(load, [load]);

  return (
    <div className="page">
      <nav className="breadcrumb" aria-label="Brotkrümelnavigation">
        <Link href="/equipment">Geräte</Link>
        <span aria-hidden="true">/</span>
        <span>Detail</span>
      </nav>

      {loading && <LoadingState>Gerät wird geladen…</LoadingState>}

      {error && !loading && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          Gerät konnte nicht geladen werden.
        </InlineAlert>
      )}

      {!loading && !error && data && (
        <>
          <header className="entity-header">
            <h1>{data.device_name ?? "Gerät"}</h1>
            <div className="badge-row">
              <StatusBadge label={identificationQualityLabel(data.identification_quality)} tone={data.identification_quality === "exact" ? "success" : "review"} />
              <StatusBadge label={`${data.contract_count} Verträge`} tone="neutral" />
            </div>
            <p className="page-sub">{[data.manufacturer, data.model, data.equipment_category].filter(Boolean).join(" · ") || "Keine weiteren Angaben"}</p>
          </header>

          <div className="detail-grid">
            <SectionCard title="Identität">
              <DefinitionList
                rules={[
                  { label: "Gerätename", value: data.device_name ?? "–" },
                  { label: "Hersteller", value: data.manufacturer ?? "–" },
                  { label: "Modell", value: data.model ?? "–" },
                  { label: "Seriennummer", value: data.serial_number ?? "–" },
                  { label: "Inventarnummer", value: data.inventory_number ?? "–" },
                  { label: "Typ", value: data.equipment_type ?? "–" },
                  { label: "Kategorie", value: data.equipment_category ?? "–" },
                  { label: "Standort", value: data.location ?? "–" },
                  { label: "Abteilung", value: data.department ?? "–" },
                ]}
              />
            </SectionCard>

            <SectionCard title="Verbundene Verträge">
              {data.contracts.length === 0 && <p className="muted">Keine Verträge verknüpft.</p>}
              <ul className="link-list">
                {data.contracts.map((c) => (
                  <li key={c.contract_id} className="link-item">
                    <Link className="table-link" href={`/contracts/${c.contract_id}`}>
                      {c.contract_number ?? c.supplier ?? "Vertrag"}{c.supplier ? ` · ${c.supplier}` : ""}
                    </Link>
                    <div className="badge-row">
                      <StatusBadge label={relationshipQualityLabel(c.relationship_quality)} tone={c.requires_review ? "review" : "success"} />
                      {c.requires_review && <StatusBadge label="Zu prüfen" tone="review" />}
                    </div>
                    {c.service_scope && <p className="muted">{c.service_scope}</p>}
                  </li>
                ))}
              </ul>
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}
