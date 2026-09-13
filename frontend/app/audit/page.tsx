"use client";

import { useCallback, useEffect, useState } from "react";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import { getContract, listContracts } from "@/lib/domain-api/contracts";
import { listActivity, type ActivityDto } from "@/lib/domain-api/activity";
import type { AuditEntryDto, ContractDetailResponse, FactReviewDto } from "@/lib/contract-detail-types";
import type { ContractListItem } from "@/lib/contract-types";
import { formatDate } from "@/lib/format";

const EVENT_LABELS: Record<string, string> = {
  "fact_review.confirmed": "Fakt bestätigt",
  "fact_review.corrected": "Fakt korrigiert",
  "fact_review.reopened": "Fakt erneut geöffnet",
  "fact_review.voided": "Fakt verworfen",
  "contract_review.started": "Vertragsreview geöffnet",
  "contract_review.completed": "Vertragsreview abgeschlossen",
  "override.set": "Override gesetzt",
  "override.void": "Override zurückgesetzt",
  "override.confirm": "Fakt manuell bestätigt",
  "contract.archived": "Vertrag archiviert",
  "contract.unarchived": "Vertrag wiederhergestellt",
  "contract.ownership_updated": "Vertragszuordnung geändert",
  "equipment.ownership_updated": "Gerätezuordnung geändert",
  "account.created": "Benutzer angelegt",
  "account.updated": "Benutzer geändert",
  "account.scope_updated": "Benutzerbereich geändert",
  "hospital.created": "Krankenhaus angelegt",
  "hospital.updated": "Krankenhaus geändert",
  "department.created": "Abteilung angelegt",
  "department.updated": "Abteilung geändert",
  "cost_center.created": "Kostenstelle angelegt",
};

function valueText(value: unknown): string {
  if (value == null) return "–";
  if (typeof value === "string") return value;
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    const keys = Object.keys(v);
    if (keys.length === 0) return "–";
    return keys.map((k) => `${k}: ${valueText(v[k])}`).join(", ");
  }
  return String(value);
}

function auditActionClass(action: string): string {
  if (action === "set") return "audit-set";
  if (action === "void") return "audit-void";
  if (action === "confirm") return "audit-confirm";
  return "";
}

function AuditRow({ e }: { e: AuditEntryDto }) {
  return (
    <li>
      <span className={`audit-action ${auditActionClass(e.action)}`}>{e.action}</span>
      <span className="audit-key">{e.label_de ?? e.key}</span>
      {e.fact_ref && <span className="audit-ref">{e.fact_ref}</span>}
      {e.old_value && <span className="audit-value">alt: {valueText(e.old_value)}</span>}
      {e.value && <span className="audit-value">neu: {valueText(e.value)}</span>}
      {e.note && <span className="audit-ref">Notiz: {e.note}</span>}
      {e.created_at && <time className="audit-date">{formatDate(e.created_at)}</time>}
    </li>
  );
}

function FactRow({ r }: { r: FactReviewDto }) {
  return (
    <li>
      <span className={`audit-action ${r.action === "confirmed" ? "audit-confirm" : r.action === "voided" ? "audit-void" : "audit-set"}`}>
        {r.action_label_de ?? r.action}
      </span>
      <span className="audit-key">{r.fact_label_de ?? r.fact_key}</span>
      {r.previous_effective_value != null && <span className="audit-value">vorher: {valueText(r.previous_effective_value)}</span>}
      {r.new_effective_value != null && <span className="audit-value">jetzt: {valueText(r.new_effective_value)}</span>}
      {r.note && <span className="audit-ref">Notiz: {r.note}</span>}
      {r.reviewer_display_name && <span className="audit-ref">von {r.reviewer_display_name}</span>}
      {r.created_at && <time className="audit-date">{formatDate(r.created_at)}</time>}
    </li>
  );
}

function ActivityRow({ item }: { item: ActivityDto }) {
  return (
    <li>
      <span className="audit-action audit-confirm">{EVENT_LABELS[item.event_name] ?? item.event_name}</span>
      <span className="audit-key">{item.display_name ?? "System"}</span>
      <span className="audit-ref">{item.role ?? "system"}</span>
      {item.context_data && Object.keys(item.context_data).length > 0 ? <span className="audit-value">{valueText(item.context_data)}</span> : null}
      {item.created_at ? <time className="audit-date">{formatDate(item.created_at)}</time> : null}
    </li>
  );
}

