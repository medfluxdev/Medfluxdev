"use client";

import Link from "next/link";
import { REVIEW_TARGET, contractHref, notEvaluableLink } from "@/lib/fix-targets";
import { useCallback, useEffect, useState } from "react";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import EmptyState from "@/components/ui/EmptyState";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { KindChip, deadlineKind } from "@/components/deadlines/TerminKind";
import { deadlineOrigin } from "@/lib/deadline-origin";
import { formatDate } from "@/lib/format";
import { listDeadlines, type DeadlineDto, type DeadlineStatus } from "@/lib/domain-api/deadlines";
import { listRenewals } from "@/lib/domain-api/registerGrid";

const HORIZONS = [
  { value: "7", label: "7 Tage" },
  { value: "30", label: "30 Tage" },
  { value: "90", label: "90 Tage" },
  { value: "180", label: "6 Monate" },
  { value: "", label: "Alle" },
];


function isoInDays(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function readParam(name: string): string | null {
  try { return new URLSearchParams(window.location.search).get(name); } catch { return null; }
}

function writeParams(mine: boolean, horizon: string) {
  try {
    const params = new URLSearchParams(window.location.search);
    if (mine) params.set("nur", "meine"); else params.delete("nur");
    if (horizon === "90") params.delete("zeitraum"); else params.set("zeitraum", horizon || "alle");
    const query = params.toString();
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  } catch {
    // Adresse ist nur Komfort.
  }
}

function initialHorizon(): string {
  const value = readParam("zeitraum");
  if (value === "alle") return "";
  return HORIZONS.some((item) => item.value === value) ? (value as string) : "90";
}

const OVERDUE_ICON = <svg viewBox="0 0 24 24" focusable="false"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16M12 13v3M12 18v.5" /></svg>;

function Rows({ items }: { items: DeadlineDto[] }) {
  return <div className="table-scroll"><table className="rg-table dl-table">
    <thead><tr><th scope="col">Fällig</th><th scope="col">Termin</th><th scope="col">Vertrag</th><th scope="col">Zuständig</th><th scope="col">Erinnerung</th><th scope="col">Herkunft</th></tr></thead>
    <tbody>{items.map((item) => <tr key={item.id}>
      <td><span className="dl-when"><span className="dl-date">{formatDate(item.due_date)}</span>{item.overdue ? <Signal tone="critical" size="sm">Überfällig</Signal> : item.days_until_due === 0 ? <Signal tone="warning" size="sm">Heute</Signal> : null}</span></td>
      <th scope="row"><span className="terminlist-kind"><KindChip kind={deadlineKind(item)} /></span><Link className="termin-link" href={deadlineOrigin(item).href} title={`Zur Quelle: ${deadlineOrigin(item).label}`}>{item.title}</Link>{item.todo_text ? <span className="contract-business-status">{item.todo_text}</span> : null}</th>
      <td><Link href={`/contracts/${item.contract_id}`}>{item.contract_label ?? "Vertrag"}</Link></td>
      <td>{item.assignee_name ?? "Vertragsverantwortliche/r"}</td>
      <td>{formatDate(item.remind_on)}</td>
      <td>{item.source === "system" ? "Berechnet aus den Vertragsdaten" : "Manuelle Wiedervorlage"}{item.basis_unconfirmed ? <> <Link className="signal-link" href={contractHref(item.contract_id, REVIEW_TARGET)} title="Zugrunde liegende KI-Werte jetzt prüfen"><Signal tone="ai">Ungeprüfte KI-Werte</Signal></Link></> : null}</td>
    </tr>)}</tbody>
  </table></div>;
}

// Alle Fristen und Wiedervorlagen (berechnet aus den gepflegten Vertragsdaten oder manuell angelegt).
// Überfälliges steht immer zuerst und unabhängig vom gewählten Zeitraum; „Nur meine“ nutzt dieselbe
// Definition wie früher das Postfach (zugewiesen oder verantwortlich, inkl. Vertretung).
export default function DeadlineList({ organizationSlug }: { organizationSlug: string }) {
  const [items, setItems] = useState<DeadlineDto[] | null>(null);
  const [mine, setMine] = useState(false);
  const [horizon, setHorizon] = useState("90");
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<DeadlineStatus | "all">("open");
  const [error, setError] = useState<string | null>(null);
  const [notEvaluable, setNotEvaluable] = useState(0);
  const [notEvaluableItems, setNotEvaluableItems] = useState<{ contract_id: string }[]>([]);

  useEffect(() => {
    setMine(readParam("nur") === "meine");
    setHorizon(initialHorizon());
    setReady(true);
  }, []);

  const load = useCallback(async () => {
    if (!organizationSlug || !ready) return;
    try {
      const data = await listDeadlines(organizationSlug, { status, mine, dueBefore: horizon ? isoInDays(Number(horizon)) : undefined });
      setItems(data.items);
      setError(null);
    } catch (caught) {
      setItems(null);
      setError(caught instanceof Error ? caught.message : "Termine konnten nicht geladen werden.");
    }
  }, [horizon, mine, organizationSlug, ready, status]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!organizationSlug) return;
    listRenewals(organizationSlug, 1)
      .then((result) => { setNotEvaluable(result.not_evaluable?.length ?? 0); setNotEvaluableItems(result.not_evaluable ?? []); })
      .catch(() => setNotEvaluable(0));
  }, [organizationSlug]);

  function change(nextMine: boolean, nextHorizon: string) {
    setMine(nextMine);
    setHorizon(nextHorizon);
    writeParams(nextMine, nextHorizon);
  }

  const overdue = (items ?? []).filter((item) => item.overdue);
  const upcoming = (items ?? []).filter((item) => !item.overdue);
  const narrowed = mine || horizon !== "" || status !== "open";

  return <div className="dl-stack">
    <section className="cw-section dl-filter">
      <div className="rg-toolbar">
        <label className="rg-check"><input type="checkbox" checked={mine} onChange={(event) => change(event.target.checked, horizon)} />Nur meine</label>
        <label>Zeitraum <select value={horizon} onChange={(event) => change(mine, event.target.value)}>{HORIZONS.map((item) => <option key={item.label} value={item.value}>{item.label}</option>)}</select></label>
        <label>Status <select value={status} onChange={(event) => setStatus(event.target.value as DeadlineStatus | "all")}><option value="open">Offen</option><option value="done">Erledigt</option><option value="cancelled">Abgebrochen</option><option value="all">Alle</option></select></label>
        {overdue.length > 0 ? <Signal tone="critical">{overdue.length} überfällig</Signal> : null}
      </div>
    </section>
    {notEvaluable > 0 ? <InlineAlert tone="warning">Für {notEvaluable} {notEvaluable === 1 ? "Vertrag ist" : "Verträge ist"} die Kündigungsfrist nicht berechenbar (Laufzeitangaben unvollständig); diese Fristen fehlen hier. <Link href={notEvaluableLink(notEvaluableItems)}>{notEvaluable === 1 ? "Laufzeitangaben ergänzen" : "Verträge anzeigen"}</Link></InlineAlert> : null}
    {error ? <p role="alert" className="rg-error">{error} <button type="button" className="btn btn-sm" onClick={() => void load()}>Erneut versuchen</button></p> : null}
    {items === null && !error ? <p role="status">Termine werden geladen…</p> : null}
    {items !== null && items.length === 0 ? (
      narrowed
        ? <EmptyState variant="calm" title="Keine Termine für diese Auswahl"><>Andere Termine sind ausgeblendet. <button type="button" className="rg-link" onClick={() => { setStatus("open"); change(false, ""); }}>Alle offenen Termine anzeigen</button></></EmptyState>
        : <EmptyState variant="calm" title="Keine offenen Termine">Fristen aus den Vertragsdaten und Wiedervorlagen erscheinen hier automatisch.</EmptyState>
    ) : null}
    {overdue.length > 0 ? <CollapsibleSection id="deadlines-overdue" title={`Überfällig (${overdue.length})`} icon={OVERDUE_ICON} iconClassName="section-tile--danger" className="dl-overdue" defaultCollapsed={false} description="Fällige Termine, die noch offen sind"><Rows items={overdue} /></CollapsibleSection> : null}
    {upcoming.length > 0 ? <CollapsibleSection id="deadlines-upcoming" title={`${status === "open" ? "Anstehend" : "Termine"} (${upcoming.length})`} tone="accent" defaultCollapsed={false}><Rows items={upcoming} /></CollapsibleSection> : null}
  </div>;
}
