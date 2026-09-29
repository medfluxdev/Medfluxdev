"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import EvidencePane from "@/components/contracts/detail/EvidencePane";
import PdfViewer from "@/components/contracts/detail/PdfViewer";
import SourceLink from "@/components/contracts/detail/SourceLink";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import { getContract, listContracts } from "@/lib/domain-api/contracts";
import type {
  ContractDetailResponse,
  DetailDocument,
  EvidenceRef,
  SourceNavigationTarget,
} from "@/lib/contract-detail-types";
import type { ContractListItem } from "@/lib/contract-types";

function toTarget(ref: EvidenceRef): SourceNavigationTarget {
  const label = ref.snippet ? ref.snippet.slice(0, 60) : ref.field_ref ?? "Quelle";
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
  const { organizationSlug } = useAuth();
  const listSeq = useRef(0);
  const detailSeq = useRef(0);
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
    const seq = ++listSeq.current;
    if (!organizationSlug) {
      setContracts([]);
      setContractId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await listContracts(organizationSlug, { page_size: 100 });
      if (seq !== listSeq.current) return;
      setContracts(res.items);
      setContractId((current) =>
        current && res.items.some((item) => item.contract_id === current)
          ? current : (res.items[0]?.contract_id ?? null)
      );
    } catch {
      if (seq === listSeq.current) setError("Verträge konnten nicht geladen werden.");
    } finally {
      if (seq === listSeq.current) setLoading(false);
    }
  }, [organizationSlug]);

  useEffect(() => {
    setContracts([]);
    setContractId(null);
    setDetail(null);
    setActiveDoc(null);
    setNavTarget(null);
    detailSeq.current += 1;
    void loadContracts();
    return () => { listSeq.current += 1; detailSeq.current += 1; };
  }, [loadContracts]);

  const loadDetail = useCallback(async (id: string) => {
    const seq = ++detailSeq.current;
    if (!organizationSlug) return;
    setLoadingDetail(true);
    setDetailError(null);
    setDetail(null);
    setActiveDoc(null);
    setNavTarget(null);
    try {
      const res = await getContract(id, organizationSlug);
      if (seq !== detailSeq.current) return;
      setDetail(res);
      setActiveDoc(res.documents.find((d) => d.viewer_supported) ?? null);
    } catch {
      if (seq !== detailSeq.current) return;
      setDetail(null);
      setDetailError("Vertragsdetail konnte nicht geladen werden.");
    } finally {
      if (seq === detailSeq.current) setLoadingDetail(false);
    }
  }, [organizationSlug]);

  useEffect(() => {
    if (contractId) void loadDetail(contractId);
    else {
      detailSeq.current += 1;
      setDetail(null);
      setActiveDoc(null);
      setNavTarget(null);
      setLoadingDetail(false);
    }
    return () => { detailSeq.current += 1; };
  }, [contractId, loadDetail]);

  function onNavigate(ref: EvidenceRef) {
    const target = toTarget(ref);
    setNavTarget(target);
    if (!target.document_version_id) return;
    const doc = detail?.documents.find((d) => d.document_version_id === target.document_version_id) ?? null;
    setActiveDoc(doc?.viewer_supported ? doc : null);
  }

  return (
    <div className="page">
      <PageHeader title="Nachweise" description="Quellen, Belege und Originaldokumente der lokalen Vertragsanalyse." />
      {error && <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void loadContracts()}>Erneut laden</button>}>{error}</InlineAlert>}
      {loading && <LoadingState>Verträge werden geladen…</LoadingState>}
      {!loading && !error && contracts.length === 0 && <div className="state-box"><div className="state-icon">∅</div><h3>Keine Verträge verfügbar</h3><p>Importieren Sie Verträge, um deren Quellen und Nachweise hier zu durchsuchen.</p></div>}
      {!loading && !error && contracts.length > 0 && (
        <section className="panel" aria-labelledby="nachweise-heading">
          <div className="panel-head">
            <div><h2 id="nachweise-heading">Nachweise durchsuchen</h2><p>Auswahl eines Vertrags – echte Quellen aus der lokalen Analyse</p></div>
            <label className="field" style={{ minWidth: 280 }}><span className="visually-hidden">Vertrag</span><select value={contractId ?? ""} onChange={(e) => setContractId(e.target.value)}>{contracts.map((c) => <option key={c.contract_id} value={c.contract_id}>{c.contract_number ?? "–"} · {c.contract_title ?? c.supplier}</option>)}</select></label>
          </div>
          {loadingDetail ? <LoadingState>Nachweise werden geladen…</LoadingState> : detailError ? <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => contractId && void loadDetail(contractId)}>Erneut laden</button>}>{detailError}</InlineAlert> : detail ? (
            <div className="detail-columns">
              <div className="detail-main">
                <div className="detail-card"><h2>Quellen</h2>{detail.documents.length === 0 ? <p className="evidence-empty">Keine Quelldokumente hinterlegt.</p> : <div className="source-list">{detail.documents.map((doc) => <SourceLink key={doc.document_version_id} document={doc} active={activeDoc?.document_version_id === doc.document_version_id} onSelect={(d) => { setActiveDoc(d); setNavTarget(null); }} />)}</div>}</div>
                <PdfViewer contractId={detail.contract_id} orgSlug={organizationSlug ?? ""} documentVersionId={activeDoc?.document_version_id ?? null} active={Boolean(activeDoc)} navTarget={navTarget} />
              </div>
              <div className="detail-aside"><div className="detail-card"><h2>Belege</h2><EvidencePane evidence={detail.evidence} activeEvidenceId={navTarget?.evidence_id ?? null} onNavigate={onNavigate} /></div></div>
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
