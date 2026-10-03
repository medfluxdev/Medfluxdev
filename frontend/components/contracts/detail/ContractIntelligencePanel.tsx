"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getContractActionProposals,
  getContractGraph,
  getContractObligations,
  getContractPolicies,
  transitionActionProposal,
  type ContractRelation,
  type ContractObligation,
  type IntelligenceActionProposal,
  type PolicyDecision,
} from "@/lib/domain-api/intelligence";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/format";
import styles from "./ContractIntelligencePanel.module.css";

interface Props {
  contractId: string;
  organizationSlug: string;
}

type IntelligenceState = {
  relations: ContractRelation[];
  obligations: ContractObligation[];
  policies: PolicyDecision[];
  actions: IntelligenceActionProposal[];
};

const EMPTY: IntelligenceState = { relations: [], obligations: [], policies: [], actions: [] };

function reviewBadge(required: boolean) {
  return required ? <StatusBadge tone="review" label="Prüfung erforderlich" /> : null;
}

function policyTone(outcome: string): "success" | "warning" | "critical" | "neutral" {
  const value = outcome.toLowerCase();
  if (["pass", "passed", "ok", "compliant", "allow"].includes(value)) return "success";
  if (["fail", "failed", "violation", "deny", "blocked"].includes(value)) return "critical";
  if (["review", "warning", "uncertain"].includes(value)) return "warning";
  return "neutral";
}

function evidenceButton(refs: string[]) {
  if (!refs.length) return null;
  return (
    <button
      type="button"
      className="cw-source-button"
      onClick={() => window.dispatchEvent(new CustomEvent("medflux:intelligence-evidence", { detail: { refs } }))}
    >
      Quelle anzeigen
    </button>
  );
}

