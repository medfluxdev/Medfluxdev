"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MouseEvent } from "react";
import type { ContractListItem } from "@/lib/contract-types";
import {
  RISK_LABEL,
  STATUS_LABEL,
  formatAnnualCost,
  formatDate,
} from "@/lib/format";

interface Props {
  items: ContractListItem[];
  extraHeader?: string;
  extra?: (item: ContractListItem) => React.ReactNode;
}

const severityLabel: Record<string, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
};

function EmptyRow({ colSpan }: { colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="contracts-empty">
        Keine Verträge gefunden. Passen Sie Ihre Suche oder Filter an.
      </td>
    </tr>
  );
}

export default function ContractTable({ items, extraHeader, extra }: Props) {
  const router = useRouter();
  const colSpan = extra ? 10 : 9;
  if (items.length === 0) {
    return (
      <table className="contract-table">
        <thead>
          <ContractHeaderRow extraHeader={extraHeader} />
        </thead>
        <tbody>
          <EmptyRow colSpan={colSpan} />
        </tbody>
      </table>
    );
  }

  return (
    <table className="contract-table">
      <thead>
        <ContractHeaderRow extraHeader={extraHeader} />
      </thead>
      <tbody>
        {items.map((c) => {
          const statusLabel = STATUS_LABEL[c.status ?? ""] ?? c.status;
          const riskLabel = RISK_LABEL[c.risk_level ?? ""] ?? c.risk_level;
          const w = c.primary_warning;

          function openContract360(e: MouseEvent<HTMLTableRowElement>) {
            const target = e.target as HTMLElement;
            // Interaktive Elemente (Links, Buttons, Felder) behalten ihre
            // eigene Aktion – der Zeilen-Klick navigiert nur auf freier Fläche.
            if (
              target.closest(
                "a, button, input, select, textarea, [role='button']"
              )
            ) {
              return;
            }
            router.push(`/contracts/${c.contract_id}`);
          }

          return (
            <tr
              key={c.contract_id}
              className="contract-row"
              onClick={openContract360}
            >
              <th scope="row" className="contract-number">
                <Link
                  href={`/contracts/${c.contract_id}`}
                  className="contract-number-link"
                  aria-label={`${c.contract_number ?? "Vertrag"} öffnen`}
                >
                  {c.contract_number ?? "–"}
                </Link>
              </th>
              <td className="contract-title">
                <Link
                  href={`/contracts/${c.contract_id}`}
                  className="contract-title-link"
                  aria-label={`${c.contract_title ?? "Vertrag"} öffnen`}
                >
                  {c.contract_title ?? "–"}
                </Link>
                {c.supplier && (
                  <span className="contract-supplier">{c.supplier}</span>
                )}
              </td>
              <td>{c.supplier ?? "–"}</td>
              <td>
                <span className={`badge badge-${c.status ?? "unknown"}`}>
                  {statusLabel}
                </span>
              </td>
              <td>
                {c.risk_level ? (
                  <span className={`risk-badge risk-${c.risk_level}`}>
                    {riskLabel}
                  </span>
                ) : (
                  "–"
                )}
              </td>
              <td
                className={
                  c.annual_cost?.unreliable ? "cost unreliable" : "cost"
                }
              >
                {formatAnnualCost(c.annual_cost)}
              </td>
              <td>{formatDate(c.contract_end_date)}</td>
              <td>{formatDate(c.latest_cancellation_date)}</td>
              <td className="warning-cell">
                {w?.title_de ? (
                  <>
                    <span className={`severity-tag severity-${w.severity}`}>
                      {severityLabel[w.severity ?? ""] ?? w.severity}
                    </span>
                    <span className="warning-title">{w.title_de}</span>
                  </>
                ) : (
                  "–"
                )}
              </td>
              {extra && (
                <td className="row-actions">{extra(c)}</td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ContractHeaderRow({ extraHeader }: { extraHeader?: string }) {
  return (
    <tr>
      <th scope="col">Nr.</th>
      <th scope="col">Vertrag</th>
      <th scope="col">Lieferant</th>
      <th scope="col">Status</th>
      <th scope="col">Risiko</th>
      <th scope="col">Jährl. Kosten</th>
      <th scope="col">Vertragsende</th>
      <th scope="col">Künd. bis</th>
      <th scope="col">Warnung</th>
      {extraHeader && <th scope="col">{extraHeader}</th>}
    </tr>
  );
}
