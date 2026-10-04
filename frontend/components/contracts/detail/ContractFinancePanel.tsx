"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { formatCurrency, formatDate } from "@/lib/format";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { listCostCenters, type CostCenterDto } from "@/lib/domain-api/organizations";
import {
  INTERVAL_LABEL,
  PRICE_ADJUSTMENT_LABEL,
  acceptFinanceSuggestion,
  createFinanceEntry,
  createServiceItem,
  deleteFinanceEntry,
  deleteServiceItem,
  dismissFinanceSuggestion,
  downloadFinanceCsv,
  getFinance,
  setCostAllocations,
  type DirectionSummaryDto,
  type FinanceDto,
  type FinanceInterval,
  type FinanceSummaryDto,
  type SuggestionDto,
} from "@/lib/domain-api/finance";

const EMPTY_ENTRY = { direction: "expense", label: "", cost_type_code: "", amount: "", amount_basis: "net", vat_rate: "19", interval: "monthly", valid_from: "", valid_to: "", apply_price_adjustment: true };
const EMPTY_SERVICE = { label: "", service_kind: "", amount: "", unit: "", plus_vat: true, valid_from: "", valid_to: "" };
const PERIODS: { key: keyof DirectionSummaryDto; label: string }[] = [
  { key: "current_year", label: "Laufendes Jahr" },
  { key: "to_date", label: "Bisher" },
  { key: "remaining_to_end", label: "Bis Vertragsende" },
  { key: "total_term", label: "Gesamtlaufzeit" },
  { key: "annual_run_rate", label: "Jährlich (aktuell)" },
];

function errorText(error: unknown) {
  return error instanceof Error && error.message ? error.message : "Die Änderung konnte nicht gespeichert werden.";
}

function money(value: { net: string; gross: string } | null, currency: string) {
  if (!value) return <span className="cw-muted">nicht berechenbar</span>;
  return <><strong>{formatCurrency(value.net, currency)}</strong><span className="cw-muted"> netto · {formatCurrency(value.gross, currency)} brutto</span></>;
}

function SummaryTable({ summary }: { summary: FinanceSummaryDto }) {
  return <div className="table-scroll"><table className="rg-table" aria-label={`Finanzübersicht ${summary.currency}`}>
    <thead><tr><th scope="col">{summary.currency}</th>{PERIODS.map((period) => <th scope="col" key={period.key}>{period.label}</th>)}</tr></thead>
    <tbody>
      {(["expense", "income"] as const).map((direction) => <tr key={direction}>
        <th scope="row">{direction === "expense" ? "Ausgaben" : "Einnahmen"}</th>
        {PERIODS.map((period) => <td key={period.key}>{money(summary[direction][period.key], summary.currency)}</td>)}
      </tr>)}
    </tbody>
  </table></div>;
}

