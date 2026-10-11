"use client";

import Link from "next/link";
import { FINANCE_ENTRIES_TARGET, contractHref, notEvaluableLink } from "@/lib/fix-targets";
import { useEffect, useState } from "react";
import { URGENCY } from "@/components/contracts/detail/ContractRenewalBrief";
import { listRenewals, type NotEvaluableItem, type RenewalListItem } from "@/lib/domain-api/registerGrid";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { formatCurrency, formatDate } from "@/lib/format";

const RANGES = [60, 120, 180, 365];

export default function RenewalOverview({ organizationSlug }: { organizationSlug: string }) {
  const [days, setDays] = useState(120);
  const [items, setItems] = useState<RenewalListItem[] | null>(null);
  const [notEvaluable, setNotEvaluable] = useState<NotEvaluableItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    listRenewals(organizationSlug, days)
      .then((result) => { if (!cancelled) { setItems(result.items); setNotEvaluable(result.not_evaluable ?? []); } })
      .catch((err) => { if (!cancelled) setError(err instanceof Error && err.message ? err.message : "Die Übersicht konnte nicht geladen werden."); });
    return () => { cancelled = true; };
  }, [days, organizationSlug]);

  const open = (items ?? []).filter((item) => !item.decision).length;

  return <section className="cw-section" aria-labelledby="renewals-heading">
    <div className="viz-head">
      <div><h2 id="renewals-heading">Anstehende Kündigungsfristen</h2>
        <p className="cw-muted">{items ? `${items.length} Verträge · ${open} ohne erfasste Entscheidung` : " "}</p></div>
      <label>Zeitraum<select value={days} onChange={(event) => setDays(Number(event.target.value))}>
        {RANGES.map((value) => <option key={value} value={value}>nächste {value} Tage</option>)}
      </select></label>
    </div>
    {error ? <p role="alert" className="rg-error">{error}</p> : null}
    {!items && !error ? <p role="status">Wird geladen…</p> : null}
    {notEvaluable.length > 0 ? <InlineAlert tone="warning">Für {notEvaluable.length} {notEvaluable.length === 1 ? "Vertrag ist" : "Verträge ist"} die Kündigungsfrist nicht berechenbar (Laufzeitangaben unvollständig) – sie fehlen in dieser Liste. <Link href={notEvaluableLink(notEvaluable)}>{notEvaluable.length === 1 ? "Laufzeitangaben ergänzen" : "Verträge anzeigen"}</Link></InlineAlert> : null}
    {items && items.length === 0 ? <EmptyState variant="calm" title="Keine fälligen Kündigungsfristen bekannt">{notEvaluable.length > 0 ? "Im gewählten Zeitraum ist keine berechenbare Frist fällig." : "Im gewählten Zeitraum ist keine Kündigungsfrist fällig."}</EmptyState> : null}
    {items && items.length > 0 ? <div className="reg-scroll"><table className="rg-table">
      <thead><tr><th scope="col">Kündbar bis</th><th scope="col">Vertrag</th><th scope="col">Partner</th><th scope="col">Jährliche Kosten</th><th scope="col">Verantwortlich</th><th scope="col">Entscheidung</th></tr></thead>
      <tbody>{items.map((item) => <tr key={item.contract_id}>
        <td>{formatDate(item.cancel_by)} <Signal tone={URGENCY[item.urgency].tone}>{item.days_left >= 0 ? `in ${item.days_left} Tagen` : "verstrichen"}</Signal></td>
        <th scope="row"><Link href={`/contracts/${item.contract_id}?tab=deadlines`}>{item.register_number ?? "–"} · {item.short_description ?? ""}</Link></th>
        <td>{item.partner ?? "–"}</td>
        <td className="num">{item.annual_cost ? formatCurrency(item.annual_cost, "EUR") : <Link href={contractHref(item.contract_id, FINANCE_ENTRIES_TARGET)} aria-label={`Kosten für ${item.register_number ?? "Vertrag"} erfassen`}>Kosten erfassen</Link>}</td>
        <td>{item.responsible ?? "–"}</td>
        <td>{item.decision ? item.decision.label : <span className="cw-muted">offen</span>}</td>
      </tr>)}</tbody>
    </table></div> : null}
  </section>;
}
