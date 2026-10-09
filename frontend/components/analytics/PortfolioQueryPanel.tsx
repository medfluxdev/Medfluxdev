"use client";

import { useId, useState } from "react";
import Link from "next/link";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { queryPortfolio, type PortfolioQueryResult } from "@/lib/domain-api/intelligenceAnalytics";

// Frage in eigenen Worten an den Vertragsbestand; die Antwort nennt die passenden Verträge mit Link.
export default function PortfolioQueryPanel({ organizationSlug }: { organizationSlug: string }) {
  const inputId = useId();
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
      setError(err instanceof Error ? err.message : "Die Frage konnte nicht beantwortet werden.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="card card-pad" aria-labelledby={`${inputId}-heading`}>
    <div className="section-head">
      <div>
        <h2 id={`${inputId}-heading`}>Fragen an das Portfolio</h2>
        <p>In eigenen Worten fragen, z. B. „Welche Verträge enden?“ – die Antwort nennt die passenden Verträge mit Link.</p>
      </div>
    </div>
    <form className="query-row" onSubmit={(event) => { event.preventDefault(); void run(); }}>
      <label className="visually-hidden" htmlFor={inputId}>Frage</label>
      <input id={inputId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Welche Verträge enden?" />
      <Button type="submit" variant="primary" loading={busy} loadingLabel="Wird beantwortet…" disabled={!query.trim()}>Fragen</Button>
    </form>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {result ? <div className="query-result" role="status">
      <h3>{result.answer}</h3>
      {result.unknowns.length ? <p className="field-hint">{result.unknowns.join(" · ")}</p> : null}
      {result.matches.length ? <ul>{result.matches.map((item) => <li key={item.contract_id}>
        <Link href={`/contracts/${item.contract_id}`}>{item.contract_number ?? item.contract_id.slice(0, 8)}</Link>
        {item.supplier ? ` · ${item.supplier}` : ""}
      </li>)}</ul> : null}
    </div> : null}
  </section>;
}
