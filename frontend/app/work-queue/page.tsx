"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import Button from "@/components/ui/Button";
import StatusBadge from "@/components/ui/StatusBadge";
import { apiGet, apiPatch } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { formatDate, formatDaysRemaining } from "@/lib/format";
import type { WorkItemList, WorkItemSummary } from "@/lib/pr4-types";
import {
  severityLabel,
  workItemStatusLabel,
  workItemTypeLabel,
} from "@/lib/pr4-types";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

function severityTone(sev: string): "critical" | "warning" | "neutral" {
  if (sev === "critical" || sev === "high") return "critical";
  if (sev === "medium") return "warning";
  return "neutral";
}

export default function WorkQueuePage() {
  const [items, setItems] = useState<WorkItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    setActionError(null);
    apiGet<WorkItemList>(
      `/api/work-queue?organization_slug=${encodeURIComponent(ORG_SLUG)}&active=true`
    )
      .then((res) => setItems(res.items ?? []))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const transition = useCallback(
    async (item: WorkItemSummary, status: "acknowledged" | "resolved") => {
      setBusyId(item.id);
      setActionError(null);
      try {
        await apiPatch<WorkItemSummary>(
          `/api/work-queue/${encodeURIComponent(item.id)}?organization_slug=${encodeURIComponent(ORG_SLUG)}`,
          { status }
        );
        if (status === "resolved") {
          setItems((prev) => prev.filter((x) => x.id !== item.id));
        } else {
          setItems((prev) =>
            prev.map((x) => (x.id === item.id ? { ...x, status } : x))
          );
        }
        toast(
          status === "resolved"
            ? "Aufgabe als erledigt markiert."
            : "Aufgabe in Bearbeitung übernommen.",
          "success"
        );
      } catch (err) {
        const reason =
          err instanceof Error && err.message
            ? err.message
            : "Status konnte nicht aktualisiert werden.";
        setActionError(reason);
        toast(reason, "error");
      } finally {
        setBusyId(null);
      }
    },
    [toast]
  );

  return (
    <div className="page">
      <PageHeader
        title="To-dos"
        description={`${items.length} ${items.length === 1 ? "offene Aufgabe" : "offene Aufgaben"}`}
      />

      {error && (
        <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>
          To-dos konnten nicht geladen werden.
        </InlineAlert>
      )}

      {actionError && (
        <InlineAlert tone="warning" role="alert">
          {actionError}
        </InlineAlert>
      )}

      {loading && <LoadingState>To-dos werden geladen…</LoadingState>}

      {!loading && !error && items.length === 0 && (
        <div className="state-box">
          <div className="state-icon">✓</div>
          <h3>Keine offenen To-dos</h3>
          <p>Aktuell sind keine offenen Aufgaben vorhanden.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <section className="panel" aria-label="To-dos">
        <div className="table-wrap">
          <table className="contract-table">
            <caption className="sr-text">Offene To-dos</caption>
            <thead>
              <tr>
                <th scope="col">Aufgabe</th>
                <th scope="col">Vertrag</th>
                <th scope="col">Priorität</th>
                <th scope="col">Frist</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">
                  Aktion
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div className="cell-title">
                      {workItemTypeLabel(item.item_type)}: {item.title_de}
                    </div>
                    {item.why_de && <p className="muted cell-sub">{item.why_de}</p>}
                    {item.equipment_device_name && (
                      <p className="muted cell-sub">
                        <span className="cell-kicker">Gerät</span>{" "}
                        {item.equipment_device_name}
                        {item.equipment_manufacturer
                          ? ` · ${item.equipment_manufacturer}`
                          : ""}
                        {item.equipment_model ? ` (${item.equipment_model})` : ""}
                        {item.equipment_serial_number
                          ? ` · Seriennr. ${item.equipment_serial_number}`
                          : ""}
                      </p>
                    )}
                    {item.requires_review && (
                      <div className="badge-row">
                        <StatusBadge label="Zu prüfen" tone="review" />
                      </div>
                    )}
                  </td>
                  <td>
                    <Link className="table-link" href={`/contracts/${item.contract_id}`}>
                      {item.contract_number ?? item.supplier ?? "Vertrag"}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge label={severityLabel(item.severity)} tone={severityTone(item.severity)} />
                  </td>
                  <td>
                    {item.target_date ? (
                      <>
                        {formatDate(item.target_date)}{" "}
                        <span className="muted">{formatDaysRemaining(item.days_remaining)}</span>
                      </>
                    ) : (
                      "–"
                    )}
                  </td>
                  <td>
                    <StatusBadge label={workItemStatusLabel(item.status)} tone="neutral" />
                  </td>
                  <td className="num">
                    <div className="row-actions">
                      {item.status === "open" && (
                        <Button
                          size="sm"
                          disabled={busyId === item.id}
                          onClick={() => transition(item, "acknowledged")}
                        >
                          In Bearbeitung
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={busyId === item.id}
                        onClick={() => transition(item, "resolved")}
                      >
                        Erledigt
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </section>
      )}
    </div>
  );
}
