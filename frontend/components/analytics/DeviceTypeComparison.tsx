"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import CoverageValue from "@/components/ui/CoverageValue";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import Skeleton from "@/components/ui/Skeleton";
import { getDeviceTypeComparison, type DeviceTypeComparison as Report } from "@/lib/domain-api/deviceTypes";
import { FINANCE_ENTRIES_TARGET, contractHref, registerHref } from "@/lib/fix-targets";
import { formatCurrency, formatDate } from "@/lib/format";
import type { GridFilter } from "@/lib/domain-api/registerGrid";

const NO_DEVICE_TYPE: GridFilter[] = [{ column: "device_types", op: "empty" }];

/**
 * Analysen: Gerätearten vergleichen (Plan GERAETEARTEN_PLAN_20261011).
 * Übersicht je Geräteart; eine Geräteart öffnet alle laufenden Verträge nebeneinander mit Kosten je Gerät
 * (nur wenn Kosten und Anzahl gepflegt sind und der Vertrag nur diese Geräteart abdeckt).
 */
export default function DeviceTypeComparison({ organizationSlug }: { organizationSlug: string }) {
  const [deviceType, setDeviceType] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [failed, setFailed] = useState(false);

  // Aus der Adresse (?geraeteart=CT), z. B. von der früheren Geräteseite oder einem geteilten Link.
  useEffect(() => {
    try {
      const value = new URLSearchParams(window.location.search).get("geraeteart");
      if (value) setDeviceType(value);
    } catch {
      // Adresse ist nur Komfort.
    }
  }, []);

  const load = useCallback(() => {
    setReport(null);
    getDeviceTypeComparison(organizationSlug, deviceType)
      .then((data) => { setReport(data); setFailed(false); })
      .catch(() => setFailed(true));
  }, [organizationSlug, deviceType]);

  useEffect(load, [load]);

  function choose(value: string | null) {
    setDeviceType(value);
    try {
      const params = new URLSearchParams(window.location.search);
      if (value) params.set("geraeteart", value); else params.delete("geraeteart");
      const query = params.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}#geraetearten`);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  return <section className="card card-pad stack-4" id="geraetearten" aria-labelledby="device-types-heading">
    <div className="cw-section-head">
      <div><h2 id="device-types-heading">Gerätearten vergleichen</h2><p className="field-hint">Laufende Verträge je Geräteart, z. B. alle Wartungsverträge für CTs. Jährliche Kosten netto; unbekannte Kosten zählen nicht als 0.</p></div>
    </div>
    <nav aria-label="Ebene des Vergleichs" className="drill-path">
      <ol>
        <li>{deviceType === null ? <span aria-current="page">Alle Gerätearten</span> : <button type="button" className="rg-link" onClick={() => choose(null)}>Alle Gerätearten</button>}</li>
        {deviceType ? <li><span aria-current="page">{deviceType}</span></li> : null}
      </ol>
    </nav>
    {failed ? <InlineAlert tone="warning" action={<Button size="sm" onClick={load}>Erneut laden</Button>}>Der Vergleich konnte nicht geladen werden.</InlineAlert> : null}
    {!report && !failed ? <Skeleton lines={3} label="Vergleich wird geladen…" /> : null}

    {report?.level === "types" ? <>
      {report.items.length === 0
        ? <EmptyState variant="calm" title="Noch keine Verträge mit Geräteart">
          <>Ordnen Sie Verträgen eine Geräteart zu (Vertrag → Verknüpfungen → Geräte). Die Liste der Gerätearten pflegen Sie unter <Link href="/stammdaten/geraetearten">Stammdaten → Gerätearten</Link>.</>
        </EmptyState>
        : <div className="table-scroll"><table className="rg-table">
          <caption className="visually-hidden">Gerätearten</caption>
          <thead><tr><th scope="col">Geräteart</th><th scope="col">Laufende Verträge</th><th scope="col">Geräte</th><th scope="col">Jährliche Kosten</th></tr></thead>
          <tbody>{report.items.map((item) => <tr key={item.value}>
            <th scope="row"><button type="button" className="rg-link" onClick={() => choose(item.value)}>{item.label}</button></th>
            <td>{item.count}</td>
            <td>{item.devices_known || "–"}{item.devices_missing ? <span className="cw-muted"> · {item.devices_missing} ohne Anzahl</span> : null}</td>
            <td><CoverageValue value={item.annual_cost} known={item.annual_known} missing={item.annual_missing} /></td>
          </tr>)}</tbody>
        </table></div>}
      {report.without_count > 0 ? <p className="field-hint">{report.without_count} von {report.running_count} laufenden Verträgen haben noch keine Geräteart. <Link href={registerHref(NO_DEVICE_TYPE)}>Diese Verträge anzeigen</Link></p> : null}
    </> : null}

    {report?.level === "contracts" ? <>
      <p className="drill-total"><strong>{report.count} laufende {report.count === 1 ? "Vertrag" : "Verträge"}</strong> · {report.devices_known} Geräte{report.devices_missing ? ` (bei ${report.devices_missing} ohne Anzahl)` : ""} · <CoverageValue value={report.totals.value} currency={report.totals.currency} known={report.totals.known} missing={report.totals.missing} /></p>
      {report.items.length === 0 ? <p className="cw-muted">Keine laufenden Verträge für diese Geräteart.</p> : <div className="table-scroll"><table className="rg-table">
        <caption className="visually-hidden">Verträge für {report.device_type}</caption>
        <thead><tr><th scope="col">Vertrag</th><th scope="col">Vertragspartner</th><th scope="col">Bereich</th><th scope="col">Ende</th><th scope="col">Anzahl</th><th scope="col">Jährliche Kosten</th><th scope="col">Kosten je Gerät</th></tr></thead>
        <tbody>{report.items.map((item) => {
          const name = item.short_description ?? "Vertrag";
          return <tr key={item.contract_id}>
            <th scope="row"><Link href={`/contracts/${item.contract_id}`}>{item.register_number ? <span className="mono">{item.register_number}</span> : null} {name}</Link>{item.other_device_types.length ? <small className="cw-muted"> · auch {item.other_device_types.join(", ")}</small> : null}</th>
            <td>{item.partner ?? "–"}</td>
            <td>{[item.hospital, item.department].filter(Boolean).join(" › ") || "–"}</td>
            <td>{item.possible_end ? formatDate(item.possible_end) : "–"}</td>
            <td>{item.quantity ?? <Link href={contractHref(item.contract_id, { tab: "relations" })} aria-label={`Anzahl für ${name} erfassen`}>erfassen</Link>}</td>
            <td>{item.annual_cost ? formatCurrency(item.annual_cost, item.currency) : <Link href={contractHref(item.contract_id, FINANCE_ENTRIES_TARGET)} aria-label={`Kosten für ${name} erfassen`}>Kosten erfassen</Link>}</td>
            <td>{item.cost_per_device ? formatCurrency(item.cost_per_device, item.currency) : <span className="cw-muted" title={item.cost_per_device_reason ?? undefined}>nicht berechenbar<span className="visually-hidden">: {item.cost_per_device_reason}</span></span>}</td>
          </tr>;
        })}</tbody>
      </table></div>}
      {report.truncated ? <p className="field-hint">Es werden die ersten 500 Verträge gezeigt; alle stehen in der Vertragsliste.</p> : null}
      <Link href={registerHref(report.register_filter as GridFilter[])}>Diese Geräteart in der Vertragsliste öffnen (alle Status)</Link>
    </> : null}
  </section>;
}
