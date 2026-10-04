"use client";

import { useEffect, useState } from "react";
import {
  getContractBillingBasis,
  reconcileContractInvoice,
  type BillingBasisResponse,
  type BillingReconciliationResponse,
} from "@/lib/domain-api/contractBilling";
import InlineAlert from "@/components/ui/InlineAlert";

interface Props {
  contractId: string;
  organizationSlug: string;
}

function amount(value: string | number | null, currency: string) {
  if (value == null) return "–";
  const n = Number(value);
  if (!Number.isFinite(n)) return `${value} ${currency}`;
  return new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(n);
}

export default function ContractBillingPanel({ contractId, organizationSlug }: Props) {
  const [basis, setBasis] = useState<BillingBasisResponse | null>(null);
  const [label, setLabel] = useState("");
  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [result, setResult] = useState<BillingReconciliationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getContractBillingBasis(organizationSlug, contractId)
      .then((res) => {
        if (!active) return;
        setBasis(res);
        const first = res.items[0];
        if (first) {
          setLabel(first.label);
          setCurrency(first.currency);
        }
      })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "Abrechnungsbasis konnte nicht geladen werden."); });
    return () => { active = false; };
  }, [contractId, organizationSlug]);

  function selectBasis(nextLabel: string) {
    setLabel(nextLabel);
    const charge = basis?.items.find((item) => item.label === nextLabel);
    if (charge) setCurrency(charge.currency);
  }

  async function reconcile() {
    const numeric = Number(invoiceAmount.replace(",", "."));
    if (!label || !Number.isFinite(numeric)) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await reconcileContractInvoice(organizationSlug, contractId, [{ label, amount: numeric, currency }]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rechnungsprüfung konnte nicht ausgeführt werden.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="cw-section" aria-labelledby="billing-intelligence-heading">
    <div className="cw-section-head"><div><h2 id="billing-intelligence-heading">Rechnungsprüfung</h2><p>Vergleich mit der bestätigten, vom System berechneten Vertragsbasis.</p></div></div>
    {error ? <InlineAlert tone="warning" role="status">{error}</InlineAlert> : null}
    {basis && !basis.available ? <p className="cw-muted">Keine eindeutig akzeptierte Abrechnungsbasis vorhanden. Es wird kein Betrag erfunden.</p> : null}
    {basis?.available ? <>
      <div className="form-grid">
        <label>Vertragsposition<select value={label} onChange={(event) => selectBasis(event.target.value)}>{basis.items.map((item, index) => <option key={`${item.label}-${index}`} value={item.label}>{item.label} · {amount(item.amount, item.currency)}</option>)}</select></label>
        <label>Rechnungsbetrag<input inputMode="decimal" value={invoiceAmount} onChange={(event) => setInvoiceAmount(event.target.value)} placeholder="0,00" /></label>
        <label>Währung<input value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} maxLength={3} /></label>
        <div><button type="button" className="btn" disabled={busy || !invoiceAmount || !label} onClick={() => void reconcile()}>{busy ? "Prüft…" : "Rechnung prüfen"}</button></div>
      </div>
      {result ? <div className="card card-pad"><h3>Ergebnis</h3>{result.message ? <p>{result.message}</p> : null}{result.findings.map((finding, index) => <div key={`${finding.invoice_label}-${index}`} className="cw-task"><strong>{finding.outcome}</strong><span>{amount(finding.invoice_amount, finding.currency)} vs. {amount(finding.contract_amount, finding.currency)}</span><p>{finding.explanation}</p>{finding.requires_review ? <span className="cw-origin-badge cw-origin-missing">Prüfung erforderlich</span> : null}</div>)}{Object.keys(result.value_leakage).length ? <p><strong>Erkannte Mehrberechnung:</strong> {Object.entries(result.value_leakage).map(([ccy, value]) => amount(value, ccy)).join(" · ")}</p> : null}</div> : null}
    </> : null}
  </section>;
}
