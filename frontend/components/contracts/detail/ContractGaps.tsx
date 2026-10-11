"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getContractRegister, type ContractRegister } from "@/lib/domain-api/register";
import { getContractRules, type ContractRuleResult } from "@/lib/domain-api/rules";
import { getContractOwnership } from "@/lib/domain-api/ownership";
import { FINANCE_ENTRIES_TARGET, REVIEW_TARGET, asFixTarget, contractHref, registerField, type FixTarget } from "@/lib/fix-targets";

interface Gap {
  key: string;
  label: string;
  reason: string;
  target: FixTarget;
}

type Props = {
  contractId: string;
  orgSlug: string;
  /** Gepflegte jährliche Kosten vorhanden (aus der Vertragsakte). */
  hasAnnualCost: boolean;
  reviewPending: boolean;
  documentCount: number;
};

/**
 * „Was fehlt noch?“: alles, was diesem Vertrag fehlt, an einem Ort – jeder Eintrag führt direkt zur Stelle.
 * Nur aus vorhandenen, deterministischen Angaben (Pflichtfelder für „Gültig“, Laufzeit, Kosten, Zuständigkeit,
 * offene Prüfung, Dokument, Regeln ohne Angabe). Ohne Lücken erscheint nichts.
 */
export default function ContractGaps({ contractId, orgSlug, hasAnnualCost, reviewPending, documentCount }: Props) {
  const [register, setRegister] = useState<ContractRegister | null>(null);
  const [responsible, setResponsible] = useState<string | null | undefined>(undefined);
  const [rules, setRules] = useState<ContractRuleResult[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      getContractRegister(orgSlug, contractId),
      getContractOwnership(orgSlug, contractId),
      getContractRules(orgSlug, contractId),
    ]).then(([registerResult, ownershipResult, rulesResult]) => {
      if (!active) return;
      if (registerResult.status === "fulfilled") setRegister(registerResult.value);
      if (ownershipResult.status === "fulfilled") setResponsible(ownershipResult.value.responsible_account_id);
      if (rulesResult.status === "fulfilled") setRules(rulesResult.value?.items ?? []);
      setLoaded(true);
    });
    return () => { active = false; };
  }, [contractId, orgSlug]);

  if (!loaded) return null;

  const gaps: Gap[] = [];
  const seen = new Set<string>();
  const add = (gap: Gap) => {
    if (seen.has(gap.key)) return;
    seen.add(gap.key);
    gaps.push(gap);
  };
  const label = (key: string) => register?.fields[key]?.label ?? key;

  if (register) {
    if (register.business_status === "in_arbeit") {
      for (const key of register.missing_for_valid ?? []) add({ key, label: label(key), reason: "nötig für „Gültig“", target: registerField(key) });
    }
    for (const key of register.terms?.missing ?? []) add({ key, label: label(key), reason: "nötig für die Fristberechnung", target: registerField(key) });
  }
  const running = register ? !["beendet", "geloescht"].includes(register.business_status) : true;
  if (!hasAnnualCost && running) add({ key: "annual_cost", label: "Jährliche Kosten", reason: "keine Finanzeinträge gepflegt", target: FINANCE_ENTRIES_TARGET });
  if (responsible === null && running) add({ key: "responsible_account_id", label: "Verantwortliche Person", reason: "erhält Erinnerungen und Aufgaben", target: { tab: "register", field: "responsible_account_id" } });
  if (reviewPending) add({ key: "review", label: "Prüfung der KI-Werte", reason: "Werte aus dem Dokument noch nicht bestätigt", target: REVIEW_TARGET });
  if (documentCount === 0) add({ key: "document", label: "Vertragsdokument", reason: "kein Original hinterlegt", target: { tab: "documents", subtab: "attachments" } });
  for (const rule of rules) {
    const target = rule.outcome === "unknown" ? asFixTarget(rule.target) : null;
    if (target) add({ key: `rule-${rule.rule_id}`, label: rule.detail.replace(/\.$/, ""), reason: `Vertragsregel „${rule.label}“`, target });
  }

  if (gaps.length === 0) return null;
  return <section className="cw-section contract-gaps" aria-labelledby="gaps-heading">
    <div className="cw-section-head"><div>
      <h2 id="gaps-heading">Was fehlt noch?</h2>
      <p>Jeder Eintrag führt direkt zur Stelle, an der er erfasst wird.</p>
    </div></div>
    <ul className="contract-gaps-list">
      {gaps.map((gap) => <li key={gap.key}>
        <Link href={contractHref(contractId, gap.target)}>{gap.label}</Link>
        <span className="cw-muted">{gap.reason}</span>
      </li>)}
    </ul>
  </section>;
}
