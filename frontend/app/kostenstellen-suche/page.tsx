"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { listCostCenters, type CostCenterDto } from "@/lib/domain-api/organizations";

/**
 * Ahmad's review preview. No budget or forecasts are invented:
 * those features require approved hospital accounting actuals.
 */
export default function CostCenterSearchPage() {
  const { organizationSlug } = useAuth();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<CostCenterDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!organizationSlug) return;
    let active = true;
    setLoading(true);
    listCostCenters(organizationSlug).then((response) => {
      if (active) { setItems(response.items.filter((item) => item.is_active)); setError(""); }
    }).catch(() => {
      if (active) { setItems([]); setError("Kostenstellen konnten nicht geladen werden."); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [organizationSlug]);
  const found = useMemo(() =>
    query.trim() ? items.filter((x) => x.code.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) : [],
    [query, items]);
  return (
    <div className="page">
      <header className="entity-header">
        <h1>Kostenstelle suchen</h1>
        <p className="page-sub">Ahmad-Testversion · Suche nach Kostenstellennummer. Es werden nur berechtigte Stammdaten des aktuellen Arbeitsbereichs abgefragt.</p>
      </header>
      <section className="card card-pad">
        <label htmlFor="cost-center-number">Kostenstellennummer</label>
        <input id="cost-center-number" type="search" autoComplete="off" placeholder="Z. B. interne Nummer der Radiologie" value={query} onChange={(e) => setQuery(e.target.value)} />
        {loading ? <p role="status">Kostenstellen werden geladen…</p> : null}
        {error ? <p role="alert" className="alert alert--critical">{error}</p> : null}
        {!loading && query.trim() && found.length === 0 && !error ? <p>Keine passende berechtigte Kostenstelle gefunden.</p> : null}
        {!loading && found.length > 0 ? (
          <ul aria-label="Kostenstellen-Suchergebnisse">
            {found.map((item) => (
              <li key={item.id} className="card card-pad">
                <strong>{item.code} · {item.name}</strong>
                <p>Krankenhaus-/Abteilungszuordnung im aktuell berechtigten Bereich.</p>
                <p><b>Genehmigtes Budget:</b> Nicht verfügbar · <b>Ist-Kosten:</b> Nicht verfügbar · <b>Prognose:</b> Noch nicht implementiert</p>
                <p className="muted small">Budget und Ist-Kosten müssen aus verifizierten Krankenhaus-Finanzdaten importiert werden; Vertragswerte sind keine genehmigten Budgets.</p>
                <Link href="/analysen">Vorhandene Vertragsanalysen öffnen</Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section className="card card-pad">
        <h2>Für die vollständige Kostenstellenanalyse noch erforderlich</h2>
        <p>Freigegebene Budget- und Ist-Buchungen je Monat/Jahr, Kostenstellenzuordnung gemeinsamer Verträge sowie Prognose-Validierung anhand historischer Daten.</p>
        <p>Ohne solche Daten zeigt MedFlux bewusst keine erfundenen Budgetwerte oder scheinbar exakten Prognosen an.</p>
        <Link href="/ahmad-review">Zur Abnahme-Checkliste</Link>
      </section>
    </div>
  );
}
