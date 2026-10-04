"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getContentSearchStatus, searchContents, type ContentSearchResult } from "@/lib/domain-api/registerGrid";

const EXAMPLES = ["24/7 Hotline", "Reaktionszeit", "Fernwartung", "Preisanpassung", "Auftragsverarbeitung"];

export default function ContentSearch({ organizationSlug }: { organizationSlug: string }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ContentSearchResult | null>(null);
  const [status, setStatus] = useState<{ documents: number; indexed: number; without_text: number; semantic_model: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q");
    if (initial) void run(initial);
    // Nur beim ersten Laden: Suchbegriff aus der Befehlspalette uebernehmen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    getContentSearchStatus(organizationSlug).then((value) => { if (!cancelled) setStatus(value); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [organizationSlug, result]);

  async function run(term: string) {
    const q = term.trim();
    if (!q) return;
    setQuery(q);
    setLoading(true);
    setError(null);
    try {
      setResult(await searchContents(organizationSlug, q));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Suche ist fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }

  return <div className="rg-panel">
    <form className="cw-section search-form" role="search" aria-label="In Vertragsinhalten suchen" onSubmit={(event) => { event.preventDefault(); void run(query); }}>
      <label htmlFor="content-query">Suchbegriff</label>
      <div className="search-row">
        <input id="content-query" type="search" maxLength={200} value={query} placeholder="z. B. 24/7 Hotline oder &quot;Reaktionszeit 4 Stunden&quot;" onChange={(event) => setQuery(event.target.value)} />
        <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>{loading ? "Sucht…" : "Suchen"}</button>
      </div>
      <p className="cw-muted">
        Durchsucht den Text aller Vertragsdokumente lokal auf diesem Rechner – mit Wortstamm, Teilwörtern und Fachsynonymen.
        Phrasen in Anführungszeichen werden genau gesucht.{" "}
        {status ? `${status.indexed} von ${status.documents} Dokumenten durchsuchbar${status.without_text ? `, ${status.without_text} ohne lesbaren Text (z. B. Scan ohne Texterkennung)` : ""}. ` : ""}
        {status?.semantic_model ? `Inhaltliche Ähnlichkeit über das lokale Modell „${status.semantic_model}“ aktiv.` : "Inhaltliche Ähnlichkeitssuche ist aus (kein lokales Embedding-Modell eingerichtet)."}
      </p>
      <div className="rg-actions">{EXAMPLES.map((example) => <button key={example} type="button" className="rg-link" onClick={() => void run(example)}>{example}</button>)}</div>
    </form>

    {error ? <p role="alert" className="rg-error">{error}</p> : null}

    {result ? <section className="cw-section" aria-labelledby="search-results-heading" aria-busy={loading}>
      <div className="cw-section-head"><div>
        <h2 id="search-results-heading">{result.items.length === 0 ? "Keine Treffer" : `${result.items.length} Verträge gefunden`}</h2>
        {result.terms.some((term) => term.alternatives.length > 0) ? <p>Auch gesucht: {result.terms.filter((term) => term.alternatives.length > 0).map((term) => `${term.term} → ${term.alternatives.join(", ")}`).join(" · ")}</p> : null}
      </div></div>
      <ol className="search-results">
        {result.items.map((item) => <li key={item.contract_id}>
          <h3><Link href={`/contracts/${item.contract_id}?tab=register`}>{item.register_number ?? "–"} · {item.short_description ?? "Vertrag"}</Link></h3>
          <ul>
            {item.hits.map((hit) => <li key={`${hit.document_version_id}-${hit.page}`}>
              <p className="search-snippet">{hit.snippet}</p>
              <p className="cw-muted">
                {hit.document}{hit.document_valid ? "" : " (ungültig)"} · Seite {hit.page}{hit.match === "semantic" ? " · inhaltlich ähnlich" : ""}
                {" · "}<Link href={`/contracts/${item.contract_id}?tab=documents&subtab=document&source_document=${encodeURIComponent(hit.document_version_id)}&source_page=${hit.page}`}>Seite öffnen</Link>
              </p>
            </li>)}
          </ul>
        </li>)}
      </ol>
    </section> : null}
  </div>;
}