export default function AuditPage() {
  const { organizationSlug } = useAuth();
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [contractId, setContractId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ContractDetailResponse | null>(null);
  const [activity, setActivity] = useState<ActivityDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadContracts = useCallback(async () => {
    if (!organizationSlug) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listContracts(organizationSlug, { page_size: 100 });
      setContracts(res.items);
      setContractId((cur) => cur ?? (res.items[0]?.contract_id ?? null));
    } catch {
      setError("Verträge konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [organizationSlug]);

  useEffect(() => { void loadContracts(); }, [loadContracts]);

  const loadDetail = useCallback(async (id: string) => {
    if (!organizationSlug) return;
    setLoadingDetail(true);
    setDetailError(null);
    try {
      const [detailResponse, activityResponse] = await Promise.all([
        getContract(id, organizationSlug),
        listActivity(organizationSlug, { objectId: id, limit: 200 }),
      ]);
      setDetail(detailResponse);
      setActivity(activityResponse.items);
    } catch {
      setDetail(null);
      setActivity([]);
      setDetailError("Audit-Daten konnten nicht geladen werden.");
    } finally {
      setLoadingDetail(false);
    }
  }, [organizationSlug]);

  useEffect(() => { if (contractId) void loadDetail(contractId); }, [contractId, loadDetail]);

  const review = detail?.contract_review;

  return (
    <div className="page">
      <PageHeader title="Audit" description="Nachvollziehbarkeit mit authentifiziertem Benutzer, Zeitpunkt und Änderung." />
      {error && <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void loadContracts()}>Erneut laden</button>}>{error}</InlineAlert>}
      {loading && <LoadingState>Verträge werden geladen…</LoadingState>}
      {!loading && !error && contracts.length === 0 && <div className="state-box"><div className="state-icon">∅</div><h3>Keine Verträge verfügbar</h3><p>Audit-Einträge erscheinen erst, wenn Verträge bearbeitet wurden.</p></div>}

      {!loading && !error && contracts.length > 0 && (
        <section className="panel" aria-labelledby="audit-heading">
          <div className="panel-head">
            <div><h2 id="audit-heading">Audit-Trail</h2><p>Prüfungen, Korrekturen, Overrides und Benutzeraktionen eines Vertrags</p></div>
            <label className="field" style={{ minWidth: 280 }}><span className="visually-hidden">Vertrag</span><select value={contractId ?? ""} onChange={(e) => setContractId(e.target.value)}>{contracts.map((c) => <option key={c.contract_id} value={c.contract_id}>{c.contract_number ?? "–"} · {c.contract_title ?? c.supplier}</option>)}</select></label>
          </div>

          {loadingDetail ? <LoadingState>Audit-Trail wird geladen…</LoadingState> : detailError ? <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => contractId && void loadDetail(contractId)}>Erneut laden</button>}>{detailError}</InlineAlert> : detail ? (
            <div className="audit-grid" style={{ marginBottom: 18 }}>
              <div className="audit-item"><span className="audit-dot" aria-hidden="true" /><div><b>Prüfstatus</b><p>{review?.status_label_de ?? "Unbekannt"}</p></div></div>
              <div className="audit-item"><span className="audit-dot" aria-hidden="true" /><div><b>Geprüfte Fakten</b><p>{review?.reviewed_count ?? 0} von {review?.relevant_count ?? 0}{review && review.unresolved_count > 0 ? ` · ${review.unresolved_count} offen` : ""}</p></div></div>
              <div className="audit-item"><span className="audit-dot" aria-hidden="true" /><div><b>Kritische Angaben</b><p>{review ? `${review.critical_reviewed_count} von ${review.critical_count} geprüft` : "–"}</p></div></div>
              <div className="audit-item"><span className="audit-dot" aria-hidden="true" /><div><b>Letzte Prüfung</b><p>{review?.reviewed_at ? formatDate(review.reviewed_at) : "Noch keine"}</p></div></div>
            </div>
          ) : null}

          {!loadingDetail && !detailError && detail ? (
            <div className="detail-columns">
              <div className="detail-card"><h2>Benutzeraktivität</h2>{activity.length === 0 ? <p className="evidence-empty">Noch keine authentifizierten Aktivitäten vorhanden.</p> : <ul className="audit-list">{activity.map((item) => <ActivityRow key={item.id} item={item} />)}</ul>}</div>
              <div className="detail-card"><h2>Fakt-Prüfungen</h2>{detail.fact_reviews.length === 0 ? <p className="evidence-empty">Keine Fakt-Prüfungen vorhanden.</p> : <ul className="audit-list">{detail.fact_reviews.map((r) => <FactRow key={r.id} r={r} />)}</ul>}</div>
              <div className="detail-card"><h2>Manuelle Overrides</h2>{detail.audit_log.length === 0 ? <p className="evidence-empty">Keine manuellen Overrides vorhanden.</p> : <ul className="audit-list">{detail.audit_log.map((e) => <AuditRow key={e.id} e={e} />)}</ul>}</div>
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
