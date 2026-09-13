"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import ContractTable from "@/components/contracts/ContractTable";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import { apiGet } from "@/lib/api";
import type { ContractListResponse } from "@/lib/contract-types";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

export default function ReviewPage() {
  const [data, setData] = useState<ContractListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = new URLSearchParams({
        organization_slug: ORG_SLUG,
        requires_review: "true",
        page_size: "100",
      });
      const res = await apiGet<ContractListResponse>(
        `/api/contracts?${p.toString()}`
      );
      setData(res);
    } catch {
      setError("Prüfungsliste konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="page">
      <div className="section-caption">Manuelle Prüfung · Faktengenauigkeit</div>

      {error && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          {error}
        </InlineAlert>
      )}

      {loading && <LoadingState>Prüfungsliste wird geladen…</LoadingState>}

      {!loading && !error && data && (
        <section className="panel" aria-labelledby="review-heading">
          <div className="panel-head">
            <div>
              <h2 id="review-heading">Zu prüfende Verträge</h2>
              <p>
                {data.total_count}{" "}
                {data.total_count === 1 ? "Vertrag" : "Verträge"} benötigen
                eine manuelle Prüfung der extrahierten Fakten.
              </p>
            </div>
          </div>
          {data.items.length === 0 ? (
            <div className="state-box">
              <div className="state-icon">✓</div>
              <h3>Keine offenen Prüfungen</h3>
              <p>
                Für die aktuell geladenen Verträge liegt kein offener manueller
                Prüfbedarf vor.
              </p>
            </div>
          ) : (
            <div className="table-wrap">
              <ContractTable
                items={data.items}
                extraHeader="Prüfung"
                extra={(item) => (
                  <Link
                    className="btn btn-sm btn-primary"
                    href={`/contracts/${item.contract_id}`}
                  >
                    Prüfen
                  </Link>
                )}
              />
            </div>
          )}
        </section>
      )}
    </div>
  );
}