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

  async function run(text?: string) {
    const asked = (text ?? query).trim();
    if (!asked) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await queryPortfolio(organizationSlug, { query: asked }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Die Frage konnte nicht beantwortet werden.");
    } finally {
      setBusy(false);
    }
  }

  const EXAMPLES = ["Welche Verträge enden?", "Welche Verträge haben keine Kosten?", "Wer ist unser größter Lieferant?"];

  return <section className="card an-ask" aria-labelledby={`${inputId}-heading`}>
    <div className="an-ask-head">
      <h2 id={`${inputId}-heading`}>Fragen an das Portfolio</h2>
      <p>In eigenen Worten fragen – die Antwort steht hier und nennt die passenden Verträge mit Link.</p>
    </div>
    <form className="an-ask-row" onSubmit={(event) => { event.preventDefault(); void run(); }}>
      <label className="visually-hidden" htmlFor={inputId}>Frage</label>
      <span className="an-ask-field">
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></svg>
        <input id={inputId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Welche Verträge enden?" />
      </span>
      <Button type="submit" variant="primary" loading={busy} loadingLabel="Wird beantwortet…" disabled={!query.trim()}>Fragen</Button>
    </form>
    <p className="an-ask-examples"><span>Zum Beispiel:</span>{EXAMPLES.map((example) => <button key={example} type="button" className="an-chip" onClick={() => { setQuery(example); void run(example); }}>{example}</button>)}</p>
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
