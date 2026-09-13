"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ContractWorkspace from "@/components/contracts/detail/ContractWorkspace";
import ContractOwnershipPanel from "@/components/contracts/detail/ContractOwnershipPanel";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

function normalizeContractDetail(res: ContractDetailResponse): ContractDetailResponse {
  return {
    ...res,
    equipment: res.equipment ?? [],
    warnings: res.warnings ?? [],
    work_items: res.work_items ?? [],
    documents: res.documents ?? [],
    evidence: res.evidence ?? [],
    overrides: res.overrides ?? [],
    audit_log: res.audit_log ?? [],
    fact_review_states: res.fact_review_states ?? [],
    fact_reviews: res.fact_reviews ?? [],
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
