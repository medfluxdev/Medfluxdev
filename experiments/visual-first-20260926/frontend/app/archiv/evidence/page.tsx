"use client";

import { useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import InlineAlert from "@/components/ui/InlineAlert";
import { useAuth } from "@/components/auth/AuthProvider";
import { contentUrl } from "@/lib/api";
import {
  searchArchiveEvidence,
  type ArchiveEvidenceResponse,
} from "@/lib/archive-evidence";

export default function ArchiveEvidenceExperimentPage() {
  const { organizationSlug } = useAuth();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ArchiveEvidenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enabled = process.env.NEXT_PUBLIC_LLAMA_ARCHIVE_EXPERIMENT === "true";

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organizationSlug || query.trim().length < 2 || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await searchArchiveEvidence(organizationSlug, query));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Suche fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Nachweissuche â€“ Experiment"
        description="LlamaIndex: Nur belegte und Ã¼berprÃ¼fungsfreie Quellen aus akzeptierten VertrÃ¤gen. Es wird kein zweites KI-Modell verwendet."
      />
      <p><Link href="/archiv">ZurÃ¼ck zum Archiv</Link></p>
      {!enabled ? (
        <InlineAlert tone="warning">
          Die experimentelle Suche ist deaktiviert.
        </InlineAlert>
      ) : (
        <>
          <form onSubmit={search} className="panel">
            <label htmlFor="archive-evidence-query">Quellen durchsuchen</label>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <input
                id="archive-evidence-query"
                type="search"
                value={query}
                maxLength={120}
                placeholder="GerÃ¤t, Vertragsklausel oder Betrag"
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="btn" type="submit"
                disabled={loading || !organizationSlug || query.trim().length < 2}>
                {loading ? "Suche lÃ¤uftâ€¦" : "Suchen"}
              </button>
            </div>
          </form>
          {error && <InlineAlert tone="critical" role="alert">{error}</InlineAlert>}
          {result && (
            <section className="panel" aria-live="polite">
              <h2>{result.items.length} Nachweise gefunden</h2>
              <p>Indexierte, bereits Ã¼berprÃ¼fte Quellen: {result.indexed_sources}</p>
              {result.items.length === 0 && (
                <p>Keine freigegebenen Quellen gefunden. VertrÃ¤ge mit offener PrÃ¼fung werden absichtlich nicht als bestÃ¤tigte Fakten angezeigt.</p>
              )}
              <ul>
                {result.items.map((item) => (
                  <li key={[`doc:${item.document_id}`, item.revision, item.page, item.field, item.source_quote].join(":")}>
                    <strong>{item.field}</strong> â€“ Seite {item.page}
                    <p>{item.source_quote}</p>
                    {organizationSlug && (
                      <a
                        href={contentUrl(item.document_id, item.revision, organizationSlug) + `#page=${item.page}`}
                        target="_blank"
                        rel="noreferrer"
                      >Originalquelle Ã¶ffnen</a>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
