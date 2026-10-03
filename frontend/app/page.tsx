"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import ActionList from "@/components/dashboard/ActionList";
import DataQuality from "@/components/dashboard/DataQuality";
import DeadlineDistribution from "@/components/dashboard/DeadlineDistribution";
import FinancialOverview from "@/components/dashboard/FinancialOverview";
import KpiCard from "@/components/dashboard/KpiCard";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import { useAuth } from "@/components/auth/AuthProvider";
import { getDashboardOverview } from "@/lib/domain-api/dashboard";
import type { DashboardOverview } from "@/lib/dashboard-types";
import { formatDate, formatISODateOnly } from "@/lib/format";

const KPI_LINKS: Record<string, string> = {
  active_contracts: "/contracts?status=active",
  expiring_soon: "/contracts?warning_type=contract_end_approaching",
  critical_cancellation: "/contracts?critical_cancellation=true",
};

function FreshnessState({ freshness }: { freshness: DashboardOverview["freshness"] }) {
  if (!freshness) return null;
  if (freshness.data_freshness === "stale") {
    return <span className="freshness-pill"><span className="freshness-dot" aria-hidden="true" />Warn-Bewertung veraltet</span>;
  }
  if (freshness.data_freshness === "none") {
    return <span className="freshness-pill"><span className="freshness-dot poor" aria-hidden="true" />Noch keine Warn-Bewertung</span>;
  }
  return <span className="freshness-pill"><span className="freshness-dot ok" aria-hidden="true" />Warn-Bewertung aktuell</span>;
}

function PanelIcon({ tone, children }: { tone: "blue" | "green" | "violet" | "amber"; children: React.ReactNode }) {
  return <span className={`dashboard-panel-icon dashboard-panel-icon-${tone}`} aria-hidden="true">{children}</span>;
}

export default function DashboardPage() {
  const { organizationSlug } = useAuth();
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!organizationSlug) return;
    setLoading(true);
    setError(null);
    try {
      const today = formatISODateOnly(new Date());
      const res = await getDashboardOverview(organizationSlug, today);
      setData(res);
    } catch {
      setError("Dashboard konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="page dashboard-page">
      {error && (
        <InlineAlert tone="critical" role="alert" action={<Button size="sm" onClick={() => void load()}>Erneut laden</Button>}>
          {error}
        </InlineAlert>
      )}

      {loading && <LoadingState>Dashboard wird geladen…</LoadingState>}

      {!loading && !error && data && data.kpis && (
        <div className="dashboard dashboard-reference-layout">
          <section className="welcome-hero" aria-labelledby="welcome-heading">
            <div>
              <h2 id="welcome-heading">Willkommen im intelligenten Vertragsmanagement</h2>
              <p>Priorisieren Sie offene Fristen, Prüfungen und verlässliche Vertragskosten.</p>
              <Link href="/import" className="hero-action"><span aria-hidden="true">+</span>Neuen Vertrag hinzufügen</Link>
            </div>
          </section>

          <section className="section-caption dashboard-data-state" aria-label="Datenstand">
            Datenstand {formatDate(data.as_of_date)}
            {data.total_action_items > 0
              ? ` · ${data.total_action_items} ${data.total_action_items === 1 ? "Handlungspunkt" : "Handlungspunkte"} offen`
              : " · kein akuter Handlungsbedarf"}
            {" · "}<FreshnessState freshness={data.freshness} />
          </section>

          <section className="intel-strip dashboard-kpi-strip" aria-label="Kennzahlen">
            {Object.entries(data.kpis)
              .filter(([, card]) => card.label_de !== "Gesamtvertragswert")
              .map(([key, card]) => (
                <div className="intel" key={key}>
                  <KpiCard card={card} href={KPI_LINKS[key]} />
                </div>
              ))}
          </section>

          <div className="lower-grid dashboard-card-grid">
            <section className="panel dashboard-feature-card" aria-labelledby="kosten">
              <div className="panel-head dashboard-feature-head">
                <div className="dashboard-feature-title">
                  <PanelIcon tone="green">€</PanelIcon>
                  <div><h2 id="kosten">Kostenübersicht</h2><p>Nur verlässliche Werte; unbekannt bleibt unbekannt</p></div>
                </div>
              </div>
              <FinancialOverview financial={data.financial} />
            </section>

            <section className="panel dashboard-feature-card" aria-labelledby="datenqualitaet">
              <div className="panel-head dashboard-feature-head">
                <div className="dashboard-feature-title">
                  <PanelIcon tone="violet">✓</PanelIcon>
                  <div><h2 id="datenqualitaet">Manuelle Prüfung / Datenqualität</h2><p>Offene Prüfungen und Datenlücken</p></div>
                </div>
              </div>
              <DataQuality items={data.data_quality} />
              {data.data_quality.length > 0 && <div className="dashboard-card-footer"><Link href="/contracts?requires_review=true">Verträge mit Prüfbedarf anzeigen →</Link></div>}
            </section>
          </div>

          <div className="dash-grid dashboard-card-grid dashboard-priority-grid">
            <section className="panel dashboard-feature-card dashboard-priority-card" aria-labelledby="handlungsbedarf">
              <div className="panel-head dashboard-feature-head">
                <div className="dashboard-feature-title">
                  <PanelIcon tone="amber">!</PanelIcon>
                  <div><h2 id="handlungsbedarf">Handlungsbedarf</h2><p>Kritische Aufgaben und Prüfungen zuerst</p></div>
                </div>
                <span className="dashboard-count-pill"><strong>{data.total_action_items}</strong>offene {data.total_action_items === 1 ? "Punkt" : "Punkte"}</span>
              </div>
              <ActionList items={data.action_items} total={data.total_action_items} />
            </section>

            <section className="panel dashboard-feature-card dashboard-priority-card" aria-labelledby="fristen">
              <div className="panel-head dashboard-feature-head">
                <div className="dashboard-feature-title">
                  <PanelIcon tone="blue">◷</PanelIcon>
                  <div><h2 id="fristen">Fristenübersicht</h2><p>Kündigungsfristen getrennt von Vertragsenden</p></div>
                </div>
              </div>
              <DeadlineDistribution buckets={data.deadlines} />
            </section>
          </div>
        </div>
      )}

      {!loading && !error && data && !data.kpis && (
        <div className="state-box">
          <div className="state-icon">∅</div>
          <h3>Keine Arbeitsdaten verfügbar</h3>
          <p>Sobald echte Vertragsdaten importiert sind, erscheinen hier priorisierte Aufgaben mit Risiko, Nachweis und nächster Aktion.</p>
        </div>
      )}
    </div>
  );
}
