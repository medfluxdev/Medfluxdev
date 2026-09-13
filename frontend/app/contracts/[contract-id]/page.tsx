"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ContractWorkspace from "@/components/contracts/detail/ContractWorkspace";
import ContractOwnershipPanel from "@/components/contracts/detail/ContractOwnershipPanel";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

function normalizeContractDetail(res: ContractDetailResponse): ContractDetailResponse {
  const factReviewStates = res.fact_review_states ?? [];
  const reviewedCount = factReviewStates.filter((fact) => ["confirmed", "corrected", "voided"].includes(fact.state)).length;
  const relevantCount = factReviewStates.length;

  return {
    ...res,
    equipment: (res.equipment ?? []).map((item, index) => ({
      ...item,
      id: item.id ?? `equipment-${index}`,
      included_services: item.included_services ?? [],
      excluded_services: item.excluded_services ?? [],
      review_reasons: item.review_reasons ?? [],
    })),
    warnings: res.warnings ?? [],
    work_items: res.work_items ?? [],
    documents: res.documents ?? [],
    evidence: res.evidence ?? [],
    overrides: res.overrides ?? [],
    audit_log: res.audit_log ?? [],
    fact_review_states: factReviewStates,
    fact_reviews: res.fact_reviews ?? [],
    contract_review: res.contract_review ?? {
      status: relevantCount > 0 ? "in_review" : "not_started",
      status_label_de: relevantCount > 0 ? "In manueller Prüfung" : "Nicht gestartet",
      reviewer_display_name: null,
      reviewer_identity_type: "system",
      authenticated_actor_id: null,
      reviewed_at: null,
      changed_noted_at: null,
      completion_note: null,
      relevant_count: relevantCount,
      reviewed_count: reviewedCount,
      unresolved_count: Math.max(0, relevantCount - reviewedCount),
      critical_count: factReviewStates.filter((fact) => fact.is_critical).length,
      critical_reviewed_count: factReviewStates.filter((fact) => fact.is_critical && ["confirmed", "corrected", "voided"].includes(fact.state)).length,
      critical_unreviewed_count: factReviewStates.filter((fact) => fact.is_critical && !["confirmed", "corrected", "voided"].includes(fact.state)).length,
    },
    import_state: res.import_state ?? {
      import_state: "analysis_ok",
      state_label_de: "Analyse abgeschlossen",
      document_version_id: res.documents?.[0]?.document_version_id ?? null,
      can_retry: false,
      message: null,
      analysis_status: null,
      requires_review: res.review?.requires_manual_review ?? false,
    },
  };
}

export default function ContractDetailPage() {
  const params = useParams<{ "contract-id": string }>();
  const contractId = params?.["contract-id"] ?? "";
  const { organizationSlug } = useAuth();

  const [data, setData] = useState<ContractDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    if (!contractId || !organizationSlug) return;
    setLoading(true);
    setError(false);
    apiGet<ContractDetailResponse>(
      `/api/contracts/${encodeURIComponent(contractId)}?organization_slug=${encodeURIComponent(organizationSlug)}`
    )
      .then((res) => setData(normalizeContractDetail(res)))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [contractId, organizationSlug]);

  useEffect(load, [load]);

  return (
    <div className="page">
      {!data && loading && <p className="state-loading">Vertrag wird geladen…</p>}

      {!data && error && !loading && (
        <div className="alert alert--critical" role="alert">
          <span>Vertrag konnte nicht geladen werden.</span>
          <button className="btn btn-sm retry" type="button" onClick={load}>
            Erneut laden
          </button>
        </div>
      )}

      {data && error && (
        <div className="alert" role="status">
          Aktualisierung fehlgeschlagen – die Anzeige zeigt den zuletzt geladenen Stand.
        </div>
      )}

      {data && organizationSlug ? (
        <>
          <ContractOwnershipPanel contractId={data.contract_id} orgSlug={organizationSlug} onSaved={load} />
          <ContractWorkspace data={data} orgSlug={organizationSlug} onReload={load} />
        </>
      ) : null}
    </div>
  );
}