export default function ContractIntelligencePanel({ contractId, organizationSlug }: Props) {
  const [state, setState] = useState<IntelligenceState>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setError(null);
    return Promise.all([
      getContractGraph(organizationSlug, contractId),
      getContractObligations(organizationSlug, contractId),
      getContractPolicies(organizationSlug, contractId),
      getContractActionProposals(organizationSlug, contractId),
    ])
      .then(([graph, obligations, policies, actions]) => {
        setState({
          relations: graph.relations ?? [],
          obligations: obligations.items ?? [],
          policies: policies.items ?? [],
          actions: actions.items ?? [],
        });
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Vertragsintelligenz konnte nicht geladen werden.");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([
      getContractGraph(organizationSlug, contractId),
      getContractObligations(organizationSlug, contractId),
      getContractPolicies(organizationSlug, contractId),
      getContractActionProposals(organizationSlug, contractId),
    ])
      .then(([graph, obligations, policies, actions]) => {
        if (!active) return;
        setState({ relations: graph.relations ?? [], obligations: obligations.items ?? [], policies: policies.items ?? [], actions: actions.items ?? [] });
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Vertragsintelligenz konnte nicht geladen werden.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [contractId, organizationSlug]);

  async function transition(item: IntelligenceActionProposal, status: "approved" | "rejected" | "executed" | "cancelled") {
    setMutatingId(item.id);
    setError(null);
    try {
      const updated = await transitionActionProposal(organizationSlug, item.id, status);
      setState((current) => ({
        ...current,
        actions: current.actions.map((action) => action.id === updated.id ? updated : action),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Handlungsvorschlag konnte nicht aktualisiert werden.");
    } finally {
      setMutatingId(null);
    }
  }

  const total = useMemo(
    () => state.relations.length + state.obligations.length + state.policies.length + state.actions.length,
    [state],
  );

  return (
    <section className="cw-section" aria-labelledby="contract-intelligence-heading">
      <div className="cw-section-head">
        <div>
          <h2 id="contract-intelligence-heading">Vertragsintelligenz</h2>
          <p>Beziehungen, Pflichten, Regelprüfungen und kontrollierte Handlungsvorschläge aus dem autoritativen Backend.</p>
        </div>
        <button type="button" className="btn-ghost" onClick={() => void load()} disabled={loading}>Aktualisieren</button>
      </div>

      {loading && <LoadingState>Vertragsintelligenz wird geladen…</LoadingState>}
      {error && <InlineAlert tone="warning" role="status">{error}</InlineAlert>}
      {!loading && total === 0 && !error && <p className="cw-muted">Für diesen Vertrag liegen noch keine zusätzlichen Intelligence-Datensätze vor.</p>}

      {!loading && total > 0 && (
        <div className={styles.grid}>
          <div className="card card-pad">
            <h3>Vertragsbeziehungen <span className="muted">({state.relations.length})</span></h3>
            {state.relations.length === 0 ? <p className="cw-muted">Keine Beziehungen erkannt.</p> : (
              <ul className={styles.list}>
                {state.relations.map((item) => <li key={item.id}>
                  <div><strong>{item.relation_type}</strong>{reviewBadge(item.requires_review)}</div>
                  {item.rationale ? <p>{item.rationale}</p> : null}
                  {item.authority ? <small>Quelle der Beziehung: {item.authority}</small> : null}
                  {evidenceButton(item.evidence_refs)}
                </li>)}
              </ul>
            )}
          </div>

          <div className="card card-pad">
            <h3>Pflichten <span className="muted">({state.obligations.length})</span></h3>
            {state.obligations.length === 0 ? <p className="cw-muted">Keine strukturierten Pflichten vorhanden.</p> : (
              <ul className={styles.list}>
                {state.obligations.map((item) => <li key={item.id}>
                  <div><strong>{item.title || item.key}</strong>{reviewBadge(item.requires_review)}</div>
                  {item.description ? <p>{item.description}</p> : null}
                  <small>{item.status}{item.due_date ? ` · fällig ${formatDate(item.due_date)}` : ""}{item.owner_role ? ` · verantwortlich: ${item.owner_role}` : ""}</small>
                  {evidenceButton([...item.evidence_refs, ...item.source_field_refs])}
                </li>)}
              </ul>
            )}
          </div>

          <div className="card card-pad">
            <h3>Regelprüfungen <span className="muted">({state.policies.length})</span></h3>
            {state.policies.length === 0 ? <p className="cw-muted">Keine Policy-Entscheidungen vorhanden.</p> : (
              <ul className={styles.list}>
                {state.policies.map((item, index) => <li key={`${item.policy_key}-${item.policy_version}-${index}`}>
                  <div><strong>{item.policy_key}</strong><StatusBadge tone={policyTone(item.outcome)} label={item.outcome} />{reviewBadge(item.requires_review)}</div>
                  {item.explanation ? <p>{item.explanation}</p> : null}
                  <small>Version {item.policy_version}</small>
                  {evidenceButton(item.evidence_refs)}
                </li>)}
              </ul>
            )}
          </div>

          <div className="card card-pad">
            <h3>Handlungsvorschläge <span className="muted">({state.actions.length})</span></h3>
            {state.actions.length === 0 ? <p className="cw-muted">Keine Handlungsvorschläge vorhanden.</p> : (
              <ul className={styles.list}>
                {state.actions.map((item) => <li key={item.id}>
                  <div><strong>{item.kind}</strong><StatusBadge tone="neutral" label={item.status} />{item.requires_human_approval ? <StatusBadge tone="warning" label="Freigabe erforderlich" /> : null}</div>
                  {item.reason ? <p>{item.reason}</p> : null}
                  {item.assignee_role ? <small>Zielrolle: {item.assignee_role}</small> : null}
                  {evidenceButton(item.evidence_refs)}
                  <div className="button-row">
                    {item.status === "proposed" ? <>
                      <button type="button" className="btn btn-sm" disabled={mutatingId === item.id} onClick={() => void transition(item, "approved")}>Freigeben</button>
                      <button type="button" className="btn-ghost" disabled={mutatingId === item.id} onClick={() => void transition(item, "rejected")}>Ablehnen</button>
                      <button type="button" className="btn-ghost" disabled={mutatingId === item.id} onClick={() => void transition(item, "cancelled")}>Stornieren</button>
                    </> : null}
                    {item.status === "approved" ? <>
                      <button type="button" className="btn btn-sm" disabled={mutatingId === item.id} onClick={() => void transition(item, "executed")}>Als ausgeführt bestätigen</button>
                      <button type="button" className="btn-ghost" disabled={mutatingId === item.id} onClick={() => void transition(item, "cancelled")}>Stornieren</button>
                    </> : null}
                  </div>
                </li>)}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
