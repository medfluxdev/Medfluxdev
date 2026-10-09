"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import InlineAlert from "@/components/ui/InlineAlert";
import Skeleton from "@/components/ui/Skeleton";
import { getNumberRange, reserveNumbers, updateNumberRange, type NumberRangeDto } from "@/lib/domain-api/catalogs";

function errorText(error: unknown) {
  return error instanceof Error && error.message ? error.message : "Die Änderung konnte nicht gespeichert werden.";
}

// Vergabe der Vertragsnummern: Praefix, Stellen, naechste Nummer, Reservierungen.
export default function NumberRangeSettings({ organizationSlug }: { organizationSlug: string }) {
  const [range, setRange] = useState<NumberRangeDto | null>(null);
  const [form, setForm] = useState({ prefix: "", padding: "6", next_value: "" });
  const [reserveText, setReserveText] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "critical"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getNumberRange(organizationSlug);
      setRange(data);
      setForm({ prefix: data.prefix, padding: String(data.padding), next_value: String(data.next_value) });
    } catch (error) {
      setMessage({ tone: "critical", text: errorText(error) });
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage({ tone: "success", text: success });
      await load();
      return true;
    } catch (error) {
      setMessage({ tone: "critical", text: errorText(error) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  function save() {
    const payload: { prefix?: string; padding?: number; next_value?: number } = { prefix: form.prefix, padding: Number(form.padding) };
    if (range && Number(form.next_value) !== range.next_value) payload.next_value = Number(form.next_value);
    void run(() => updateNumberRange(organizationSlug, payload), "Nummernkreis gespeichert.");
  }

  async function reserve() {
    const values = reserveText.split(/[\s,;]+/).map((part) => Number(part)).filter((value) => Number.isInteger(value) && value > 0);
    if (values.length === 0) return;
    if (await run(() => reserveNumbers(organizationSlug, values), "Nummern reserviert.")) setReserveText("");
  }

  if (!range && !message) return <Skeleton lines={4} label="Nummernkreis wird geladen…" />;
  return <section className="card card-pad" aria-labelledby="number-range-heading">
    <div className="section-head">
      <div>
        <h2 id="number-range-heading">Vertragsnummern</h2>
        {range ? <p>Nächste Nummer: <strong>{range.next_formatted}</strong> · {range.used_count} vergeben · {range.reserved.length} reserviert</p> : null}
      </div>
    </div>
    {message ? <InlineAlert tone={message.tone} role={message.tone === "critical" ? "alert" : "status"}>{message.text}</InlineAlert> : null}
    {range ? <>
      <form className="form-grid" onSubmit={(event) => { event.preventDefault(); save(); }}>
        <Field label="Präfix" htmlFor="nr-prefix"><input id="nr-prefix" maxLength={16} value={form.prefix} onChange={(event) => setForm((current) => ({ ...current, prefix: event.target.value }))} /></Field>
        <Field label="Stellen" htmlFor="nr-padding"><input id="nr-padding" type="number" min={1} max={12} value={form.padding} onChange={(event) => setForm((current) => ({ ...current, padding: event.target.value }))} /></Field>
        <Field label="Nächste Nummer" htmlFor="nr-next" hint="Nur erhöhen; bereits vergebene Nummern werden nie erneut vergeben."><input id="nr-next" type="number" min={1} value={form.next_value} onChange={(event) => setForm((current) => ({ ...current, next_value: event.target.value }))} /></Field>
        <div className="form-actions"><Button type="submit" variant="primary" disabled={busy}>Speichern</Button></div>
      </form>
      <form className="form-grid mt-4" onSubmit={(event) => { event.preventDefault(); void reserve(); }}>
        <Field label="Nummern reservieren" htmlFor="nr-reserve" hint="z. B. „1, 21, 100“ – diese Nummern werden bei der automatischen Vergabe übersprungen.">
          <input id="nr-reserve" value={reserveText} onChange={(event) => setReserveText(event.target.value)} />
        </Field>
        <div className="form-actions"><Button type="submit" disabled={busy || !reserveText.trim()}>Reservieren</Button></div>
      </form>
      {range.reserved.length > 0 ? <p className="field-hint">Reserviert: {range.reserved.map((item) => item.formatted).join(", ")}</p> : null}
    </> : null}
  </section>;
}
