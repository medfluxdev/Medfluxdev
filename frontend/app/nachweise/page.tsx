"use client";

import { useCallback, useEffect, useState } from "react";
import EvidencePane from "@/components/contracts/detail/EvidencePane";
import PdfViewer from "@/components/contracts/detail/PdfViewer";
import SourceLink from "@/components/contracts/detail/SourceLink";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { apiGet } from "@/lib/api";
import type {
  ContractDetailResponse,
  DetailDocument,
  EvidenceRef,
  SourceNavigationTarget,
} from "@/lib/contract-detail-types";
import type { ContractListResponse, ContractListItem } from "@/lib/contract-types";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

function toTarget(ref: EvidenceRef): SourceNavigationTarget {
  const label = ref.snippet
    ? ref.snippet.slice(0, 60)
    : ref.field_ref ?? "Quelle";
  return {
    document_version_id: ref.document_version_id,
    page: ref.page,
    bbox: ref.bbox,
    bbox_space: ref.bbox_space,
    supports_exact_navigation: ref.supports_exact_navigation,
    label,
    field_ref: ref.field_ref,
    evidence_id: ref.evidence_id,
  };
}

export default function NachweisePage() {
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [contractId, setContractId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ContractDetailResponse | null>(null);
  const [activeDoc, setActiveDoc] = useState<DetailDocument | null>(null);
  const [navTarget, setNavTarget] = useState<SourceNavigationTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadContracts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams({
        organization_slug: ORG_SLUG,
        page_size: "100",
      });
      const res = await apiGet<ContractListResponse>(`/api/contracts?${p.toString()}`);
      setContracts(res.items);
      setContractId((cur) => cur ?? (res.items[0]?.contract_id ?? null));
    } catch {
      setError("Verträge konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContracts();
  }, [loadContracts]);

  const loadDetail = useCallback(async (id: string) => {
    setLoadingDetail(true);
    setDetailError(null);
    try {
      const res = await apiGet<ContractDetailResponse>(
        `/api/contracts/${encodeURIComponent(id)}?organization_slug=${encodeURIComponent(ORG_SLUG)}`
      );
      setDetail(res);
      const first = res.documents.find((d) => d.viewer_supported) ?? null;
      setActiveDoc(first);
      setNavTarget(null);
    } catch {
      setDetail(null);
      setDetailError("Vertragsdetail konnte nicht geladen werden.");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (!contractId) return;
    loadDetail(contractId);
  }, [contractId, loadDetail]);

  function onNavigate(ref: EvidenceRef) {
    const target = toTarget(ref);
    setNavTarget(target);
    if (!target.document_version_id) return;
    const doc =
      detail?.documents.find(
        (d) => d.document_version_id === target.document_version_id
      ) ?? null;
    if (doc && doc.viewer_supported) setActiveDoc(doc);
    else setActiveDoc(null);
  }

  return (
    <div className="page">
      <PageHeader
        title="Nachweise"
        description="Quellen, Belege und Originaldokumente der lokalen Vertragsanalyse."
      />

      {error && (
        <InlineAlert
          tone="critical"
          role="alert"
          action={
            <button type="button" className="btn btn-sm" onClick={() => void loadContracts()}>
              Erneut laden
            </button>
          }
        >
          {error}
        </InlineAlert>
      )}

      {loading && <LoadingState>Verträge werden geladen…</LoadingState>}

      {!loading && !error && contracts.length === 0 && (
        <div className="state-box">
          <div className="state-icon">∅</div>
          <h3>Keine Verträge verfügbar</h3>
          <p>
            Importieren Sie Verträge, um deren Quellen und Nachweise hier zu
            durchsuchen.
          </p>
        </div>
      )}

      {!loading && !error && contracts.length > 0 && (
        <section className="panel" aria-labelledby="nachweise-heading">
          <div className="panel-head">
            <div>
              <h2 id="nachweise-heading">Nachweise durchsuchen</h2>
              <p>Auswahl eines Vertrags – echte Quellen aus der lokalen Analyse</p>
            </div>
            <label className="field" style={{ minWidth: 280 }}>
              <span className="visually-hidden">Vertrag</span>
              <select
                value={contractId ?? ""}
                onChange={(e) => setContractId(e.target.value)}
              >
                {contracts.map((c) => (
                  <option key={c.contract_id} value={c.contract_id}>
                    {c.contract_number ?? "–"} · {c.contract_title ?? c.supplier}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loadingDetail ? (
            <LoadingState>Nachweise werden geladen…</LoadingState>
          ) : detailError ? (
            <InlineAlert
              tone="critical"
              role="alert"
              action={
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => contractId && void loadDetail(contractId)}
                >
                  Erneut laden
                </button>
              }
            >
              {detailError}
            </InlineAlert>
          ) : detail ? (
            <div className="detail-columns">
              <div className="detail-main">
                <div className="detail-card">
                  <h2>Quellen</h2>
                  {detail.documents.length === 0 ? (
                    <p className="evidence-empty">Keine Quelldokumente hinterlegt.</p>
                  ) : (
                    <div className="source-list">
                      {detail.documents.map((doc) => (
                        <SourceLink
                          key={doc.document_version_id}
                          document={doc}
                          active={activeDoc?.document_version_id === doc.document_version_id}
                          onSelect={(d) => {
                            setActiveDoc(d);
                            setNavTarget(null);
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
                <PdfViewer
                  contractId={detail.contract_id}
                  orgSlug={ORG_SLUG}
                  documentVersionId={activeDoc?.document_version_id ?? null}
                  active={Boolean(activeDoc)}
                  navTarget={navTarget}
                />
              </div>
              <div className="detail-aside">
                <div className="detail-card">
                  <h2>Belege</h2>
                  <EvidencePane
                    evidence={detail.evidence}
                    activeEvidenceId={navTarget?.evidence_id ?? null}
                    onNavigate={onNavigate}
                  />
                </div>
              </div>
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
