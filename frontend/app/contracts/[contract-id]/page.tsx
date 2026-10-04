"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ContractWorkspace from "@/components/contracts/detail/ContractWorkspace";
import ContractOwnershipPanel from "@/components/contracts/detail/ContractOwnershipPanel";
import ContractIntelligencePanel from "@/components/contracts/detail/ContractIntelligencePanel";
import ContractBackendAnalysisPanel from "@/components/contracts/detail/ContractBackendAnalysisPanel";
import ContractBillingPanel from "@/components/contracts/detail/ContractBillingPanel";
import ContractLifecyclePanel from "@/components/contracts/detail/ContractLifecyclePanel";
import PdfViewer from "@/components/contracts/detail/PdfViewer";
import { useAuth } from "@/components/auth/AuthProvider";
import { getContract } from "@/lib/domain-api/contracts";
import type { ContractDetailResponse, EvidenceRef, SourceNavigationTarget } from "@/lib/contract-detail-types";

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

function sourceTarget(ref: EvidenceRef): SourceNavigationTarget {
  return {
    document_version_id: ref.document_version_id,
    page: ref.page,
    bbox: ref.bbox,
    bbox_space: ref.bbox_space,
    supports_exact_navigation: ref.supports_exact_navigation,
    label: ref.snippet || ref.field_ref || "Quelle",
    field_ref: ref.field_ref,
    evidence_id: ref.evidence_id,
  };
}

function resolveEvidence(data: ContractDetailResponse, refs: string[]): EvidenceRef | null {
  for (const wanted of refs) {
    const exact = data.evidence.find((ref) => ref.evidence_id === wanted || ref.field_ref === wanted);
    if (exact) return exact;
  }
  for (const wanted of refs) {
    const prefixed = data.evidence.find((ref) => ref.field_ref?.startsWith(`${wanted}.`) || wanted.startsWith(`${ref.field_ref}.`));
    if (prefixed) return prefixed;
  }
  return null;
}

export default function ContractDetailPage() {
  const params = useParams<{ "contract-id": string }>();
  const contractId = params?.["contract-id"] ?? "";
  const { organizationSlug, account } = useAuth();

  const [data, setData] = useState<ContractDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [intelligenceTarget, setIntelligenceTarget] = useState<SourceNavigationTarget | null>(null);
  const [sourceUnavailable, setSourceUnavailable] = useState(false);

  const load = useCallback(() => {
    if (!contractId || !organizationSlug) return;
    setLoading(true);
    setError(false);
    getContract(contractId, organizationSlug)
      .then((res) => setData(normalizeContractDetail(res)))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [contractId, organizationSlug]);

  useEffect(load, [load]);

  useEffect(() => {
    function onEvidence(event: Event) {
      if (!data) return;
      const detail = (event as CustomEvent<{ refs?: string[] }>).detail;
      const refs = Array.isArray(detail?.refs) ? detail.refs.filter((value): value is string => typeof value === "string") : [];
      const evidence = resolveEvidence(data, refs);
      if (!evidence?.document_version_id) {
        setIntelligenceTarget(null);
        setSourceUnavailable(true);
        return;
      }
      setSourceUnavailable(false);
      setIntelligenceTarget(sourceTarget(evidence));
      window.setTimeout(() => document.getElementById("intelligence-source-viewer")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    }
    window.addEventListener("medflux:intelligence-evidence", onEvidence);
    return () => window.removeEventListener("medflux:intelligence-evidence", onEvidence);
  }, [data]);

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
          <ContractWorkspace
            data={data}
            orgSlug={organizationSlug}
            onReload={load}
            slots={{
              overview: <>
                <ContractIntelligencePanel contractId={data.contract_id} organizationSlug={organizationSlug} />
                {account?.is_developer ? (
                  <details className="dev-details">
                    <summary>Entwicklerdetails: vollständige Analyse</summary>
                    <ContractBackendAnalysisPanel data={data} organizationSlug={organizationSlug} />
                  </details>
                ) : null}
              </>,
              register: <ContractOwnershipPanel contractId={data.contract_id} orgSlug={organizationSlug} onSaved={load} />,
              deadlines: <ContractLifecyclePanel contractId={data.contract_id} organizationSlug={organizationSlug} />,
              finance: <ContractBillingPanel contractId={data.contract_id} organizationSlug={organizationSlug} />,
            }}
          />
          {sourceUnavailable ? (
            <div id="intelligence-source-viewer" className="alert" role="status">
              Der Intelligence-Nachweis konnte keinem kanonischen Vertragsnachweis zugeordnet werden. Es wird keine Quelle erfunden.
            </div>
          ) : null}
          {intelligenceTarget ? (
            <section id="intelligence-source-viewer" className="cw-section" aria-label="Quelle aus der Vertragsanalyse">
              <div className="cw-section-head">
                <div><h2>Quelle aus der Vertragsanalyse</h2><p>{intelligenceTarget.label}</p></div>
                <button type="button" className="btn-ghost" onClick={() => setIntelligenceTarget(null)}>Schließen</button>
              </div>
              <PdfViewer
                contractId={data.contract_id}
                orgSlug={organizationSlug}
                documentVersionId={intelligenceTarget.document_version_id}
                active={true}
                navTarget={intelligenceTarget}
              />
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
