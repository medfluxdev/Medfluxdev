"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import Button from "@/components/ui/Button";
import StatusBadge from "@/components/ui/StatusBadge";
import WorkItemCollaborationPanel from "@/components/work-queue/WorkItemCollaborationPanel";
import { useAuth } from "@/components/auth/AuthProvider";
import { useToast } from "@/components/ui/Toast";
import { formatDate, formatDaysRemaining } from "@/lib/format";
import { listWorkItems, setWorkItemStatus } from "@/lib/domain-api/workQueue";
import type { WorkItemSummary } from "@/lib/pr4-types";
import {
  severityLabel,
  workItemStatusLabel,
  workItemTypeLabel,
} from "@/lib/pr4-types";

const STATUS_OPTIONS = [
  ["", "Alle aktiven Status"],
  ["open", "Offen"],
  ["acknowledged", "In Bearbeitung"],
] as const;

const SEVERITY_OPTIONS = [
  ["", "Alle Prioritäten"],
  ["critical", "Kritisch"],
  ["high", "Hoch"],
  ["medium", "Mittel"],
  ["low", "Niedrig"],
  ["info", "Info"],
] as const;

const TYPE_OPTIONS = [
  ["", "Alle Aufgabentypen"],
  ["manual_review", "Manuelle Prüfung"],
  ["missing_cost", "Fehlende Kosten"],
  ["equipment_coverage_review", "Geräte-/Leistungsabdeckung"],
  ["equipment_relationship_ambiguous", "Geräte-Zuordnung"],
  ["sla_issue", "Service-Level-Konflikt"],
] as const;

function severityTone(sev: string): "critical" | "warning" | "neutral" {
  if (sev === "critical" || sev === "high") return "critical";
  if (sev === "medium") return "warning";
  return "neutral";
}

