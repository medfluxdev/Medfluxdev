"use client";

import { useState } from "react";
import Link from "next/link";
import { queryPortfolio, type PortfolioQueryResult } from "@/lib/domain-api/intelligenceAnalytics";

export default function PortfolioQueryPanel({ organizationSlug }: { organizationSlug: string }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<PortfolioQueryResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await queryPortfolio(organizationSlug, { query: query.trim() }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Portfolio-Abfrage fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="card card-pad">
    <h2>Fragen an das Portfolio</h2>
    <p className="muted">Aus dem akzeptierten Vertragsbestand, ohne Frontend-Neuberechnung.</p>
    <label>Frage<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Welche Verträge enden?" /></label>
    <button type="button" className="btn" onClick={() => void run()} disabled={!query.trim() || busy}>{busy ? "Analysiert…" : "Analysieren"}</button>
    {error ? <p className="alert alert--critical">{error}</p> : null}
    {result ? <div><h3>{result.answer}</h3>{result.unknowns.length ? <p className="muted">{result.unknowns.join(" · ")}</p> : null}<ul>{result.matches.map((item) => <li key={item.contract_id}><Link href={`/contracts/${item.contract_id}`}>{item.contract_number ?? item.contract_id.slice(0, 8)}</Link> · {item.supplier ?? "–"} · {item.status ?? "–"}</li>)}</ul></div> : null}
  </section>;
}
