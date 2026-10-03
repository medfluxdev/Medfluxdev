"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import SectionCard from "@/components/ui/SectionCard";
import StatusBadge from "@/components/ui/StatusBadge";
import DefinitionList from "@/components/ui/DefinitionList";
import Button from "@/components/ui/Button";
import { useAuth } from "@/components/auth/AuthProvider";
import { getEquipment } from "@/lib/domain-api/equipment";
import { getEquipmentLifecycle, updateEquipmentLifecycle, type EquipmentLifecycle, type EquipmentLifecycleStatus } from "@/lib/domain-api/lifecycle";
import type { EquipmentDetail } from "@/lib/pr4-types";
import {
  identificationQualityLabel,
  relationshipQualityLabel,
} from "@/lib/pr4-types";

const LIFECYCLE_LABELS: Record<EquipmentLifecycleStatus, string> = {
  active: "Aktiv",
  maintenance_due: "Wartung fällig",
  out_of_service: "Außer Betrieb",
  retired: "Ausgemustert",
};

export default function EquipmentDetailPage() {
  const params = useParams<{ "equipment-id": string }>();
  const equipmentId = params?.["equipment-id"] ?? "";
  const { organizationSlug } = useAuth();

  const [data, setData] = useState<EquipmentDetail | null>(null);
  const [lifecycle, setLifecycle] = useState<EquipmentLifecycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    if (!equipmentId || !organizationSlug) return;
    setLoading(true);
    setError(false);
    Promise.all([getEquipment(equipmentId, organizationSlug), getEquipmentLifecycle(organizationSlug, equipmentId)])
      .then(([equipment, lifecycleState]) => { setData(equipment); setLifecycle(lifecycleState); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [equipmentId, organizationSlug]);

  useEffect(load, [load]);

  async function saveLifecycle() {
    if (!organizationSlug || !lifecycle) return;
    setSaving(true);
    try {
      const updated = await updateEquipmentLifecycle(organizationSlug, equipmentId, {
        status: lifecycle.status,
        next_service_date: lifecycle.next_service_date,
        note: lifecycle.note,
      });
      setLifecycle(updated);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <nav className="breadcrumb" aria-label="Brotkrümelnavigation">
        <Link href="/equipment">Geräte</Link>
        <span aria-hidden="true">/</span>
        <span>Detail</span>
      </nav>

      {loading && <LoadingState>Gerät wird geladen…</LoadingState>}

      {error && !loading && !data && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          Gerät konnte nicht geladen werden.
        </InlineAlert>
      )}

      {!loading && data && (
        <>
          <header className="entity-header">
            <h1>{data.device_name ?? "Gerät"}</h1>
            <div className="badge-row">
              <StatusBadge label={identificationQualityLabel(data.identification_quality)} tone={data.identification_quality === "exact" ? "success" : "review"} />
              <StatusBadge label={`${data.contract_count} Verträge`} tone="neutral" />
              {lifecycle ? <StatusBadge label={LIFECYCLE_LABELS[lifecycle.status]} tone={lifecycle.status === "active" ? "success" : lifecycle.status === "maintenance_due" ? "warning" : "neutral"} /> : null}
            </div>
            <p className="page-sub">{[data.manufacturer, data.model, data.equipment_category].filter(Boolean).join(" · ") || "Keine weiteren Angaben"}</p>
          </header>

          {error ? <InlineAlert tone="warning" role="status">Eine Aktualisierung konnte nicht abgeschlossen werden.</InlineAlert> : null}

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

            {lifecycle ? <SectionCard title="Betriebsstatus">
              <div className="form-grid">
                <label>Status<select value={lifecycle.status} onChange={(event) => setLifecycle((current) => current ? { ...current, status: event.target.value as EquipmentLifecycleStatus } : current)}>{Object.entries(LIFECYCLE_LABELS).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                <label>Nächster Service<input type="date" value={lifecycle.next_service_date ?? ""} onChange={(event) => setLifecycle((current) => current ? { ...current, next_service_date: event.target.value || null } : current)} /></label>
                <label className="form-field-wide">Notiz<textarea rows={3} value={lifecycle.note ?? ""} onChange={(event) => setLifecycle((current) => current ? { ...current, note: event.target.value || null } : current)} /></label>
                <div><Button variant="primary" disabled={saving} onClick={() => void saveLifecycle()}>Betriebsstatus speichern</Button></div>
              </div>
            </SectionCard> : null}

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
