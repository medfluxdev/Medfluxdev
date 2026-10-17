"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import {
  getContractBillingBasis,
  reconcileContractInvoice,
  type BillingBasisResponse,
  type BillingFinding,
  type BillingReconciliationResponse,
} from "@/lib/domain-api/contractBilling";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { FINANCE_ENTRIES_TARGET, contractHref } from "@/lib/fix-targets";

interface Props {
  contractId: string;
  organizationSlug: string;
}

const CHECKDOC = <svg viewBox="0 0 24 24" focusable="false"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M9 15l2 2 4-4" /></svg>;

function amount(value: string | number | null, currency: string) {
  if (value == null) return "–";
  const n = Number(value);
  if (!Number.isFinite(n)) return `${value} ${currency}`;
  return new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(n);
}

/** Deutsche Eingabe („8.000,00“ oder „8000.5“) → Zahl; sonst NaN. */
export function parseAmount(raw: string): number {
  const value = raw.trim().replace(/\s|€/g, "");
  if (!value) return Number.NaN;
  const normalized = value.includes(",") ? value.replace(/\./g, "").replace(",", ".") : value;
  return /^-?\d+(\.\d+)?$/.test(normalized) ? Number(normalized) : Number.NaN;
}

function FindingSignal({ finding, contractId }: { finding: BillingFinding; contractId: string }) {
  const invoice = Number(finding.invoice_amount);
  const contract = finding.contract_amount == null ? null : Number(finding.contract_amount);
  if (finding.outcome === "matched" && contract != null) {
    return <p className="bill-result"><Signal tone="done"><strong>Stimmt überein.</strong> {amount(invoice, finding.currency)} entspricht der Vertragsbasis. Abweichung {amount(0, finding.currency)}.</Signal></p>;
  }
  if (contract != null && Number.isFinite(invoice) && (finding.outcome === "overbilled" || finding.outcome === "underbilled")) {
    const diff = invoice - contract;
    const percent = contract !== 0 ? ` (${(diff / contract * 100).toLocaleString("de-DE", { maximumFractionDigits: 1, signDisplay: "always" })} %)` : "";
    return <p className="bill-result">
      <Signal tone="warning"><strong>Weicht ab:</strong> {diff > 0 ? "+" : ""}{amount(diff, finding.currency)}{percent} gegenüber der Vertragsbasis ({amount(contract, finding.currency)}).</Signal>
      {" "}<Link className="rg-link" href={contractHref(contractId, FINANCE_ENTRIES_TARGET)}>Finanzeintrag öffnen</Link>
    </p>;
  }
  return <p className="bill-result"><Signal tone="neutral">{finding.explanation || "Kein eindeutiger Vergleich möglich."}</Signal></p>;
}

/** Werkzeug: Rechnungsbetrag gegen die bestätigte Vertragsbasis vergleichen; ändert keine Daten. */
export default function ContractBillingPanel({ contractId, organizationSlug }: Props) {
  const [basis, setBasis] = useState<BillingBasisResponse | null>(null);
  const [index, setIndex] = useState(0);
  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [result, setResult] = useState<BillingReconciliationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  useEffect(() => {
    let active = true;
    getContractBillingBasis(organizationSlug, contractId)
      .then((res) => { if (active) setBasis(res); })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "Abrechnungsbasis konnte nicht geladen werden."); });
    return () => { active = false; };
  }, [contractId, organizationSlug]);

  const charge = basis?.items[index] ?? null;
  // Die Währung kommt aus der Vertragsposition, kein eigenes Feld.
  const currency = charge?.currency ?? "EUR";
  const numeric = parseAmount(invoiceAmount);
  const ready = Boolean(charge) && Number.isFinite(numeric) && numeric > 0;

  async function reconcile() {
    if (!charge || !ready) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await reconcileContractInvoice(organizationSlug, contractId, [{ label: charge.label, amount: numeric, currency }]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rechnungsprüfung konnte nicht ausgeführt werden.");
    } finally {
      setBusy(false);
    }
  }

  return <CollapsibleSection id="billing-intelligence" title="Rechnung prüfen" description="Werkzeug: Rechnungsbetrag gegen die bestätigte Vertragsbasis vergleichen. Ändert keine Daten." tone="accent" icon={CHECKDOC}>
    {error ? <InlineAlert tone="warning" role="status">{error}</InlineAlert> : null}
    {basis && !basis.available ? <p className="cw-muted">Keine eindeutig akzeptierte Abrechnungsbasis vorhanden. Es wird kein Betrag erfunden.</p> : null}
    {basis?.available ? <>
      <form className="bill-form" onSubmit={(event) => { event.preventDefault(); void reconcile(); }}>
        <label className="bill-field">Vertragsposition
          <select value={index} onChange={(event) => { setIndex(Number(event.target.value)); setResult(null); }}>
            {basis.items.map((item, position) => <option key={`${item.label}-${position}`} value={position}>{item.label} · {amount(item.amount, item.currency)}</option>)}
          </select>
        </label>
        <label className="bill-field" htmlFor={`${id}-amount`}>Rechnungsbetrag ({currency}, laut Vertrag)
          <span className="bill-input">
            <input id={`${id}-amount`} inputMode="decimal" value={invoiceAmount} onChange={(event) => { setInvoiceAmount(event.target.value); setResult(null); }} placeholder="0,00" />
            <span className="bill-suffix" aria-hidden="true">{currency}</span>
          </span>
        </label>
        <button type="submit" className="btn btn-primary" disabled={busy || !ready}>{busy ? "Prüft…" : "Prüfen"}</button>
      </form>
      {!ready && invoiceAmount.trim() ? <p className="field-hint">Bitte einen Betrag größer als 0 eingeben.</p> : null}
      {result ? <div className="bill-results">
        {result.message ? <p className="cw-muted">{result.message}</p> : null}
        {result.findings.map((finding, position) => <FindingSignal key={`${finding.invoice_label}-${position}`} finding={finding} contractId={contractId} />)}
        {Object.keys(result.value_leakage).length ? <p><strong>Erkannte Mehrberechnung:</strong> {Object.entries(result.value_leakage).map(([ccy, value]) => amount(value, ccy)).join(" · ")}</p> : null}
      </div> : null}
    </> : null}
  </CollapsibleSection>;
}
