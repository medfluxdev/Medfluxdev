"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import StatusBadge, { type StatusTone } from "@/components/ui/StatusBadge";
import { getContractRules, RULE_OUTCOME_LABEL, type ContractRuleResult, type RuleOutcome } from "@/lib/domain-api/rules";
import { usePermissions } from "@/lib/use-permissions";
import { asFixTarget, contractHref, fixLabel } from "@/lib/fix-targets";

const TONE: Record<RuleOutcome, StatusTone> = { pass: "success", fail: "critical", unknown: "warning", na: "neutral" };
const STATUS_TONE: Record<string, StatusTone> = { "Verstoß": "critical", "Unvollständig": "warning", "Erfüllt": "success" };

// Ergebnis der Vertragsregeln der Organisation für diesen Vertrag (vom System geprüft, nicht von der KI).
export default function ContractRulesSection({ organizationSlug, contractId, version }: { organizationSlug: string; contractId: string; version?: unknown }) {
  const { can } = usePermissions();
  const [data, setData] = useState<{ status: string | null; items: ContractRuleResult[] } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getContractRules(organizationSlug, contractId)
      .then((result) => { if (active) { setData(result); setFailed(false); } })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [organizationSlug, contractId, version]);

  if (failed) return null;
  if (!data) return null;
  if (data.items.length === 0) {
    return can("catalog.admin") ? <p className="cw-muted rules-empty">
      Noch keine Vertragsregeln festgelegt. <Link href="/stammdaten/vertragsregeln">Regeln festlegen</Link>, um jeden Vertrag automatisch gegen Ihre Vorgaben zu prüfen.
    </p> : null;
  }

  const relevant = data.items.filter((item) => item.outcome !== "na");
  const notApplicable = data.items.length - relevant.length;
  return <section className="cw-section" aria-labelledby="rules-heading">
    <div className="cw-section-head">
      <div><h2 id="rules-heading">Vertragsregeln</h2><p>Vom System anhand der Stammdaten geprüft.</p></div>
      {data.status ? <StatusBadge label={data.status} tone={STATUS_TONE[data.status] ?? "neutral"} /> : null}
    </div>
    {relevant.length === 0 ? <p className="cw-muted">Keine der Regeln gilt für diesen Vertrag.</p> : <ul className="rules-list">
      {relevant.map((item) => {
        // Fehlende oder verletzte Angabe: direkt zur Stelle, an der sie gepflegt wird.
        const target = item.outcome === "unknown" || item.outcome === "fail" ? asFixTarget(item.target) : null;
        return <li key={item.rule_id}>
          <StatusBadge label={RULE_OUTCOME_LABEL[item.outcome]} tone={TONE[item.outcome]} />
          <div><strong>{item.label}</strong><span>{item.detail}</span></div>
          {target ? <Link className="rg-link rules-fix" href={contractHref(contractId, target)} aria-label={`${item.label}: ${fixLabel(target)}`}>{fixLabel(target)}</Link> : null}
        </li>;
      })}
    </ul>}
    {notApplicable > 0 ? <p className="cw-muted">{notApplicable === 1 ? "1 Regel gilt" : `${notApplicable} Regeln gelten`} für diesen Vertrag nicht.</p> : null}
  </section>;
}