export default function ContractFinancePanel({ contractId, orgSlug }: { contractId: string; orgSlug: string }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [data, setData] = useState<FinanceDto | null>(null);
  const [costTypes, setCostTypes] = useState<LookupDto[]>([]);
  const [rechargeModes, setRechargeModes] = useState<LookupDto[]>([]);
  const [centers, setCenters] = useState<CostCenterDto[]>([]);
  const [entryForm, setEntryForm] = useState(EMPTY_ENTRY);
  const [serviceForm, setServiceForm] = useState(EMPTY_SERVICE);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [showServiceForm, setShowServiceForm] = useState(false);
  const [allocations, setAllocations] = useState<{ cost_center_id: string; share_percent: string; recharge_mode: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const apply = useCallback((next: FinanceDto) => {
    setData(next);
    setAllocations(next.allocations.map((item) => ({ cost_center_id: item.cost_center_id, share_percent: item.share_percent, recharge_mode: item.recharge_mode ?? "" })));
  }, []);

  useEffect(() => {
    getFinance(orgSlug, contractId).then(apply).catch((error) => setMessage({ tone: "error", text: errorText(error) }));
  }, [apply, contractId, orgSlug]);

  useEffect(() => {
    if (!editable) return;
    Promise.allSettled([listLookups(orgSlug), listCostCenters(orgSlug)]).then(([lookups, costCenters]) => {
      if (lookups.status === "fulfilled") {
        setCostTypes(lookups.value.items.filter((item) => item.field_key === "cost_type"));
        setRechargeModes(lookups.value.items.filter((item) => item.field_key === "recharge_mode"));
      }
      if (costCenters.status === "fulfilled") setCenters(costCenters.value.items.filter((item) => item.is_active));
    });
  }, [editable, orgSlug]);

  async function run(action: () => Promise<FinanceDto>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      apply(await action());
      setMessage({ tone: "ok", text: success });
      return true;
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addEntry() {
    const values: Record<string, unknown> = { ...entryForm, cost_type_code: entryForm.cost_type_code || null, valid_to: entryForm.valid_to || null };
    if (await run(() => createFinanceEntry(orgSlug, contractId, values), "Finanzeintrag angelegt.")) {
      setEntryForm(EMPTY_ENTRY);
      setShowEntryForm(false);
    }
  }

  async function addService() {
    const values: Record<string, unknown> = {
      ...serviceForm,
      service_kind: serviceForm.service_kind || null,
      amount: serviceForm.amount || null,
      unit: serviceForm.unit || null,
      valid_from: serviceForm.valid_from || null,
      valid_to: serviceForm.valid_to || null,
    };
    if (await run(() => createServiceItem(orgSlug, contractId, values), "Leistung angelegt.")) {
      setServiceForm(EMPTY_SERVICE);
      setShowServiceForm(false);
    }
  }

  async function exportCsv(expenses: boolean, income: boolean) {
    try {
      const { blob, filename } = await downloadFinanceCsv(orgSlug, contractId, { expenses, income });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename ?? "finanzdaten.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error) });
    }
  }

  function suggestionRow(scope: "finance" | "service", item: SuggestionDto) {
    const values = item.values;
    const currency = String(values.currency ?? "EUR");
    return <li key={`${scope}-${item.key}`}>
      <span><strong>{String(values.label)}</strong>: {values.amount ? formatCurrency(String(values.amount), currency) : "–"}
        {scope === "finance" ? ` ${values.amount_basis === "gross" ? "brutto" : "netto"}, ${INTERVAL_LABEL[values.interval as FinanceInterval] ?? values.interval}, ab ${formatDate(String(values.valid_from))}` : values.unit ? ` ${values.unit}` : ""}
      </span>
      {item.assumptions && item.assumptions.length > 0 ? <span className="rg-origin rg-origin-ai_corrected">{item.assumptions.join(" · ")}</span> : null}
      <span className="rg-origin rg-origin-ai" title={`Quelle: ${item.source_field}`}>KI-Vorschlag</span>
      {editable ? <span className="rg-actions">
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(() => acceptFinanceSuggestion(orgSlug, contractId, scope, item.key), "Vorschlag übernommen.")}>Übernehmen</button>
        <button type="button" className="btn" disabled={busy} onClick={() => void run(() => dismissFinanceSuggestion(orgSlug, contractId, scope, item.key), "Vorschlag verworfen.")}>Verwerfen</button>
      </span> : null}
    </li>;
  }

  if (!data) return <section className="cw-section"><p role={message ? "alert" : "status"}>{message?.text ?? "Finanzdaten werden geladen…"}</p></section>;

  const allocationSum = allocations.reduce((sum, item) => sum + (Number(item.share_percent) || 0), 0);
  const costTypeLabel = (code: string | null) => costTypes.find((item) => item.code === code)?.label ?? code ?? "–";
  const suggestionCount = data.suggestions.entries.length + data.suggestions.services.length;

  return <div className="rg-panel">
    <section className="cw-section" aria-labelledby="fin-summary-heading">
      <div className="cw-section-head">
        <div><h2 id="fin-summary-heading">Finanzdaten</h2><p>Kalkulatorisch auf Basis ganzer Monate, aus den gepflegten Finanzeinträgen (Stand {formatDate(data.as_of)}).</p></div>
        {data.entries.length > 0 ? <div className="rg-actions"><button type="button" className="btn" onClick={() => void exportCsv(true, true)}>Export (CSV)</button><button type="button" className="btn" onClick={() => void exportCsv(true, false)}>Nur Ausgaben</button></div> : null}
      </div>
      {data.summaries.length === 0 ? <p className="cw-muted">Noch keine Finanzeinträge. {suggestionCount > 0 ? "Die KI hat Vorschläge aus dem Vertrag – siehe unten." : "Bitte Einträge erfassen."}</p> : data.summaries.map((summary) => <div key={summary.currency}>
        <SummaryTable summary={summary} />
        {summary.notes.length > 0 ? <ul className="rg-explanation">{summary.notes.map((note) => <li key={note}>{note}</li>)}</ul> : null}
      </div>)}
      {data.price_adjustment.kind ? <p className="cw-muted">Preisanpassung: {PRICE_ADJUSTMENT_LABEL[data.price_adjustment.kind] ?? data.price_adjustment.kind}{data.price_adjustment.percent ? ` ${Number(data.price_adjustment.percent).toLocaleString("de-DE")} %` : ""}{data.price_adjustment.index_name ? ` (${data.price_adjustment.index_name})` : ""}{data.price_adjustment.next_date ? `, nächste Anpassung ${formatDate(data.price_adjustment.next_date)}` : ""} – Pflege in den Stammdaten.</p> : null}
    </section>

    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

    {suggestionCount > 0 ? <section className="cw-section rg-ai" aria-labelledby="fin-ai-heading">
      <div className="cw-section-head"><div><h2 id="fin-ai-heading">KI-Vorschläge aus dem Vertrag</h2><p>Nur übernommene Vorschläge fließen in die Berechnung ein. Annahmen sind gekennzeichnet.</p></div></div>
      <ul>{data.suggestions.entries.map((item) => suggestionRow("finance", item))}{data.suggestions.services.map((item) => suggestionRow("service", item))}</ul>
    </section> : null}

    <section className="cw-section" aria-labelledby="fin-entries-heading">
      <div className="cw-section-head"><div><h2 id="fin-entries-heading">Finanzeinträge</h2><p>Ausgaben und Einnahmen mit Gültigkeitszeitraum. Preisänderungen als neuer Eintrag mit neuem Zeitraum.</p></div>
        {editable && !showEntryForm ? <button type="button" className="btn btn-primary" onClick={() => setShowEntryForm(true)}>Eintrag erstellen</button> : null}</div>
      {showEntryForm ? <form className="rg-transition" aria-label="Finanzeintrag anlegen" onSubmit={(event) => { event.preventDefault(); void addEntry(); }}>
        <div className="rg-form-grid">
          <label>Typ<select value={entryForm.direction} onChange={(event) => setEntryForm((form) => ({ ...form, direction: event.target.value }))}><option value="expense">Ausgaben</option><option value="income">Einnahmen</option></select></label>
          <label>Bezeichnung *<input required maxLength={255} value={entryForm.label} onChange={(event) => setEntryForm((form) => ({ ...form, label: event.target.value }))} /></label>
          <label>Kostenart<select value={entryForm.cost_type_code} onChange={(event) => setEntryForm((form) => ({ ...form, cost_type_code: event.target.value }))}><option value="">–</option>{costTypes.map((item) => <option key={item.id} value={item.code}>{item.label}</option>)}</select></label>
          <label>Betrag *<input required inputMode="decimal" value={entryForm.amount} onChange={(event) => setEntryForm((form) => ({ ...form, amount: event.target.value }))} /></label>
          <label>Basis<select value={entryForm.amount_basis} onChange={(event) => setEntryForm((form) => ({ ...form, amount_basis: event.target.value }))}><option value="net">Netto</option><option value="gross">Brutto</option></select></label>
          <label>Steuer %<select value={entryForm.vat_rate} onChange={(event) => setEntryForm((form) => ({ ...form, vat_rate: event.target.value }))}><option value="19">19</option><option value="7">7</option><option value="0">0</option></select></label>
          <label>Intervall<select value={entryForm.interval} onChange={(event) => setEntryForm((form) => ({ ...form, interval: event.target.value }))}>{(Object.keys(INTERVAL_LABEL) as FinanceInterval[]).map((key) => <option key={key} value={key}>{INTERVAL_LABEL[key]}</option>)}</select></label>
          <label>Gültig ab *<input type="date" required value={entryForm.valid_from} onChange={(event) => setEntryForm((form) => ({ ...form, valid_from: event.target.value }))} /></label>
          <label>Gültig bis<input type="date" min={entryForm.valid_from || undefined} value={entryForm.valid_to} onChange={(event) => setEntryForm((form) => ({ ...form, valid_to: event.target.value }))} /></label>
          <label className="rg-check"><input type="checkbox" checked={entryForm.apply_price_adjustment} onChange={(event) => setEntryForm((form) => ({ ...form, apply_price_adjustment: event.target.checked }))} />Preisanpassung anwenden</label>
        </div>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => { setShowEntryForm(false); setEntryForm(EMPTY_ENTRY); }}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
      </form> : null}
      {data.entries.length === 0 ? <p className="cw-muted">Keine Einträge.</p> : <div className="table-scroll"><table className="rg-table">
        <thead><tr><th scope="col">Typ</th><th scope="col">Bezeichnung</th><th scope="col">Kostenart</th><th scope="col">Betrag</th><th scope="col">Intervall</th><th scope="col">Gültig</th><th scope="col">Herkunft</th>{editable ? <th scope="col"><span className="sr-only">Aktionen</span></th> : null}</tr></thead>
        <tbody>{data.entries.map((item) => <tr key={item.id}>
          <td>{item.direction === "expense" ? "Ausgaben" : "Einnahmen"}</td>
          <th scope="row">{item.label}{item.note ? <span className="contract-business-status">{item.note}</span> : null}</th>
          <td>{costTypeLabel(item.cost_type_code)}</td>
          <td>{formatCurrency(item.amount, item.currency)} {item.amount_basis === "net" ? "netto" : "brutto"} · {Number(item.vat_rate).toLocaleString("de-DE")} %</td>
          <td>{INTERVAL_LABEL[item.interval]}</td>
          <td>{item.interval === "once" ? formatDate(item.valid_from) : `${formatDate(item.valid_from)} – ${item.valid_to ? formatDate(item.valid_to) : "offen"}`}</td>
          <td>{item.origin === "ai_confirmed" ? <span className="rg-origin rg-origin-ai_confirmed">KI · bestätigt</span> : <span className="rg-origin">Manuell</span>}</td>
          {editable ? <td><button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => deleteFinanceEntry(orgSlug, contractId, item.id), "Eintrag gelöscht.")}>Löschen</button></td> : null}
        </tr>)}</tbody>
      </table></div>}
    </section>

    <section className="cw-section" aria-labelledby="fin-services-heading">
      <div className="cw-section-head"><div><h2 id="fin-services-heading">Leistungskatalog</h2><p>Einzelpreise wie Stundensätze, Reisekosten oder Pauschalen.</p></div>
        {editable && !showServiceForm ? <button type="button" className="btn btn-primary" onClick={() => setShowServiceForm(true)}>Leistung erstellen</button> : null}</div>
      {showServiceForm ? <form className="rg-transition" aria-label="Leistung anlegen" onSubmit={(event) => { event.preventDefault(); void addService(); }}>
        <div className="rg-form-grid">
          <label>Leistung *<input required maxLength={255} value={serviceForm.label} onChange={(event) => setServiceForm((form) => ({ ...form, label: event.target.value }))} /></label>
          <label>Betrag<input inputMode="decimal" value={serviceForm.amount} onChange={(event) => setServiceForm((form) => ({ ...form, amount: event.target.value }))} /></label>
          <label>Einheit<input maxLength={64} placeholder="z. B. pro Stunde" value={serviceForm.unit} onChange={(event) => setServiceForm((form) => ({ ...form, unit: event.target.value }))} /></label>
          <label className="rg-check"><input type="checkbox" checked={serviceForm.plus_vat} onChange={(event) => setServiceForm((form) => ({ ...form, plus_vat: event.target.checked }))} />zzgl. USt.</label>
          <label>Gültig ab<input type="date" value={serviceForm.valid_from} onChange={(event) => setServiceForm((form) => ({ ...form, valid_from: event.target.value }))} /></label>
          <label>Gültig bis<input type="date" value={serviceForm.valid_to} onChange={(event) => setServiceForm((form) => ({ ...form, valid_to: event.target.value }))} /></label>
        </div>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => { setShowServiceForm(false); setServiceForm(EMPTY_SERVICE); }}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
      </form> : null}
      {data.services.length === 0 ? <p className="cw-muted">Keine Leistungen erfasst.</p> : <table className="rg-table">
        <thead><tr><th scope="col">Leistung</th><th scope="col">Betrag</th><th scope="col">Gültig</th><th scope="col">Herkunft</th>{editable ? <th scope="col"><span className="sr-only">Aktionen</span></th> : null}</tr></thead>
        <tbody>{data.services.map((item) => <tr key={item.id}>
          <th scope="row">{item.label}</th>
          <td>{item.amount ? `${formatCurrency(item.amount, item.currency)}${item.unit ? ` ${item.unit}` : ""}${item.plus_vat ? " zzgl. USt." : ""}` : "–"}</td>
          <td>{item.valid_from || item.valid_to ? `${item.valid_from ? formatDate(item.valid_from) : "–"} – ${item.valid_to ? formatDate(item.valid_to) : "offen"}` : "unbefristet"}</td>
          <td>{item.origin === "ai_confirmed" ? "KI · bestätigt" : "Manuell"}</td>
          {editable ? <td><button type="button" className="rg-link" disabled={busy} onClick={() => void run(() => deleteServiceItem(orgSlug, contractId, item.id), "Leistung gelöscht.")}>Löschen</button></td> : null}
        </tr>)}</tbody>
      </table>}
    </section>

    <section className="cw-section" aria-labelledby="fin-alloc-heading">
      <div className="cw-section-head"><div><h2 id="fin-alloc-heading">Kostenstellen-Aufteilung</h2><p>Verteilung der Vertragskosten (Summe 100 %). Ohne Aufteilung gilt die Kostenstelle aus der Organisationszuordnung.</p></div></div>
      {data.allocations.length > 0 && !editable ? <table className="rg-table"><tbody>{data.allocations.map((item) => <tr key={item.cost_center_id}><th scope="row">{item.code} – {item.name}</th><td>{Number(item.share_percent).toLocaleString("de-DE")} %</td><td>{item.annual_net ? `${formatCurrency(item.annual_net, "EUR")} netto/Jahr` : "–"}</td></tr>)}</tbody></table> : null}
      {editable ? <form onSubmit={(event) => { event.preventDefault(); void run(() => setCostAllocations(orgSlug, contractId, allocations.filter((item) => item.cost_center_id).map((item) => ({ ...item, recharge_mode: item.recharge_mode || null }))), "Aufteilung gespeichert."); }}>
        {allocations.map((item, index) => {
          const current = data.allocations.find((row) => row.cost_center_id === item.cost_center_id);
          return <div className="rg-form-grid mb-2" key={index}>
            <label>Kostenstelle<select value={item.cost_center_id} onChange={(event) => setAllocations((rows) => rows.map((row, i) => i === index ? { ...row, cost_center_id: event.target.value } : row))}><option value="">Bitte auswählen</option>{centers.map((center) => <option key={center.id} value={center.id}>{center.code} – {center.name}</option>)}</select></label>
            <label>Anteil %<input inputMode="decimal" value={item.share_percent} onChange={(event) => setAllocations((rows) => rows.map((row, i) => i === index ? { ...row, share_percent: event.target.value } : row))} /></label>
            <label>Weiterbelastung<select value={item.recharge_mode} onChange={(event) => setAllocations((rows) => rows.map((row, i) => i === index ? { ...row, recharge_mode: event.target.value } : row))}><option value="">–</option>{rechargeModes.map((mode) => <option key={mode.id} value={mode.code}>{mode.label}</option>)}</select></label>
            <span className="rg-actions">{current?.annual_net ? <span className="cw-muted">{formatCurrency(current.annual_net, "EUR")} netto/Jahr</span> : null}<button type="button" className="rg-link" onClick={() => setAllocations((rows) => rows.filter((_, i) => i !== index))}>Entfernen</button></span>
          </div>;
        })}
        <div className="rg-actions">
          <span className={Math.abs(allocationSum - 100) < 0.001 || allocations.length === 0 ? "cw-muted" : "rg-error"}>Summe {allocationSum.toLocaleString("de-DE")} %</span>
          <button type="button" className="btn" onClick={() => setAllocations((rows) => [...rows, { cost_center_id: "", share_percent: rows.length ? "" : "100", recharge_mode: "" }])}>Kostenstelle hinzufügen</button>
          <button type="submit" className="btn btn-primary" disabled={busy || (allocations.length > 0 && Math.abs(allocationSum - 100) >= 0.001)}>Aufteilung speichern</button>
        </div>
      </form> : null}
    </section>
  </div>;
}
