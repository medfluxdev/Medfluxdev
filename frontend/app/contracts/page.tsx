"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import ContractTable from "@/components/contracts/ContractTable";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { apiGet } from "@/lib/api";
import type {
  ContractListResponse,
  ContractsQuery,
} from "@/lib/contract-types";
import {
  RISK_LABEL,
  STATUS_LABEL,
  formatAnnualCost,
  formatDate,
} from "@/lib/format";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";
const PAGE_SIZES = [25, 50, 100] as const;

const DEFAULT_QUERY: ContractsQuery = {
  q: "",
  status: [],
  risk: [],
  warning_type: [],
  requires_action: null,
  requires_review: null,
  critical_cancellation: null,
  automatic_renewal: null,
  archived: null,
  supplier: "",
  contract_number: "",
  currency: "",
  annual_cost_min: "",
  annual_cost_max: "",
  start_date_from: "",
  start_date_to: "",
  end_date_from: "",
  end_date_to: "",
  cancellation_from: "",
  cancellation_to: "",
  sort: "operational",
  direction: "asc",
  page: 1,
  page_size: 25,
};

const QUICK_FILTERS: {
  key: "critical_cancellation" | "automatic_renewal" | "requires_action" | "requires_review" | "expiring_soon";
  label: string;
}[] = [
  { key: "critical_cancellation", label: "Kritische Kündigungsfrist" },
  { key: "automatic_renewal", label: "Automatische Verlängerung" },
  { key: "requires_action", label: "Handlungsbedarf" },
  { key: "requires_review", label: "Manuelle Prüfung" },
  { key: "expiring_soon", label: "Endet bald" },
];

function parseQuery(sp: URLSearchParams): ContractsQuery {
  const split = (k: string) => sp.getAll(k);
  const first = (k: string) => sp.get(k) ?? "";
  const asDate = (k: string) => sp.get(k) ?? "";
  const page = Number(sp.get("page") ?? "1");
  const pageSize = Number(sp.get("page_size") ?? "25");
  const direction = sp.get("direction") === "desc" ? "desc" : "asc";
  return {
    q: first("q"),
    status: split("status"),
    risk: split("risk"),
    warning_type: split("warning_type"),
    requires_action: sp.get("requires_action") === "true" ? true : sp.get("requires_action") === "false" ? false : null,
    requires_review: sp.get("requires_review") === "true" ? true : sp.get("requires_review") === "false" ? false : null,
    critical_cancellation: sp.get("critical_cancellation") === "true" ? true : sp.get("critical_cancellation") === "false" ? false : null,
    automatic_renewal: sp.get("automatic_renewal") === "true" ? true : sp.get("automatic_renewal") === "false" ? false : null,
    archived: sp.get("archived") === "true" ? true : sp.get("archived") === "false" ? false : null,
    supplier: first("supplier"),
    contract_number: first("contract_number"),
    currency: first("currency"),
    annual_cost_min: first("annual_cost_min"),
    annual_cost_max: first("annual_cost_max"),
    start_date_from: asDate("start_date_from"),
    start_date_to: asDate("start_date_to"),
    end_date_from: asDate("end_date_from"),
    end_date_to: asDate("end_date_to"),
    cancellation_from: asDate("cancellation_from"),
    cancellation_to: asDate("cancellation_to"),
    sort: first("sort") || "operational",
    direction,
    page: Number.isFinite(page) && page > 0 ? page : 1,
    page_size: (PAGE_SIZES as readonly number[]).includes(pageSize) ? (pageSize as ContractsQuery["page_size"]) : 25,
  };
}

