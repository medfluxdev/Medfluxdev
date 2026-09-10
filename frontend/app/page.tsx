"use client";

import { useCallback, useEffect, useState } from "react";
import ActionList from "@/components/dashboard/ActionList";
import DataQuality from "@/components/dashboard/DataQuality";
import DeadlineDistribution from "@/components/dashboard/DeadlineDistribution";
import FinancialOverview from "@/components/dashboard/FinancialOverview";
import KpiCard from "@/components/dashboard/KpiCard";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import { apiGet } from "@/lib/api";
import type { DashboardOverview } from "@/lib/dashboard-types";
import { formatDate, formatISODateOnly } from "@/lib/format";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

function FreshnessState({
  freshness,
}: {
  freshness: DashboardOverview["freshness"];
}) {
  if (!freshness) return null;
  if (freshness.data_freshness === "stale") {
    return (
      <span className="freshness-pill">
        <span className="freshness-dot" aria-hidden="true" />
        Warn-Bewertung veraltet
      </span>
    );
  }
  if (freshness.data_freshness === "none") {
    return (
      <span className="freshness-pill">
        <span className="freshness-dot poor" aria-hidden="true" />
        Noch keine Warn-Bewertung
      </span>
    );
  }
  return (
    <span className="freshness-pill">
      <span className="freshness-dot ok" aria-hidden="true" />
      Warn-Bewertung aktuell
    </span>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const today = formatISODateOnly(new Date());
      const res = await apiGet<DashboardOverview>(
        `/api/dashboard/overview?organization_slug=${encodeURIComponent(
          ORG_SLUG
        )}&as_of_date=${today}`
      );
      setData(res);
    } catch {
      setError("Dashboard konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="page">
      {error && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          {error}
        </InlineAlert>
      )}

      {loading && <LoadingState>Dashboard wird geladen…</LoadingState>}

      {!loading && !error && data && data.kpis && (
        <div className="dashboard">
          <div className="section-caption">Operative Intelligenz</div>

          <section className="intel-strip" aria-label="Kennzahlen">
            {Object.values(data.kpis).map((k) => (
              <div className="intel" key={k.label_de}>
                <KpiCard card={k} />
              </div>
            ))}
          </section>

          <section className="section-caption" style={{ marginTop: 4 }}>
            Datenstand {formatDate(data.as_of_date)}
            {data.total_action_items > 0
              ? ` · ${data.total_action_items} ${
                  data.total_action_items === 1
                    ? "Handlungspunkt"
                    : "Handlungspunkte"
                } offen`
              : " · kein akuter Handlungsbedarf"}
            {" · "}
            <FreshnessState freshness={data.freshness} />
          </section>

          <div className="dash-grid">
            <section className="panel" aria-labelledby="handlungsbedarf">
              <div className="panel-head">
                <div>
                  <h2 id="handlungsbedarf">Handlungsbedarf</h2>
                  <p>Priorisierte Aufgaben aus der lokalen Analyse</p>
                </div>
              </div>
              <ActionList items={data.action_items} total={data.total_action_items} />
            </section>

            <section className="panel" aria-labelledby="fristen">
              <div className="panel-head">
                <div>
                  <h2 id="fristen">Fristenübersicht</h2>
                  <p>Verteilungen aus den akzeptierten Berechnungen</p>
                </div>
              </div>
              <DeadlineDistribution buckets={data.deadlines} />
            </section>
          </div>

          <div className="lower-grid">
            <section className="panel" aria-labelledby="kosten">
              <div className="panel-head">
                <div>
                  <h2 id="kosten">Kostenübersicht</h2>
                  <p>Nur verlässliche, akzeptierte Werte</p>
                </div>
              </div>
              <FinancialOverview financial={data.financial} />
            </section>

            <section className="panel" aria-labelledby="datenqualitaet">
              <div className="panel-head">
                <div>
                  <h2 id="datenqualitaet">Manuelle Prüfung / Datenqualität</h2>
                  <p>Prüfungen und Bewertungen der extrahierten Angaben</p>
                </div>
              </div>
              <DataQuality items={data.data_quality} />
            </section>
          </div>
        </div>
      )}

      {!loading && !error && data && !data.kpis && (
        <div className="state-box">
          <div className="state-icon">∅</div>
          <h3>Keine Arbeitsdaten verfügbar</h3>
          <p>
            Sobald echte Vertragsdaten importiert sind, erscheinen hier
            priorisierte Aufgaben mit Risiko, Nachweis und nächster Aktion.
          </p>
        </div>
      )}
    </div>
  );
}