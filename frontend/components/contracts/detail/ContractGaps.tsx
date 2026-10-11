"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getContractRegister, type ContractRegister } from "@/lib/domain-api/register";
import { getContractRules, type ContractRuleResult } from "@/lib/domain-api/rules";
import { getContractOwnership } from "@/lib/domain-api/ownership";
import { FINANCE_ENTRIES_TARGET, REVIEW_TARGET, asFixTarget, contractHref, registerField, type FixTarget } from "@/lib/fix-targets";

export interface Gap {
  key: string;
  label: string;
  reason: string;
  /** Befehl für Strg+K, z. B. „Vertragsbeginn erfassen“. */
  command: string;
  target: FixTarget;
}

type Input = {
  contractId: string;
  orgSlug: string;
  /** Gepflegte jährliche Kosten vorhanden (aus der Vertragsakte). */
  hasAnnualCost: boolean;
  reviewPending: boolean;
  documentCount: number;
  /** Neu laden, wenn sich die Vertragsakte ändert (z. B. nach dem Speichern). */
  version?: unknown;
};

/**
 * „Was fehlt noch?“: alles, was diesem Vertrag fehlt – nur aus vorhandenen, deterministischen Angaben
 * (Pflichtfelder für „Gültig“, Laufzeit, Kosten, Zuständigkeit, offene Prüfung, Dokument, Regeln ohne Angabe).
 * `null`, solange nichts geladen ist.
 */
export function useContractGaps({ contractId, orgSlug, hasAnnualCost, reviewPending, documentCount, version }: Input): Gap[] | null {
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
      setRegister(registerResult.status === "fulfilled" ? registerResult.value : null);
      setResponsible(ownershipResult.status === "fulfilled" ? ownershipResult.value?.responsible_account_id : undefined);
      setRules(rulesResult.status === "fulfilled" ? rulesResult.value?.items ?? [] : []);
      setLoaded(true);
    });
    return () => { active = false; };
  }, [contractId, orgSlug, version]);

  return useMemo(() => {
    if (!loaded) return null;
    const gaps: Gap[] = [];
    const seen = new Set<string>();
    const add = (gap: Gap) => {
      if (seen.has(gap.key)) return;
      seen.add(gap.key);
      gaps.push(gap);
    };
    const label = (key: string) => register?.fields?.[key]?.label ?? key;
    const field = (key: string, reason: string) => add({ key, label: label(key), reason, command: `${label(key)} erfassen`, target: registerField(key) });

    if (register) {
      if (register.business_status === "in_arbeit") for (const key of register.missing_for_valid ?? []) field(key, "nötig für „Gültig“");
      for (const key of register.terms?.missing ?? []) field(key, "nötig für die Fristberechnung");
    }
    const running = register ? !["beendet", "geloescht"].includes(register.business_status) : true;
    if (!hasAnnualCost && running) add({ key: "annual_cost", label: "Jährliche Kosten", reason: "keine Finanzeinträge gepflegt", command: "Kosten erfassen", target: FINANCE_ENTRIES_TARGET });
    if (responsible === null && running) add({ key: "responsible_account_id", label: "Verantwortliche Person", reason: "erhält Erinnerungen und Aufgaben", command: "Verantwortliche Person festlegen", target: { tab: "register", field: "responsible_account_id" } });
    if (reviewPending) add({ key: "review", label: "Prüfung der KI-Werte", reason: "Werte aus dem Dokument noch nicht bestätigt", command: "KI-Werte prüfen", target: REVIEW_TARGET });
    if (documentCount === 0) add({ key: "document", label: "Vertragsdokument", reason: "kein Original hinterlegt", command: "Vertragsdokument hinzufügen", target: { tab: "documents", subtab: "attachments" } });
    for (const rule of rules) {
      const target = rule.outcome === "unknown" ? asFixTarget(rule.target) : null;
      const text = rule.detail.replace(/\.$/, "");
      if (target) add({ key: `rule-${rule.rule_id}`, label: text, reason: `Vertragsregel „${rule.label}“`, command: `${text} – erfassen`, target });
    }
    return gaps;
  }, [documentCount, hasAnnualCost, loaded, register, responsible, reviewPending, rules]);
}

/** Karte „Was fehlt noch?“ oben in der Übersicht; ohne Lücken unsichtbar. */
export default function ContractGaps({ contractId, gaps, searchHref }: { contractId: string; gaps: Gap[] | null; searchHref?: string | null }) {
  if (!gaps || gaps.length === 0) return null;
  return <section className="cw-section contract-gaps" aria-labelledby="gaps-heading">
    <div className="cw-section-head"><div>
      <h2 id="gaps-heading">Was fehlt noch?</h2>
      <p>Jeder Eintrag führt direkt zur Stelle, an der er erfasst wird. Auch über Strg+K erreichbar.</p>
    </div>{searchHref ? <Link className="btn btn-sm" href={searchHref}>Fehlende Angaben im Dokument suchen</Link> : null}</div>
    <ul className="contract-gaps-list">
      {gaps.map((gap) => <li key={gap.key}>
        <Link href={contractHref(contractId, gap.target)}>{gap.label}</Link>
        <span className="cw-muted">{gap.reason}</span>
      </li>)}
    </ul>
  </section>;
}