function buildParams(q: ContractsQuery): URLSearchParams {
  const p = new URLSearchParams();
  if (q.q) p.set("q", q.q);
  q.status.forEach((v) => p.append("status", v));
  q.risk.forEach((v) => p.append("risk", v));
  q.warning_type.forEach((v) => p.append("warning_type", v));
  if (q.requires_action !== null) p.set("requires_action", String(q.requires_action));
  if (q.requires_review !== null) p.set("requires_review", String(q.requires_review));
  if (q.critical_cancellation !== null) p.set("critical_cancellation", String(q.critical_cancellation));
  if (q.automatic_renewal !== null) p.set("automatic_renewal", String(q.automatic_renewal));
  if (q.archived !== null) p.set("archived", String(q.archived));
  if (q.supplier) p.set("supplier", q.supplier);
  if (q.contract_number) p.set("contract_number", q.contract_number);
  if (q.currency) p.set("currency", q.currency);
  if (q.annual_cost_min) p.set("annual_cost_min", q.annual_cost_min);
  if (q.annual_cost_max) p.set("annual_cost_max", q.annual_cost_max);
  if (q.start_date_from) p.set("start_date_from", q.start_date_from);
  if (q.start_date_to) p.set("start_date_to", q.start_date_to);
  if (q.end_date_from) p.set("end_date_from", q.end_date_from);
  if (q.end_date_to) p.set("end_date_to", q.end_date_to);
  if (q.cancellation_from) p.set("cancellation_from", q.cancellation_from);
  if (q.cancellation_to) p.set("cancellation_to", q.cancellation_to);
  if (q.sort !== "operational") p.set("sort", q.sort);
  if (q.direction !== "asc") p.set("direction", q.direction);
  if (q.page > 1) p.set("page", String(q.page));
  if (q.page_size !== 25) p.set("page_size", String(q.page_size));
  return p;
}

export default function ContractsPage() {
  return (
    <Suspense>
      <ContractsInner />
    </Suspense>
  );
}

function ContractsInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsStr = searchParams.toString();

  const [data, setData] = useState<ContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const requestId = useRef(0);
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;

  const commit = useCallback((next: ContractsQuery) => {
    const params = buildParams(next);
    const qs = params.toString();
    router.replace(`${pathnameRef.current}${qs ? `?${qs}` : ""}`, {
      scroll: false,
    });
  }, [router]);

  const current = searchParamsStr
    ? parseQuery(new URLSearchParams(searchParamsStr))
    : DEFAULT_QUERY;

  // Fetch bei Aenderung der URL (deckt Eingaben, Filter, Back/Forward ab).
  useEffect(() => {
    const q = current;
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    const api = new URLSearchParams();
    api.set("organization_slug", ORG_SLUG);
    for (const [k, v] of buildParams(q)) api.append(k, v);
    apiGet<ContractListResponse>(`/api/contracts?${api.toString()}`, undefined)
      .then((res) => {
        if (requestId.current === id) setData(res);
      })
      .catch(() => {
        if (requestId.current === id)
          setError("Vertragsliste konnte nicht geladen werden.");
      })
      .finally(() => {
        if (requestId.current === id) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParamsStr, reloadTick]);

  // Debounce fuer die Freitext-Suche.
  const debounceRef = useRef<number | null>(null);
  const onSearchInput = useCallback(
    (value: string) => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        commit({ ...current, q: value, page: 1 });
      }, 300);
    },
    [commit, current]
  );

  const applyImmediate = useCallback(
    (patch: Partial<ContractsQuery>) => {
      commit({ ...current, ...patch });
    },
    [commit, current]
  );

  const toggleList = useCallback(
    (key: "status" | "risk" | "warning_type", value: string) => {
      const list = current[key];
      const next = list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value];
      applyImmediate({ [key]: next, page: 1 } as Partial<ContractsQuery>);
    },
    [applyImmediate, current]
  );

  const toggleBool = useCallback(
    (key: "requires_action" | "requires_review" | "critical_cancellation" | "automatic_renewal") => {
      const cur = current[key];
      const next: boolean | null = cur === true ? null : true;
      applyImmediate({ [key]: next, page: 1 } as Partial<ContractsQuery>);
    },
    [applyImmediate, current]
  );

  const resetAll = useCallback(() => {
    commit(DEFAULT_QUERY);
  }, [commit]);

  const total = data?.total_count ?? 0;
  const uniqueFilters =
    (current.q ? 1 : 0) +
    current.status.length +
    current.risk.length +
    current.warning_type.length +
    (current.requires_action !== null ? 1 : 0) +
    (current.requires_review !== null ? 1 : 0) +
    (current.critical_cancellation !== null ? 1 : 0) +
    (current.automatic_renewal !== null ? 1 : 0) +
    (current.supplier ? 1 : 0) +
    (current.contract_number ? 1 : 0) +
    (current.currency ? 1 : 0) +
    (current.annual_cost_min || current.annual_cost_max ? 1 : 0) +
    (current.start_date_from || current.start_date_to ? 1 : 0) +
    (current.end_date_from || current.end_date_to ? 1 : 0) +
    (current.cancellation_from || current.cancellation_to ? 1 : 0);

  return (
    <div className="page">
      <PageHeader
        title="Verträge"
        description={
          <>
            {total} {total === 1 ? "Vertrag" : "Verträge"}
            {current.q && <> für Suche „{current.q}“</>}
            {data?.freshness.data_freshness === "stale" && (
              <>
                {" "}
                · Warnungen bewertet zum{" "}
                {formatDate(data.freshness.warning_evaluation_as_of_date)}{" "}
                (veraltet)
              </>
            )}
            {uniqueFilters > 0 && (
              <span>
                {" "}
                · {uniqueFilters}{" "}
                {uniqueFilters === 1 ? "aktiver Filter" : "aktive Filter"} gesetzt
              </span>
            )}
          </>
        }
      />

      <section
        className="contracts-search"
        aria-label="Verträge suchen und filtern"
      >
        <form
          role="search"
          className="search-row"
          onSubmit={(e) => e.preventDefault()}
        >
          <label className="sr-text" htmlFor="contract-search">
            Verträge durchsuchen
          </label>
          <input
            id="contract-search"
            type="search"
            placeholder="Nach Nr., Titel, Lieferant oder Gerät suchen…"
            defaultValue={current.q}
            onChange={(e) => onSearchInput(e.target.value)}
          />
          <button type="button" onClick={() => onSearchInput("")} className="btn-ghost">
            Zurücksetzen
          </button>
          <button
            type="button"
            className="btn-ghost"
            aria-expanded={showAdvanced}
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Erweiterte Filter ausblenden" : "Erweiterte Filter"}
          </button>
        </form>

        <div className="quick-filters" role="group" aria-label="Schnellfilter">
          {QUICK_FILTERS.map((qf) => {
            const active =
              qf.key === "expiring_soon"
                ? current.status.includes("expiring_soon")
                : current[qf.key] === true;
            return (
              <button
                key={qf.key}
                type="button"
                aria-pressed={active}
                className={`chip${active ? " active" : ""}`}
                onClick={() =>
                  qf.key === "expiring_soon"
                    ? toggleList("status", "expiring_soon")
                    : toggleBool(qf.key)
                }
              >
                {qf.label}
              </button>
            );
          })}
          <button
            key="reset"
            type="button"
            className="chip chip-reset"
            disabled={uniqueFilters === 0}
            onClick={resetAll}
          >
            Alle Filter zurücksetzen
          </button>
        </div>

        {showAdvanced && (
          <div className="advanced-filters">
            <fieldset className="filter-group">
              <legend>Status</legend>
              {Object.entries(STATUS_LABEL).map(([v, label]) => (
                <label key={v} className="filter-check">
                  <input
                    type="checkbox"
                    checked={current.status.includes(v)}
                    onChange={() => toggleList("status", v)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>

            <fieldset className="filter-group">
              <legend>Risiko</legend>
              {Object.entries(RISK_LABEL).map(([v, label]) => (
                <label key={v} className="filter-check">
                  <input
                    type="checkbox"
                    checked={current.risk.includes(v)}
                    onChange={() => toggleList("risk", v)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>

            <div className="filter-group">
              <label htmlFor="f-supplier">Lieferant</label>
              <input
                id="f-supplier"
                type="text"
                value={current.supplier}
                onChange={(e) => applyImmediate({ supplier: e.target.value, page: 1 })}
              />
            </div>

            <div className="filter-group">
              <label htmlFor="f-contract-number">Vertragsnummer</label>
              <input
                id="f-contract-number"
                type="text"
                value={current.contract_number}
                placeholder="z. B. V-2024-001"
                onChange={(e) => applyImmediate({ contract_number: e.target.value, page: 1 })}
              />
            </div>

            <div className="filter-group">
              <label htmlFor="f-currency">Währung</label>
              <input
                id="f-currency"
                type="text"
                value={current.currency}
                onChange={(e) => applyImmediate({ currency: e.target.value, page: 1 })}
              />
            </div>

            <div className="filter-group">
              <span className="group-legend">Vertragsbeginn</span>
              <div className="date-range">
                <label htmlFor="f-start-from" className="sr-text">Von</label>
                <input id="f-start-from" type="date" value={current.start_date_from}
                  onChange={(e) => applyImmediate({ start_date_from: e.target.value, page: 1 })} />
                <label htmlFor="f-start-to" className="sr-text">Bis</label>
                <input id="f-start-to" type="date" value={current.start_date_to}
                  onChange={(e) => applyImmediate({ start_date_to: e.target.value, page: 1 })} />
              </div>
            </div>

            <div className="filter-group">
              <span className="group-legend">Kündigungsfrist</span>
              <div className="date-range">
                <label htmlFor="f-cancel-from" className="sr-text">Von</label>
                <input id="f-cancel-from" type="date" value={current.cancellation_from}
                  onChange={(e) => applyImmediate({ cancellation_from: e.target.value, page: 1 })} />
                <label htmlFor="f-cancel-to" className="sr-text">Bis</label>
                <input id="f-cancel-to" type="date" value={current.cancellation_to}
                  onChange={(e) => applyImmediate({ cancellation_to: e.target.value, page: 1 })} />
              </div>
            </div>

            <div className="filter-group">
              <span className="group-legend">Jährliche Kosten</span>
              <div className="cost-range">
                <label htmlFor="f-cost-min" className="sr-text">Minimum</label>
                <input id="f-cost-min" type="number" placeholder="Min"
                  value={current.annual_cost_min}
                  onChange={(e) => applyImmediate({ annual_cost_min: e.target.value, page: 1 })} />
                <label htmlFor="f-cost-max" className="sr-text">Maximum</label>
                <input id="f-cost-max" type="number" placeholder="Max"
                  value={current.annual_cost_max}
                  onChange={(e) => applyImmediate({ annual_cost_max: e.target.value, page: 1 })} />
              </div>
            </div>

            <div className="filter-group">
              <span className="group-legend">Vertragsende</span>
              <div className="date-range">
                <label htmlFor="f-end-from" className="sr-text">Von</label>
                <input id="f-end-from" type="date" value={current.end_date_from}
                  onChange={(e) => applyImmediate({ end_date_from: e.target.value, page: 1 })} />
                <label htmlFor="f-end-to" className="sr-text">Bis</label>
                <input id="f-end-to" type="date" value={current.end_date_to}
                  onChange={(e) => applyImmediate({ end_date_to: e.target.value, page: 1 })} />
              </div>
            </div>
          </div>
        )}
      </section>

      {error && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => setReloadTick((n) => n + 1)}>Erneut laden</button>}>
          {error}
        </InlineAlert>
      )}

      {loading && <LoadingState>Verträge werden geladen…</LoadingState>}

      {!loading && !error && data && data.total_count === 0 && (
        <div className="state-box">
          <div className="state-icon">∅</div>
          <h3>Keine Verträge gefunden</h3>
          <p>
            {uniqueFilters > 0 || current.q
              ? "Keine Verträge für die gewählten Filter gefunden."
              : "Noch keine Verträge vorhanden."}
          </p>
        </div>
      )}

      {!loading && !error && data && data.total_count > 0 && (
        <section className="panel contracts-body" aria-label="Vertragsliste">
          <div className="contracts-toolbar">
            <select
              aria-label="Sortierung"
              value={current.sort}
              onChange={(e) => applyImmediate({ sort: e.target.value, page: 1 })}
            >
              <option value="operational">Empfohlene Sortierung</option>
              <option value="title">Titel</option>
              <option value="supplier">Lieferant</option>
              <option value="end_date">Vertragsende</option>
              <option value="cancellation_date">Kündigungsfrist</option>
              <option value="annual_cost">Jährliche Kosten</option>
              <option value="risk">Risiko</option>
              <option value="updated_at">Zuletzt aktualisiert</option>
            </select>
            <button
              type="button"
              className="btn-ghost"
              onClick={() =>
                applyImmediate({
                  direction: current.direction === "asc" ? "desc" : "asc",
                })
              }
            >
              {current.direction === "asc" ? "Aufsteigend ↑" : "Absteigend ↓"}
            </button>
            <select
              aria-label="Einträge pro Seite"
              value={current.page_size}
              onChange={(e) =>
                applyImmediate({ page_size: Number(e.target.value) as ContractsQuery["page_size"], page: 1 })
              }
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s} pro Seite
                </option>
              ))}
            </select>
          </div>

          <ContractTable items={data.items} />

          <nav className="contracts-pagination" aria-label="Seitennavigation">
            <button
              type="button"
              disabled={data.page <= 1}
              onClick={() => applyImmediate({ page: data.page - 1 })}
            >
              ← Zurück
            </button>
            <span>
              Seite {data.page}
              {data.has_more || data.page > 1
                ? ` von ${Math.max(1, Math.ceil(data.total_count / data.page_size))}`
                : ""}
            </span>
            <button
              type="button"
              disabled={!data.has_more}
              onClick={() => applyImmediate({ page: data.page + 1 })}
            >
              Weiter →
            </button>
          </nav>
        </section>
      )}
    </div>
  );
}