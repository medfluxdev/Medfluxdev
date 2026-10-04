"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import type {
  ContractDetailResponse,
  AuditEntryDto,
} from "@/lib/contract-detail-types";
import { formatDate } from "@/lib/format";

interface Props {
  data: ContractDetailResponse;
  orgSlug: string;
  onReload: () => void;
}

const KEY_LABELS: Record<string, string> = {
  "cost.tax_basis": "Steuerbasis",
  "cost.tax_rate_percent": "Steuersatz (%)",
  "date.event_start": "Vertragsbeginn (Übergabedatum)",
  "fact.confirm": "Fakt-Bestätigung",
};

function keyLabel(key: string, labelDe?: string | null): string {
  // UAT Re-Test (Defect 4): bevorzugt die deutsche Bezeichnung aus dem Backend,
  // fallback auf die lokale Karte bzw. den rohen Key (nur bei unbekannten).
  if (labelDe) return labelDe;
  return KEY_LABELS[key] ?? key;
}

function valueText(value: Record<string, unknown> | null): string {
  if (!value) return "–";
  const keys = Object.keys(value);
  if (keys.length === 1) return String(value[keys[0]] ?? "–");
  const date = value["date"];
  if (date) return String(date);
  const percent = value["percent"];
  if (percent != null) return `${percent} %`;
  return JSON.stringify(value);
}

const AUDIT_ACTION_LABEL: Record<string, string> = {
  set: "Gesetzt",
  void: "Zurückgesetzt",
  confirm: "Bestätigt",
};