// Aufgaben aus der KI-Analyse (Prüfbedarf, fehlende Kosten, Geräte). Fristen
// (Kündigung, Vertragsende, Verlängerung) stehen allein unter „Termine“.
export default function TaskQueue() {
  const { organizationSlug } = useAuth();
  const requestSeq = useRef(0);
  const contextSeq = useRef(0);
  const [items, setItems] = useState<WorkItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [itemType, setItemType] = useState("");
  const [selectedWorkItemId, setSelectedWorkItemId] = useState<string | null>(null);
  const toast = useToast();
  const effectiveOrgSlug = organizationSlug;

  const load = useCallback(() => {
    const seq = ++requestSeq.current;
    if (!effectiveOrgSlug) {
      setItems([]);
      setLoading(false);
      setError(false);
      return;
    }
    setLoading(true);
    setError(false);
    setActionError(null);
    listWorkItems(effectiveOrgSlug, {
      active: true,
      status: status ? [status] : [],
      severity: severity ? [severity] : [],
      item_type: itemType ? [itemType] : [],
    })
      .then((res) => { if (seq === requestSeq.current) setItems(res.items ?? []); })
      .catch(() => { if (seq === requestSeq.current) setError(true); })
      .finally(() => { if (seq === requestSeq.current) setLoading(false); });
  }, [effectiveOrgSlug, itemType, severity, status]);

  useEffect(() => {
    void load();
    return () => { requestSeq.current += 1; };
  }, [load]);

  useEffect(() => {
    contextSeq.current += 1;
    setSelectedWorkItemId(null);
    setItems([]);
    setBusyId(null);
    setActionError(null);
  }, [organizationSlug]);

  const activeFilterCount = useMemo(() => [status, severity, itemType].filter(Boolean).length, [status, severity, itemType]);

  const transition = useCallback(async (item: WorkItemSummary, nextStatus: "acknowledged" | "resolved") => {
    if (!effectiveOrgSlug || busyId) return;
    const context = contextSeq.current;
    setBusyId(item.id);
    setActionError(null);
    try {
      await setWorkItemStatus(item.id, effectiveOrgSlug, nextStatus);
      if (context !== contextSeq.current) return;
      if (nextStatus === "resolved") {
        setItems((prev) => prev.filter((x) => x.id !== item.id));
        if (selectedWorkItemId === item.id) setSelectedWorkItemId(null);
      } else {
        setItems((prev) => prev.map((x) => (x.id === item.id ? { ...x, status: nextStatus } : x)));
      }
      toast(nextStatus === "resolved" ? "Aufgabe als erledigt markiert." : "Aufgabe in Bearbeitung übernommen.", "success");
    } catch (err) {
      if (context !== contextSeq.current) return;
      const reason = err instanceof Error && err.message ? err.message : "Status konnte nicht aktualisiert werden.";
      setActionError(reason);
      toast(reason, "error");
    } finally {
      if (context === contextSeq.current) setBusyId(null);
    }
  }, [effectiveOrgSlug, busyId, selectedWorkItemId, toast]);

  function resetFilters() {
    setStatus("");
    setSeverity("");
    setItemType("");
  }

  return (
    <div className="work-queue-page">
      {!loading && !error ? <p className="field-hint" role="status">{`${items.length} ${items.length === 1 ? "offene Aufgabe" : "offene Aufgaben"}`}</p> : null}

      <section className="work-queue-filterbar" aria-label="Aufgaben filtern">
        <label>Status<select aria-label="Status filtern" value={status} onChange={(e) => setStatus(e.target.value)}>{STATUS_OPTIONS.map(([value, label]) => <option value={value} key={value || "all"}>{label}</option>)}</select></label>
        <label>Priorität<select aria-label="Priorität filtern" value={severity} onChange={(e) => setSeverity(e.target.value)}>{SEVERITY_OPTIONS.map(([value, label]) => <option value={value} key={value || "all"}>{label}</option>)}</select></label>
        <label>Aufgabentyp<select aria-label="Aufgabentyp filtern" value={itemType} onChange={(e) => setItemType(e.target.value)}>{TYPE_OPTIONS.map(([value, label]) => <option value={value} key={value || "all"}>{label}</option>)}</select></label>
        {activeFilterCount > 0 && <Button size="sm" onClick={resetFilters}>Filter zurücksetzen ({activeFilterCount})</Button>}
      </section>

      <p className="work-queue-legend" role="note">Fristen wie Kündigung, Vertragsende und Verlängerung stehen unter „Termine“ – berechnet aus den gepflegten Vertragsdaten.</p>

      {selectedWorkItemId ? <WorkItemCollaborationPanel key={`${organizationSlug}:${selectedWorkItemId}`} workItemId={selectedWorkItemId} onClose={() => setSelectedWorkItemId(null)} /> : null}

      {error && <InlineAlert tone="critical" role="alert" action={<button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut laden</button>}>Aufgaben konnten nicht geladen werden.</InlineAlert>}
      {actionError && <InlineAlert tone="warning" role="alert">{actionError}</InlineAlert>}
      {loading && <LoadingState>Aufgaben werden geladen…</LoadingState>}

      {!loading && !error && items.length === 0 && (
        <div className="state-box">
          <div className="state-icon">✓</div>
          <h3>{activeFilterCount ? "Keine passenden Aufgaben" : "Keine offenen Aufgaben"}</h3>
          <p>{activeFilterCount ? "Für die gewählten Filter wurden keine aktiven Aufgaben gefunden." : "Aktuell sind keine offenen Aufgaben vorhanden."}</p>
          {activeFilterCount > 0 && <Button size="sm" onClick={resetFilters}>Alle offenen Aufgaben anzeigen</Button>}
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <section className="panel" aria-label="Aufgaben">
          <div className="table-wrap" tabIndex={0} aria-label="Aufgaben-Tabelle, horizontal scrollbar">
            <table className="contract-table work-queue-table">
              <caption className="sr-text">Offene Aufgaben</caption>
              <thead><tr><th scope="col">Aufgabe</th><th scope="col">Vertrag</th><th scope="col">Priorität</th><th scope="col">Termin</th><th scope="col">Status</th><th scope="col" className="num">Aktion</th></tr></thead>
              <tbody>
                {items.map((item) => {
                  return (
                    <tr key={item.id}>
                      <td>
                        <div className="cell-title">{workItemTypeLabel(item.item_type)}: {item.title_de}</div>
                        {item.why_de && <p className="muted cell-sub"><strong>Warum:</strong> {item.why_de}</p>}
                        {item.action_hint_de && <p className="cell-sub work-action-hint"><strong>Nächster Schritt:</strong> {item.action_hint_de}</p>}
                        {item.equipment_device_name && <p className="muted cell-sub"><span className="cell-kicker">Gerät</span>{" "}{item.equipment_device_name}{item.equipment_manufacturer ? ` · ${item.equipment_manufacturer}` : ""}{item.equipment_model ? ` (${item.equipment_model})` : ""}{item.equipment_serial_number ? ` · Seriennr. ${item.equipment_serial_number}` : ""}</p>}
                        {item.requires_review && <div className="badge-row"><StatusBadge label="Manuelle Prüfung" tone="review" /><Link className="table-link" href={`/contracts/${item.contract_id}?tab=documents&subtab=review`}>Prüfung öffnen</Link></div>}
                      </td>
                      <td><Link className="table-link" href={`/contracts/${item.contract_id}`}>{item.contract_number ?? item.supplier ?? "Vertrag"}</Link></td>
                      <td><StatusBadge label={severityLabel(item.severity)} tone={severityTone(item.severity)} /></td>
                      <td>
                        {item.target_date ? <><div>{formatDate(item.target_date)}</div><span className="muted">{formatDaysRemaining(item.days_remaining)}</span></> : <span className="muted">Kein Termin</span>}
                      </td>
                      <td><StatusBadge label={workItemStatusLabel(item.status)} tone="neutral" /></td>
                      <td className="num"><div className="row-actions"><Button size="sm" onClick={() => setSelectedWorkItemId((current) => current === item.id ? null : item.id)}>Organisieren</Button>{item.status === "open" && <Button size="sm" disabled={busyId === item.id} onClick={() => transition(item, "acknowledged")}>In Bearbeitung</Button>}<Button size="sm" variant="primary" disabled={busyId === item.id} onClick={() => transition(item, "resolved")}>Erledigt</Button></div></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