export default function OverridePanel({ data, orgSlug, onReload }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [taxBasis, setTaxBasis] = useState("");
  const [taxRate, setTaxRate] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [confirmRef, setConfirmRef] = useState("");
  const [note, setNote] = useState("");

  async function submit(body: unknown): Promise<boolean> {
    setBusy(true);
    setMsg(null);
    try {
      await apiPost(
        `/api/contracts/${encodeURIComponent(
          data.contract_id
        )}/overrides?organization_slug=${encodeURIComponent(orgSlug)}`,
        body
      );
      setMsg({ ok: true, text: "Gespeichert." });
      onReload();
      return true;
    } catch {
      setMsg({ ok: false, text: "Speichern fehlgeschlagen." });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function setTaxBasisSubmit() {
    if (!taxBasis || (taxBasis !== "net" && taxBasis !== "gross")) {
      setMsg({ ok: false, text: "Steuerbasis muss 'net' oder 'gross' sein." });
      return;
    }
    await submit({ key: "cost.tax_basis", action: "set", value: taxBasis, note: note || null });
  }

  async function setTaxRateSubmit() {
    const num = Number(taxRate);
    if (!Number.isFinite(num) || num < 0 || num > 100) {
      setMsg({ ok: false, text: "Steuersatz muss 0–100 % sein." });
      return;
    }
    await submit({ key: "cost.tax_rate_percent", action: "set", value: num, note: note || null });
  }

  async function setEventDateSubmit() {
    if (!eventDate) {
      setMsg({ ok: false, text: "Bitte ein Übergabedatum angeben." });
      return;
    }
    await submit({ key: "date.event_start", action: "set", value: eventDate, note: note || null });
  }

  async function confirmFactSubmit() {
    if (!confirmRef) {
      setMsg({ ok: false, text: "Feld-Referenz angeben." });
      return;
    }
    await submit({ key: "fact.confirm", action: "confirm", value: null, fact_ref: confirmRef, note: note || null });
  }

  async function voidKey(key: string) {
    await submit({ key, action: "void", value: null, note: note || null });
  }

  return (
    <section className="detail-card" aria-label="Bestätigen und Überschreiben">
      <h2>Bestätigen &amp; Überschreiben</h2>
      <p className="muted small">
        Manuelle Entscheidungen zu materialen Vertragsfakten (append-only, geprüft
        und nachvollziehbar). Bis zur Benutzerverwaltung (Schritt 16) wird die
        Herkunft als Entwicklungs-Kontext gekennzeichnet.
      </p>

      {msg && (
        <p className={msg.ok ? "form-ok" : "form-error"} role="status">
          {msg.text}
        </p>
      )}

      <div className="override-group">
        <h3>Steuerbasis &amp; Steuersatz der wiederkehrenden Kosten</h3>
        {data.costs.tax_breakdown?.source && (
          <p className="muted small">
            Netto/MwSt./Brutto sind direkt aus dem Vertrag belegt – ein
            Überschreiben ist nur bei Korrekturbedarf nötig.
          </p>
        )}
        <div className="override-row">
          <select
            value={taxBasis}
            onChange={(e) => setTaxBasis(e.target.value)}
            aria-label="Steuerbasis"
          >
            <option value="">– Basis auswählen –</option>
            <option value="net">Netto (zzgl. Umsatzsteuer)</option>
            <option value="gross">Brutto (inkl. Umsatzsteuer)</option>
          </select>
          <button type="button" className="btn btn-sm" onClick={setTaxBasisSubmit} disabled={busy}>
            Basis speichern
          </button>
        </div>
        <div className="override-row">
          <input
            type="number"
            min={0}
            max={100}
            step="0.1"
            placeholder="Steuersatz, z. B. 19"
            value={taxRate}
            onChange={(e) => setTaxRate(e.target.value)}
            aria-label="Steuersatz in Prozent"
          />
          <button type="button" className="btn btn-sm" onClick={setTaxRateSubmit} disabled={busy}>
            Satz speichern
          </button>
        </div>
        <button type="button" className="btn-link" onClick={() => voidKey("cost.tax_basis")} disabled={busy}>
          Steuerbasis zurücksetzen
        </button>
        <button type="button" className="btn-link" onClick={() => voidKey("cost.tax_rate_percent")} disabled={busy}>
          Steuersatz zurücksetzen
        </button>
      </div>

      <div className="override-group">
        <h3>Vertragsbeginn (ereignisbasiert)</h3>
        <div className="override-row">
          <input
            type="date"
            value={eventDate}
            onChange={(e) => setEventDate(e.target.value)}
            aria-label="Übergabedatum / tatsächlicher Vertragsbeginn"
          />
          <button type="button" className="btn btn-sm" onClick={setEventDateSubmit} disabled={busy}>
            Übergabedatum setzen
          </button>
        </div>
        <button type="button" className="btn-link" onClick={() => voidKey("date.event_start")} disabled={busy}>
          Zurücksetzen
        </button>
      </div>

      <div className="override-group">
        <h3>Fakt bestätigen</h3>
        <div className="override-row">
          <input
            type="text"
            placeholder="z. B. dates.start_date (Vertragsbeginn)"
            value={confirmRef}
            onChange={(e) => setConfirmRef(e.target.value)}
            aria-label="Zu bestätigendes Feld"
          />
          <input
            type="text"
            placeholder="Notiz (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            aria-label="Notiz"
          />
          <button type="button" className="btn btn-sm" onClick={confirmFactSubmit} disabled={busy}>
            Bestätigen
          </button>
        </div>
      </div>

      <div className="override-group">
        <h3>Aktuell wirksame manuelle Werte</h3>
        {(data.overrides ?? []).length === 0 && (
          <p className="muted">Keine manuellen Werte gesetzt.</p>
        )}
        <ul className="override-now-list">
          {(data.overrides ?? []).map((o) => (
            <li key={o.key}>
              <strong>{keyLabel(o.key, o.label_de)}</strong>: {valueText(o.value)}
              {o.is_development && (
                <span className="fact-review">Entwicklung (unverifiziert)</span>
              )}
              {o.note && <span className="muted"> – {o.note}</span>}
            </li>
          ))}
        </ul>
      </div>

      <div className="override-group">
        <h3>Audit-Historie (append-only)</h3>
        {(data.audit_log ?? []).length === 0 && (
          <p className="muted">Noch keine Einträge.</p>
        )}
        <ul className="audit-list">
          {(data.audit_log ?? []).map((a: AuditEntryDto) => (
            <li key={a.id}>
              <span className={`audit-action audit-${a.action}`}>
                {AUDIT_ACTION_LABEL[a.action] ?? a.action}
              </span>
              <span className="audit-key">{keyLabel(a.key, a.label_de)}</span>
              {a.action === "set" && (
                <>
                  <span className="audit-old">
                    {valueText((a.old_value as Record<string, unknown> | null) ?? null)
                      ? `${valueText((a.old_value as Record<string, unknown> | null) ?? null)} → `
                      : ""}
                  </span>
                  <span className="audit-value">{valueText(a.value)}</span>
                </>
              )}
              {a.action === "void" && a.old_value != null && (
                <span className="audit-value">
                  {valueText(a.old_value as Record<string, unknown>)} (zurückgesetzt)
                </span>
              )}
              {a.fact_ref && <span className="audit-ref">{a.fact_ref}</span>}
              {a.note && <span className="muted"> – {a.note}</span>}
              <span className="audit-date">
                {a.created_at ? formatDate(a.created_at.slice(0, 10)) : ""}
              </span>
              {a.is_development && (
                <span className="fact-review">Entwicklung/unverifiziert</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
