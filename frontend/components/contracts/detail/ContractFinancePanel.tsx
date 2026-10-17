"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ActionMenu, { type ActionMenuItem } from "@/components/ui/ActionMenu";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import InlineAlert from "@/components/ui/InlineAlert";
import AiOrigin, { AiReviewContext } from "@/components/ui/AiOrigin";
import Signal from "@/components/ui/Signal";
import { formatCurrency, formatDate } from "@/lib/format";
import { SECTION_PARAM, asFixTarget, contractHref, fixLabel } from "@/lib/fix-targets";
import { listLookups, type LookupDto } from "@/lib/domain-api/catalogs";
import { listCostCenters, type CostCenterDto } from "@/lib/domain-api/organizations";
import type { ContractCostsSection } from "@/lib/contract-detail-types";
import {
  INTERVAL_LABEL,
  PAYMENT_TIMING_LABEL,
  PRICE_ADJUSTMENT_LABEL,
  acceptFinanceSuggestion,
  createFinanceEntry,
  deleteFinanceEntry,
  dismissFinanceSuggestion,
  downloadFinanceCsv,
  getFinance,
  setCostAllocations,
  updateFinanceEntry,
  type DirectionSummaryDto,
  type FinanceDto,
  type FinanceEntryDto,
  type FinanceInterval,
  type FinanceSummaryDto,
  type PaymentTiming,
  type SuggestionDto,
} from "@/lib/domain-api/finance";

const EMPTY_ENTRY = { direction: "expense", label: "", cost_type_code: "", amount: "", amount_basis: "net", vat_rate: "19", interval: "monthly", valid_from: "", valid_to: "", apply_price_adjustment: true, payment_timing: "", payment_reminder: false };
type EntryForm = typeof EMPTY_ENTRY;
type NB = "net" | "gross";
// Rohwerte der Analyse (Steuerbasis, Bezugsperiode) in deutscher Schreibweise; Unbekanntes bleibt wie geliefert.
const DOC_WORD: Record<string, string> = {
  net: "Netto", gross: "Brutto", annual: "Jährlich", yearly: "Jährlich", monthly: "Monatlich", quarterly: "Quartalsweise",
  semi_annual: "Halbjährlich", one_time: "Einmalig", once: "Einmalig",
};

type Phase = "past" | "current" | "future";

const NB_KEY = "medflux.kosten.nb";
const PER_YEAR: Record<FinanceInterval, number> = { monthly: 12, quarterly: 4, semi_annual: 2, annual: 1, once: 0 };
// Symbole (24 × 24, nur Striche). Kennfarben: Art der Angabe, nie Zustand (docs/VISUAL_IDENTITY.md).
const PATH = {
  gauge: "M4 16a8 8 0 1 1 16 0M12 16l4-5M12 14.5a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3",
  list: "M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM8 8h8M8 12h8M8 16h5",
  tag: "M3 12V4h8l10 10-8 8zM7.5 7a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3",
  pie: "M12 3a9 9 0 1 0 9 9h-9zM15 3.5A9 9 0 0 1 20.5 9H15z",
  checkdoc: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M9 15l2 2 4-4",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z",
  euro: "M18 6.5A7 7 0 0 0 7.5 12A7 7 0 0 0 18 17.5M4 10h10M4 14h10",
  cal: "M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM16 3v4M8 3v4M3 10h18",
  flag: "M5 21V4h11l-2 4 2 4H5",
  check: "M20 6 9 17l-5-5",
  minus: "M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM8 12h8",
  pay: "M5 6h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zM3 10h18M7 14h3",
  bell: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0",
  pen: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  doc: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5",
  download: "M12 4v11M7 10l5 5 5-5M4 20h16",
  split: "M4 12h16M12 4v16",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  plus: "M12 5v14M5 12h14",
  arrow: "M5 12h14M13 6l6 6-6 6",
  layers: "M12 3 3 8l9 5 9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5",
  info: "M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 11v6M12 7.5v.5",
} as const;
type IconName = keyof typeof PATH;

/** Kachel-Symbol im Kartenkopf (CollapsibleSection setzt Größe und Farbe). */
const tileIcon = (name: IconName) => <svg viewBox="0 0 24 24" focusable="false"><path d={PATH[name]} /></svg>;
/** Kleines Symbol vor einem Wort (dekorativ). */
const Icon = ({ name, className = "fin-ico" }: { name: IconName; className?: string }) => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={PATH[name]} /></svg>;
const signalIcon = (name: IconName) => <Icon name={name} className="signal-icon" />;

type ChipKind = "cost" | "unit" | "dept" | "accent" | "ai" | "neutral";
/** Kennfarben-Plakette: Farbe + Symbol + Wort. */
function Chip({ kind, icon, children, small = false }: { kind: ChipKind; icon?: IconName; children: ReactNode; small?: boolean }) {
  return <span className={`fin-chip fin-chip--${kind}${small ? " fin-chip--sm" : ""}`}>{icon ? <Icon name={icon} /> : null}{children}</span>;
}

function errorText(error: unknown) {
  return error instanceof Error && error.message ? error.message : "Die Änderung konnte nicht gespeichert werden.";
}

const euro = (value: number, currency: string) => formatCurrency(value.toFixed(2), currency);

function hasIncome(summary: FinanceSummaryDto) {
  return Object.values(summary.income).some((value) => value && (Number(value.net) !== 0 || Number(value.gross) !== 0));
}

/** Netto/Brutto eines Eintrags (wie backend/app/finance/calc.net_gross). */
function netGross(item: Pick<FinanceEntryDto, "amount" | "amount_basis" | "vat_rate">) {
  const amount = Number(item.amount);
  const factor = 1 + Number(item.vat_rate) / 100;
  return item.amount_basis === "gross" ? { net: amount / factor, gross: amount } : { net: amount, gross: amount * factor };
}

/** Tag vor einem ISO-Datum (Ende des alten Preises bei „Preis ändern ab …“). */
function dayBefore(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

const isoDays = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / 86_400_000;

/** Volle Monate zwischen zwei ISO-Daten. */
function monthsBetween(from: string, to: string): number {
  const [fy, fm, fd] = from.split("-").map(Number);
  const [ty, tm, td] = to.split("-").map(Number);
  return (ty - fy) * 12 + (tm - fm) - (td < fd ? 1 : 0);
}

function phaseOf(item: FinanceEntryDto, asOf: string): Phase {
  if (item.valid_from > asOf) return "future";
  if (item.interval === "once") return "past";
  return item.valid_to && item.valid_to < asOf ? "past" : "current";
}

/** Vertragsjahr: aus der Preisstaffel der KI, sonst aus dem Vertragsbeginn. */
function contractYear(item: FinanceEntryDto, contractStart: string | null): number | null {
  const staffel = /^costs\.scheduled_prices\.(\d+)$/.exec(item.source_key ?? "");
  if (staffel) return Number(staffel[1]);
  if (!contractStart || item.valid_from < contractStart) return null;
  return Math.floor(monthsBetween(contractStart, item.valid_from) / 12) + 1;
}

// Kurzname: Klammerzusätze (z. B. der MwSt-Hinweis, auch ohne schließende Klammer) und „N. Vertragsjahr“ entfallen;
// das Vertragsjahr steht in der Unterzeile, der volle Name im Tooltip.
const shortTitle = (label: string) => label.replace(/\s*\(.*$/, "").replace(/\s*\d+\.\s*Vertragsjahr$/i, "").trim() || label;
// Der MwSt-Hinweis steht einmal in der Kartenbeschreibung, nicht in jeder Zeile.
const TAX_NOTE = /mwst|mehrwertsteuer|umsatzsteuer|\bust\b/i;

function yearsLabel(from: string, to: string | null): string {
  const start = from.slice(0, 4);
  if (!to || to.slice(0, 4) === start) return start;
  return `${start}/${to.slice(2, 4)}`;
}

function entryToForm(item: FinanceEntryDto): EntryForm {
  return {
    direction: item.direction, label: item.label, cost_type_code: item.cost_type_code ?? "", amount: String(Number(item.amount)), amount_basis: item.amount_basis,
    vat_rate: String(Number(item.vat_rate)), interval: item.interval, valid_from: item.valid_from, valid_to: item.valid_to ?? "",
    apply_price_adjustment: item.apply_price_adjustment, payment_timing: item.payment_timing ?? "", payment_reminder: item.payment_reminder,
  };
}

function entryValues(form: EntryForm): Record<string, unknown> {
  return {
    ...form,
    cost_type_code: form.cost_type_code || null,
    valid_to: form.valid_to || null,
    payment_timing: form.payment_timing || null,
    payment_reminder: Boolean(form.payment_timing) && form.direction === "expense" && form.payment_reminder,
  };
}

function suggestionKind(key: string): string | null {
  return key.startsWith("costs.scheduled_prices.") ? "Preisplan (Staffel)" : null;
}

/**
 * Zahlung je Eintrag als Signal (Farbe + Symbol + Wort). Der Vertrag kennt Zahlungszeitpunkt und Erinnerung,
 * aber keine erfassten Zahlungen – „Bezahlt“ gibt es deshalb (noch) nicht.
 */
/** Stand des Zeitraums neben dem Namen: abgelaufen (grau), aktuell mit Restzeit, geplant (Kosten-Kennfarbe). */
function phaseSignal(phase: Phase, left: number | null) {
  if (phase === "past") return <Signal tone="neutral" size="sm">Abgelaufen</Signal>;
  if (phase === "future") return <Chip kind="cost" icon="cal" small>Geplant</Chip>;
  const rest = left == null ? "unbefristet" : left <= 0 ? "endet diesen Monat" : `noch ${left} ${left === 1 ? "Monat" : "Monate"}`;
  return <Signal tone={left != null && left <= 0 ? "warning" : "info"} size="sm">Aktuell · {rest}</Signal>;
}

function paymentSignal(item: FinanceEntryDto, phase: Phase) {
  if (item.direction !== "expense") return <span className="cw-muted">–</span>;
  if (Number(item.amount) === 0) return <Signal tone="neutral" size="sm" icon={signalIcon("minus")}>Keine Zahlung</Signal>;
  if (phase === "past") return <span className="cw-muted" title="Zeitraum abgelaufen">–</span>;
  if (phase === "future") return <Signal tone="info" size="sm" icon={signalIcon("cal")} title={item.payment_timing ? `Zahlung ${PAYMENT_TIMING_LABEL[item.payment_timing]}` : undefined}>Fällig {item.valid_from.slice(0, 4)}</Signal>;
  if (!item.payment_timing) return <Signal tone="warning" size="sm" icon={signalIcon("pay")} title="Zahlungszeitpunkt nicht erfasst">Nicht erfasst</Signal>;
  return <Signal tone="info" size="sm" icon={signalIcon(item.payment_reminder ? "bell" : "cal")} title={item.payment_reminder ? "Erinnerung 14 Tage vor jeder Zahlung" : undefined}>
    Fällig {PAYMENT_TIMING_LABEL[item.payment_timing]}{item.payment_reminder ? " · Erinnerung" : ""}
  </Signal>;
}

/** Obere Achsengrenze in runden Schritten (1, 2, 2,5, 5 × 10^n), damit die Achse lesbar bleibt. */
function niceMax(value: number): number {
  if (value <= 0) return 0;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].map((factor) => (factor * magnitude) / 5).find((candidate) => candidate * 5 >= value) ?? magnitude * 2;
  return step * 5;
}

/** „jährlich“, „halbjährlich“ … aus dem Anpassungsintervall in Monaten. */
function adjustmentRhythm(months: number | null): string {
  const value = months ?? 12;
  if (value === 12) return "jährlich";
  if (value === 6) return "halbjährlich";
  if (value === 3) return "vierteljährlich";
  if (value % 12 === 0) return `alle ${value / 12} Jahre`;
  return `alle ${value} Monate`;
}

/**
 * Reiter „Finanzen“ (Entwurf „Kosten“): Kosten auf einen Blick → Zu prüfen → Finanzeinträge →
 * Kostenstellen-Aufteilung → Details aus dem Dokument. Gerechnet wird nur im Backend aus den
 * gepflegten Einträgen (backend/app/finance/calc.py); die Balken ohne Vertragsende zeigen die Einträge selbst.
 */
export default function ContractFinancePanel({ contractId, orgSlug, documentCosts = null, contractStart = null, documentBasis = null, findSource }: {
  contractId: string;
  orgSlug: string;
  /** Kosten aus der KI-Analyse (nur mit Analyse): Erklärung, was zur Berechnung fehlt, und Währungskonflikt. */
  documentCosts?: ContractCostsSection | null;
  /** Vertragsbeginn (Vertragsdaten) für „Vertragsjahr N“. */
  contractStart?: string | null;
  /** Steuer, Währung und Bezugsperiode laut Dokument (KI) – nur solange keine Einträge gepflegt sind. */
  documentBasis?: { tax_basis: string | null; tax_rate_percent: number | null; currency: string | null; source_period: string | null } | null;
  /** Fundstelle eines Extraktionsfelds öffnen, falls es eine gibt. */
  findSource?: (sourceField: string) => (() => void) | null;
}) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [data, setData] = useState<FinanceDto | null>(null);
  const [costTypes, setCostTypes] = useState<LookupDto[]>([]);
  const [rechargeModes, setRechargeModes] = useState<LookupDto[]>([]);
  const [centers, setCenters] = useState<CostCenterDto[]>([]);
  const [nb, setNb] = useState<NB>("net");
  const [entryForm, setEntryForm] = useState(EMPTY_ENTRY);
  const [editingEntry, setEditingEntry] = useState<string | null>(null);
  const [priceChange, setPriceChange] = useState<{ id: string; amount: string; from: string } | null>(null);
  const [payment, setPayment] = useState<{ id: string; timing: string; reminder: boolean } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; label: string } | null>(null);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [splitting, setSplitting] = useState(false);
  // ?abschnitt=entries (z. B. „Kosten erfassen“): Formular für einen neuen Eintrag gleich öffnen.
  const linkedSection = useSearchParams()?.get(SECTION_PARAM) ?? null;
  const openedFromLink = useRef(false);
  useEffect(() => {
    if (linkedSection === "entries" && editable && !openedFromLink.current) {
      openedFromLink.current = true;
      setShowEntryForm(true);
    }
  }, [editable, linkedSection]);

  // Netto/Brutto gilt für alle Beträge im Reiter; der Browser merkt sich die Wahl.
  useEffect(() => {
    try {
      if (window.localStorage.getItem(NB_KEY) === "gross") setNb("gross");
    } catch {
      // ohne Speicher: Netto
    }
  }, []);
  function chooseNb(next: NB) {
    setNb(next);
    try {
      window.localStorage.setItem(NB_KEY, next);
    } catch {
      // nur Komfort
    }
  }

  function openEntryForm(preset: Partial<EntryForm> = {}) {
    setEditingEntry(null);
    setEntryForm({ ...EMPTY_ENTRY, ...preset });
    setShowEntryForm(true);
    window.requestAnimationFrame(() => document.getElementById("fin-entries-heading")?.scrollIntoView?.({ block: "start" }));
  }

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

  function closeEntryForm() {
    setShowEntryForm(false);
    setEditingEntry(null);
    setEntryForm(EMPTY_ENTRY);
  }

  async function saveEntry() {
    const values = entryValues(entryForm);
    const ok = editingEntry
      ? await run(() => updateFinanceEntry(orgSlug, contractId, editingEntry, values), "Finanzeintrag gespeichert.")
      : await run(() => createFinanceEntry(orgSlug, contractId, values), "Finanzeintrag angelegt.");
    if (ok) closeEntryForm();
  }

  function editEntry(item: FinanceEntryDto) {
    setPriceChange(null);
    setPayment(null);
    setEditingEntry(item.id);
    setEntryForm(entryToForm(item));
    setShowEntryForm(true);
  }

  // Neuer Preis ab Stichtag: der bisherige Eintrag endet am Vortag, ein neuer übernimmt alle übrigen Angaben.
  async function changePrice(item: FinanceEntryDto, amount: string, from: string) {
    if (!amount.trim() || !from) return;
    if (from <= item.valid_from || (item.valid_to && from > item.valid_to)) {
      setMessage({ tone: "error", text: `Der neue Preis muss nach dem ${formatDate(item.valid_from)}${item.valid_to ? ` und spätestens am ${formatDate(item.valid_to)}` : ""} beginnen.` });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await updateFinanceEntry(orgSlug, contractId, item.id, { valid_to: dayBefore(from) });
      try {
        apply(await createFinanceEntry(orgSlug, contractId, { ...entryValues(entryToForm(item)), amount: amount.trim(), valid_from: from, valid_to: item.valid_to }));
      } catch (error) {
        // Neuer Eintrag gescheitert: altes Ende wiederherstellen, damit kein Zeitraum fehlt.
        apply(await updateFinanceEntry(orgSlug, contractId, item.id, { valid_to: item.valid_to }));
        throw error;
      }
      setPriceChange(null);
      setMessage({ tone: "ok", text: `Neuer Preis ab ${formatDate(from)} gespeichert; der bisherige endet am ${formatDate(dayBefore(from))}.` });
    } catch (error) {
      setMessage({ tone: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  }

  // Zahlungserinnerung (Systemtermin "Zahlung fällig") nur mit gepflegtem Zahlungszeitpunkt.
  async function savePayment(item: FinanceEntryDto, timing: string, reminder: boolean) {
    const ok = await run(() => updateFinanceEntry(orgSlug, contractId, item.id, { payment_timing: timing || null, payment_reminder: Boolean(timing) && reminder }), "Zahlungsangaben gespeichert.");
    if (ok) setPayment(null);
  }

  function openPayment(item: FinanceEntryDto, reminder = item.payment_reminder) {
    setPriceChange(null);
    setPayment({ id: item.id, timing: item.payment_timing ?? "", reminder });
  }

  async function removeConfirmed() {
    if (!confirmDelete) return;
    const target = confirmDelete;
    const ok = await run(() => deleteFinanceEntry(orgSlug, contractId, target.id), "Eintrag gelöscht.");
    if (ok) setConfirmDelete(null);
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

  function suggestionRow(item: SuggestionDto) {
    const values = item.values;
    const currency = String(values.currency ?? "EUR");
    const kind = suggestionKind(item.key);
    const source = findSource?.(item.source_field) ?? null;
    const period = `${values.amount_basis === "gross" ? "brutto" : "netto"}, ${INTERVAL_LABEL[values.interval as FinanceInterval] ?? "Intervall unbekannt"}${values.payment_timing ? ` ${PAYMENT_TIMING_LABEL[values.payment_timing as PaymentTiming] ?? ""}` : ""}, ${values.valid_to ? `${formatDate(String(values.valid_from))} – ${formatDate(String(values.valid_to))}` : `ab ${formatDate(String(values.valid_from))}`}`;
    const title = shortTitle(String(values.label));
    return <li key={item.key}>
      <span><strong>{title}</strong>: {values.amount ? formatCurrency(String(values.amount), currency) : "–"}{period ? ` ${period}` : ""}</span>
      {kind ? <Chip kind="cost" icon="euro" small>{kind}</Chip> : null}
      {item.assumptions && item.assumptions.length > 0 ? <span className="rg-origin rg-origin-ai_corrected">{item.assumptions.join(" · ")}</span> : null}
      <AiOrigin state="unreviewed" onOpenSource={source} factKey={item.source_field} subject={title} />
      {editable ? <span className="rg-actions">
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void run(() => acceptFinanceSuggestion(orgSlug, contractId, "finance", item.key), "Vorschlag übernommen.")}>Übernehmen</button>
        <button type="button" className="btn" disabled={busy} onClick={() => void run(() => dismissFinanceSuggestion(orgSlug, contractId, "finance", item.key), "Vorschlag verworfen.")}>Verwerfen</button>
      </span> : null}
    </li>;
  }

  function renderEntryForm(label: string) {
    return <form className="rg-transition fin-form" aria-label={label} onSubmit={(event) => { event.preventDefault(); void saveEntry(); }}>
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
        <label>Zahlungszeitpunkt<select value={entryForm.payment_timing} onChange={(event) => setEntryForm((form) => ({ ...form, payment_timing: event.target.value, payment_reminder: event.target.value ? form.payment_reminder : false }))}><option value="">nicht erfasst</option>{(Object.keys(PAYMENT_TIMING_LABEL) as PaymentTiming[]).map((key) => <option key={key} value={key}>{PAYMENT_TIMING_LABEL[key]}</option>)}</select></label>
        <label className="rg-check"><input type="checkbox" checked={entryForm.payment_reminder} disabled={!entryForm.payment_timing || entryForm.direction !== "expense"} onChange={(event) => setEntryForm((form) => ({ ...form, payment_reminder: event.target.checked }))} />An Zahlung erinnern (14 Tage vorher)</label>
      </div>
      <div className="rg-actions"><button type="button" className="btn" onClick={closeEntryForm}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
    </form>;
  }

  if (!data) return <section className="cw-section"><p role={message ? "alert" : "status"}>{message?.text ?? "Finanzdaten werden geladen…"}</p></section>;

  const asOf = data.as_of;
  const allocationSum = allocations.reduce((sum, item) => sum + (Number(item.share_percent) || 0), 0);
  const costTypeLabel = (code: string | null) => costTypes.find((item) => item.code === code)?.label ?? code ?? "–";
  const suggestionCount = data.suggestions.entries.length;
  const hasEntries = data.entries.length > 0;
  const anyIncome = data.entries.some((item) => item.direction === "income");
  const showCostType = data.entries.some((item) => item.cost_type_code);
  const main = data.summaries[0] ?? null;
  const currency = main?.currency ?? "EUR";
  const contractEnd = main?.contract_end ?? null;
  const nbWord = nb === "net" ? "netto" : "brutto";
  const otherWord = nb === "net" ? "brutto" : "netto";
  const pick = (value: { net: number; gross: number }) => (nb === "net" ? value.net : value.gross);
  const other = (value: { net: number; gross: number }) => (nb === "net" ? value.gross : value.net);
  // Erklärung aus der Analyse, solange nichts gepflegt ist: was gefunden wurde und was zur Berechnung fehlt.
  const availability = !hasEntries && documentCosts?.availability && (documentCosts.annual_recurring.amount == null || documentCosts.availability.manual_input_required) ? documentCosts.availability : null;
  const reviewCount = suggestionCount + (availability ? 1 : 0);
  const phases = new Map(data.entries.map((item) => [item.id, phaseOf(item, asOf)]));
  const activeCount = [...phases.values()].filter((phase) => phase === "current").length;
  const pa = data.price_adjustment;
  const expenses = data.entries.filter((item) => item.direction === "expense");

  // Zeiträume = laufende Ausgaben-Einträge der Hauptwährung, zeitlich sortiert (gleiche Zeilen wie die Tabelle).
  const periods = expenses.filter((item) => item.interval !== "once" && item.currency === currency).sort((a, b) => a.valid_from.localeCompare(b.valid_from));
  const yearly = periods.map((item) => {
    const value = netGross(item);
    const factor = PER_YEAR[item.interval];
    return { item, phase: phases.get(item.id)!, label: yearsLabel(item.valid_from, item.valid_to), value: { net: value.net * factor, gross: value.gross * factor } };
  });
  const maxYearly = Math.max(0, ...yearly.map((row) => pick(row.value)));
  const allYears = periods.length > 0 && periods.every((item) => item.valid_to && Math.abs(isoDays(item.valid_to) - isoDays(item.valid_from) - 364.5) <= 2);
  const showPeriods = periods.length >= 2;

  // Kopfzahlen-Untertitel: nur Angaben, die aus den Einträgen selbst ablesbar sind.
  const monthsThisYear = Array.from({ length: 12 }, (_, index) => `${asOf.slice(0, 4)}-${String(index + 1).padStart(2, "0")}`)
    .filter((month) => expenses.some((item) => item.interval === "once"
      ? item.valid_from.slice(0, 7) === month
      : item.valid_from.slice(0, 7) <= month && (!item.valid_to || item.valid_to.slice(0, 7) >= month))).length;
  const firstStart = expenses.reduce<string | null>((first, item) => (!first || item.valid_from < first ? item.valid_from : first), null);
  const currentYear = contractStart && asOf >= contractStart && (!contractEnd || asOf <= contractEnd) ? Math.floor(monthsBetween(contractStart, asOf) / 12) + 1 : null;

  const glance = (value: { net: string; gross: string } | null) => (value ? { net: Number(value.net), gross: Number(value.gross) } : null);
  const annual = main ? glance(main.expense.annual_run_rate) : null;

  // Vertragsjahre (Backend, mit Preisanpassung) für Diagramm, Preisanpassung und „Ohne Erhöhung“.
  const years = main?.contract_years ?? [];
  const fullYears = years.filter((year) => !year.partial);
  const firstFull = fullYears[0] ?? null;
  const lastFull = fullYears[fullYears.length - 1] ?? null;
  const lastYear = years[years.length - 1] ?? null;
  const lastFactor = lastYear ? Number(lastYear.factor) : 1;
  const adjustmentCount = years.filter((year, index) => index > 0 && Number(year.factor) > Number(years[index - 1].factor)).length;
  const withoutIncrease = main?.total_without_adjustment ? glance(main.total_without_adjustment) : null;
  const totalTerm = main?.expense.total_term ? glance(main.expense.total_term) : null;
  const axisMax = niceMax(Math.max(0, ...years.map((year) => pick(glance(year.amount)!))));
  const axisTicks = axisMax > 0 ? [0, 1, 2, 3, 4, 5].map((step) => (axisMax / 5) * step) : [];
  const axisEuro = (amount: number) => new Intl.NumberFormat("de-DE", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  const nextMonthStart = (() => { const [y, m] = asOf.split("-").map(Number); return m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, "0")}-01`; })();

  const primaryCenter = data.primary_cost_center ?? null;

  // Kostenstellen-Tabelle: Aufteilung oder (ohne Aufteilung) die Hauptkostenstelle mit 100 %. Beträge netto aus dem Backend;
  // brutto im Verhältnis der Jahreskosten brutto/netto (folgt dem Netto/Brutto-Umschalter).
  const runRate = main?.expense.annual_run_rate ? glance(main.expense.annual_run_rate) : null;
  const grossFactor = runRate && runRate.net > 0 ? runRate.gross / runRate.net : null;
  const splitValue = (net: string | null) => (net == null ? null : nb === "net" ? Number(net) : grossFactor != null ? Number(net) * grossFactor : null);
  const splitRows = data.allocations.length
    ? data.allocations.map((item) => ({ id: item.cost_center_id, code: item.code, name: item.name, share: Number(item.share_percent), annual: item.annual_net, primary: item.cost_center_id === data.primary_cost_center_id }))
    : primaryCenter ? [{ id: primaryCenter.cost_center_id, code: primaryCenter.code, name: primaryCenter.name, share: 100, annual: primaryCenter.annual_net, primary: true }] : [];
  const splitShare = splitRows.reduce((sum, row) => sum + row.share, 0);
  const splitAmounts = splitRows.map((row) => splitValue(row.annual));
  const splitAmount = splitAmounts.length && splitAmounts.every((value) => value != null) ? splitAmounts.reduce<number>((sum, value) => sum + value!, 0) : null;
  const splitBasis = runRate ? `Basis: ${euro(pick(runRate), currency)} ${nbWord} / Jahr.` : "Basis: Jahreskosten noch nicht gepflegt.";

  // Berechnungsgrundlage: aus den aktuellen Ausgaben (sonst allen Einträgen); ohne Einträge laut Dokument. Nichts wird ergänzt.
  const basisFrom = expenses.filter((item) => phases.get(item.id) === "current");
  const basisEntries = basisFrom.length ? basisFrom : data.entries;
  const sameOr = (values: string[]) => { const unique = [...new Set(values)]; return unique.length === 1 ? unique[0] : "Unterschiedlich"; };
  const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
  const basisRows: [string, string][] | null = hasEntries
    ? [
      ["Steuerbasis", sameOr(basisEntries.map((item) => (item.amount_basis === "net" ? "Netto" : "Brutto")))],
      ["Mehrwertsteuer", sameOr(basisEntries.map((item) => `${Number(item.vat_rate).toLocaleString("de-DE")} %`))],
      ["Währung", sameOr(basisEntries.map((item) => item.currency))],
      ["Bezugsperiode", sameOr(basisEntries.map((item) => capital(INTERVAL_LABEL[item.interval])))],
    ]
    : documentBasis
      ? [
        ["Steuerbasis", documentBasis.tax_basis ? DOC_WORD[documentBasis.tax_basis] ?? documentBasis.tax_basis : "Nicht angegeben"],
        ["Mehrwertsteuer", documentBasis.tax_rate_percent != null ? `${documentBasis.tax_rate_percent.toLocaleString("de-DE")} %` : "Nicht angegeben"],
        ["Währung", documentBasis.currency ?? "Nicht angegeben"],
        ["Bezugsperiode", documentBasis.source_period ? DOC_WORD[documentBasis.source_period] ?? documentBasis.source_period : "Nicht angegeben"],
      ]
      : null;

  const paText = pa.kind
    ? `${PRICE_ADJUSTMENT_LABEL[pa.kind] ?? "Unbekannt"}${pa.percent ? ` ${Number(pa.percent).toLocaleString("de-DE")} %` : ""}${pa.index_name ? ` (${pa.index_name})` : ""}`
    : "Nicht erfasst";
  const paRow = <div key="pa" className="fin-basis-pa">
    <dt>Preisanpassung</dt>
    <dd>{paText}{pa.next_date ? <span className="fin-basis-sub">nächste {formatDate(pa.next_date)}</span> : null}
      <Link scroll={false} className="rg-link fin-basis-sub" href={contractHref(contractId, { tab: "register", field: "price_adjustment_kind" })}>{pa.kind ? "In den Vertragsdaten ändern" : "Erfassen"}</Link></dd>
  </div>;

  const columnCount = 6 + (showCostType ? 1 : 0) + (editable ? 1 : 0);
  const changing = priceChange ? data.entries.find((item) => item.id === priceChange.id) ?? null : null;
  const paying = payment ? data.entries.find((item) => item.id === payment.id) ?? null : null;
  const bases = new Set(data.entries.map((item) => `${item.amount_basis}:${Number(item.vat_rate)}`));
  const taxLine = hasEntries && bases.size === 1
    ? (() => { const first = data.entries[0]; const vat = Number(first.vat_rate).toLocaleString("de-DE"); return first.amount_basis === "net" ? ` Erfasst netto, zzgl. ${vat} % MwSt.` : ` Erfasst brutto, inkl. ${vat} % MwSt.`; })()
    : "";

  function entryMenu(item: FinanceEntryDto): ActionMenuItem[] {
    const source = item.source_key ? findSource?.(item.source_key) ?? null : null;
    const items: ActionMenuItem[] = [{ label: "Bearbeiten", icon: <Icon name="pen" />, onSelect: () => editEntry(item) }];
    if (item.interval !== "once") items.push({ label: "Preis ändern ab …", icon: <Icon name="euro" />, onSelect: () => { setPayment(null); setPriceChange({ id: item.id, amount: "", from: "" }); } });
    if (item.direction === "expense") {
      items.push(item.payment_reminder
        ? { label: "Zahlungserinnerung ausschalten", icon: <Icon name="bell" />, onSelect: () => void savePayment(item, item.payment_timing ?? "", false) }
        : { label: "An Zahlung erinnern", icon: <Icon name="bell" />, onSelect: () => (item.payment_timing ? void savePayment(item, item.payment_timing, true) : openPayment(item, true)) });
    }
    if (source) items.push({ label: "Quelle im Dokument", icon: <Icon name="doc" />, onSelect: source });
    items.push("separator", { label: "Löschen", icon: <Icon name="trash" />, danger: true, onSelect: () => setConfirmDelete({ id: item.id, label: item.label }) });
    return items;
  }

  function entryRow(item: FinanceEntryDto) {
    const phase = phases.get(item.id)!;
    const value = netGross(item);
    const year = contractYear(item, contractStart);
    const note = item.note && !TAX_NOTE.test(item.note) ? item.note : null;
    const left = phase === "current" && item.valid_to ? monthsBetween(asOf, item.valid_to) : null;
    const source = item.source_key ? findSource?.(item.source_key) ?? null : null;
    const needsPayment = editable && item.direction === "expense" && phase === "current" && !item.payment_timing && Number(item.amount) !== 0;
    return <tr key={item.id} className={phase === "current" ? "is-now" : phase === "past" ? "is-past" : undefined}>
      <td className="fin-mono">{item.interval === "once" ? formatDate(item.valid_from) : <>{formatDate(item.valid_from)} –<br />{item.valid_to ? formatDate(item.valid_to) : "offen"}</>}</td>
      <th scope="row">
        <span className="fin-row-title" title={[item.label, note].filter(Boolean).join(" – ")}><span className="fin-rowic fin-rowic--cost"><Icon name="euro" /></span>{year ? `Vertragsjahr ${year}` : shortTitle(item.label)}{phaseSignal(phase, left)}</span>
      </th>
      {showCostType ? <td>{costTypeLabel(item.cost_type_code)}</td> : null}
      <td className="num"><span className="fin-amount">{euro(pick(value), item.currency)}</span><span className="fin-row-sub">{Number(item.amount) === 0 ? "kostenfrei" : `${euro(other(value), item.currency)} ${otherWord}`}</span></td>
      <td>{INTERVAL_LABEL[item.interval]}</td>
      <td>{paymentSignal(item, phase)}</td>
      <td>{item.origin === "ai_confirmed"
        ? <AiOrigin state="confirmed" onOpenSource={source} factKey={item.source_key} subject={shortTitle(item.label)} detail={item.created_by_name ? `übernommen von ${item.created_by_name}` : null} />
        : <Signal tone="neutral" size="sm">Manuell</Signal>}</td>
      {editable ? <td><span className="fin-acts">
        {needsPayment ? <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => openPayment(item)}><Icon name="pay" />Zahlung erfassen</button> : null}
        <ActionMenu label={`Weitere Aktionen: ${item.label}`} items={entryMenu(item)} disabled={busy} />
      </span></td> : null}
    </tr>;
  }

  const nbToggle = <span className="fin-nb" role="group" aria-label="Netto oder Brutto">
    <button type="button" aria-pressed={nb === "net"} onClick={() => chooseNb("net")}>Netto</button>
    <button type="button" aria-pressed={nb === "gross"} onClick={() => chooseNb("gross")}>Brutto</button>
  </span>;

  const deleteConfirm = confirmDelete ? <div className="rg-transition fin-confirm" role="group" aria-label="Löschen bestätigen">
    <span>„{confirmDelete.label}“ löschen? Das lässt sich nicht rückgängig machen.</span>
    <span className="rg-actions"><button type="button" className="btn" onClick={() => setConfirmDelete(null)}>Abbrechen</button><button type="button" className="btn btn-danger" disabled={busy} onClick={() => void removeConfirmed()}>Löschen</button></span>
  </div> : null;

  return <div className="rg-panel fin-panel">
    <CollapsibleSection id="fin-summary" title={years.length ? `Kosten auf einen Blick · ${years.length} ${years.length === 1 ? "Vertragsjahr" : "Vertragsjahre"}` : "Kosten auf einen Blick"} tone="cost" icon={tileIcon("gauge")}
      description={`Kalkulatorisch nach ganzen Monaten aus den gepflegten Finanzeinträgen · Stand ${formatDate(asOf)}`}
      summary={annual ? `${euro(pick(annual), currency)} ${nbWord} jährlich` : "Noch nicht gepflegt"}
      actions={<>{nbToggle}{hasEntries ? <button type="button" className="btn" onClick={() => void exportCsv(true, true)} aria-label="Export als CSV"><Icon name="download" />CSV</button> : null}{hasEntries && anyIncome ? <button type="button" className="btn" onClick={() => void exportCsv(true, false)}>Nur Ausgaben</button> : null}</>}>
      {documentCosts?.currency_conflict ? <InlineAlert tone="warning" role="status">Das Dokument nennt Beträge in verschiedenen Währungen. Bitte die Einträge prüfen – Summen werden je Währung getrennt geführt.</InlineAlert> : null}
      {data.summaries.map((summary, position) => {
        const tile = (key: keyof DirectionSummaryDto, direction: "expense" | "income" = "expense") => glance(summary[direction][key]);
        const value = (money: { net: number; gross: number } | null) => (money ? euro(pick(money), summary.currency) : "–");
        const main_ = tile("annual_run_rate");
        const past = tile("to_date");
        const remaining = tile("remaining_to_end");
        const total = tile("total_term");
        return <div key={summary.currency} className="fin-glance-block">
          <dl className="fin-kpis" aria-label={`Ausgaben ${summary.currency}`}>
            <div className="fin-kpi fin-kpi--main">
              <dt><Icon name="euro" />Jährlich (aktuell)</dt>
              <dd><span className="fin-kpi-value num">{value(main_)}</span><span className="fin-kpi-sub">{main_ ? [position === 0 && currentYear ? `Vertragsjahr ${currentYear}` : nbWord, `${euro(other(main_), summary.currency)} ${otherWord}`].join(" · ") : "nicht berechenbar"}</span></dd>
            </div>
            <div className="fin-kpi fin-kpi--year">
              <dt><Icon name="cal" />Laufendes Jahr {asOf.slice(0, 4)}</dt>
              <dd><span className="fin-kpi-value num">{value(tile("current_year"))}</span><span className="fin-kpi-sub">{position === 0 && monthsThisYear > 0 ? (monthsThisYear === 12 ? "Gesamtes Kalenderjahr" : `${monthsThisYear} von 12 Monaten`) : nbWord}</span></dd>
            </div>
            <div className="fin-kpi fin-kpi--end">
              <dt><Icon name="flag" />Bis Vertragsende</dt>
              <dd><span className="fin-kpi-value num">{value(remaining)}</span><span className="fin-kpi-sub">{summary.contract_end ? `Verbleibend ab ${formatDate(nextMonthStart)} bis ${formatDate(summary.contract_end)}` : "Vertragsende unbekannt"}</span></dd>
            </div>
            <div className="fin-kpi fin-kpi--past">
              <dt><Icon name="check" />Bisher kalkuliert</dt>
              <dd><span className="fin-kpi-value num">{value(past)}</span><span className="fin-kpi-sub">{position === 0 && firstStart ? `seit ${formatDate(firstStart)}` : nbWord}</span></dd>
            </div>
            <div className="fin-kpi fin-kpi--total">
              <dt><Icon name="layers" />Gesamtkosten</dt>
              <dd><span className="fin-kpi-value num">{value(total)}</span><span className="fin-kpi-sub">{total ? `Gesamte Vertragslaufzeit${summary.projected_adjustment ? " · inkl. Erhöhungen" : ""}` : "nicht berechenbar"}</span></dd>
            </div>
          </dl>
          <div className="fin-info">
            <span><Icon name="info" />Alle Hauptbeträge {nbWord}, sofern nicht anders angegeben.</span>
            {past && remaining && total ? <span className="num">{euro(pick(past), summary.currency)} bisher + {euro(pick(remaining), summary.currency)} verbleibend = <strong>{euro(pick(total), summary.currency)} gesamt</strong></span> : null}
          </div>
          {hasIncome(summary) ? <p className="fin-income">Einnahmen: jährlich {value(tile("annual_run_rate", "income"))} · laufendes Jahr {value(tile("current_year", "income"))} · bisher {value(tile("to_date", "income"))} ({nbWord})</p> : null}
          {summary.notes.length > 0 ? <ul className="rg-explanation">{(summary.note_items ?? summary.notes.map((text) => ({ text, target: null }))).map((note) => {
            const target = asFixTarget(note.target);
            return <li key={note.text}>{note.text}{target ? <> <Link scroll={false} className="rg-link" href={contractHref(contractId, target)}>{fixLabel(target)}</Link></> : null}</li>;
          })}</ul> : null}
        </div>;
      })}
      {main && pa.kind ? <section className="fin-pa" aria-labelledby="fin-pa-heading">
        <div className="fin-pa-main">
          <div className="fin-pa-head"><h3 id="fin-pa-heading">Preisanpassung</h3><Chip kind="accent" small>{PRICE_ADJUSTMENT_LABEL[pa.kind] ?? "Unbekannt"}</Chip></div>
          {pa.kind === "percent" && pa.percent
            ? <p className="fin-pa-value"><span className="num">+{Number(pa.percent).toLocaleString("de-DE")} %</span> <span className="fin-pa-rhythm">{adjustmentRhythm(pa.interval_months)}</span></p>
            : <p className="fin-pa-value">{pa.kind === "index" ? pa.index_name ?? "Index" : PRICE_ADJUSTMENT_LABEL[pa.kind] ?? "Unbekannt"}</p>}
          <p className="fin-pa-sub">{pa.kind === "percent" ? "Feste Steigerung · keine Indexbindung." : pa.kind === "fixed" ? "Keine Preisanpassung vereinbart." : "Künftige Beträge können nicht vorausberechnet werden."}</p>
          {editable ? <Link scroll={false} className="rg-link fin-pa-edit" href={contractHref(contractId, { tab: "register", field: "price_adjustment_kind" })}>In den Vertragsdaten ändern</Link> : null}
        </div>
        {pa.kind === "percent" && pa.percent ? <div className="fin-pa-calc">
          <h4>Berechnung</h4>
          <dl>
            <div><dt>Auf den</dt><dd>Vorjahrespreis</dd></div>
            <div><dt>Nächste</dt><dd>{pa.next_date ? formatDate(pa.next_date) : "Nicht erfasst"}</dd></div>
            {years.length ? <div><dt>Anpassungen</dt><dd>{adjustmentCount} in {years.length} {years.length === 1 ? "Jahr" : "Jahren"}</dd></div> : null}
          </dl>
        </div> : null}
        {pa.kind === "percent" && pa.percent && firstFull && lastFull && firstFull !== lastFull ? <div className="fin-pa-prices">
          <div><span>Startpreis / Jahr</span><strong className="num">{euro(pick(glance(firstFull.amount)!), currency)}</strong><small>Vertragsjahr {firstFull.index}</small></div>
          <div><span>Preis im Jahr {lastFull.index}</span><strong className="num">{euro(pick(glance(lastFull.amount)!), currency)}</strong><small>Vertragsjahr {lastFull.index}</small></div>
          <p className="fin-pa-formula">Vorjahrespreis × {(1 + Number(pa.percent) / 100).toLocaleString("de-DE", { maximumFractionDigits: 4 })}</p>
        </div> : null}
      </section> : null}
      {years.length ? <section className="fin-chart" aria-labelledby="fin-chart-heading">
        <h3 id="fin-chart-heading">{main?.projected_adjustment ? "Jahreskosten inklusive Steigerung" : "Jahreskosten je Vertragsjahr"} <span className="fin-chart-unit">({nbWord})</span></h3>
        <div className="fin-cols" aria-hidden="true">
          <div className="fin-axis">{axisTicks.slice().reverse().map((tick) => <span key={tick}>{axisEuro(tick)}</span>)}</div>
          <div className="fin-plot">
            {axisTicks.map((tick) => <span key={tick} className="fin-grid" style={{ bottom: `${axisMax > 0 ? (tick / axisMax) * 100 : 0}%` }} />)}
            {years.map((year) => {
              const amount = pick(glance(year.amount)!);
              const phase = asOf > year.end ? "past" : asOf >= year.start ? "now" : "future";
              return <div key={year.index} className={`fin-col is-${phase}`}>
                <span className="fin-col-bar" style={{ height: `${axisMax > 0 ? (amount / axisMax) * 100 : 0}%` }}><span className="fin-col-value num">{euro(amount, currency)}</span></span>
              </div>;
            })}
          </div>
          <span />
          <div className="fin-col-labels">{years.map((year) => {
            const now = asOf >= year.start && asOf <= year.end;
            return <span key={year.index} className={now ? "is-now" : undefined}>Jahr {year.index}{year.partial ? ` (${year.months} Mon.)` : ""}{now ? <Chip kind="cost" small>Aktuell</Chip> : null}</span>;
          })}</div>
        </div>
        <table className="visually-hidden" aria-label="Jahreskosten je Vertragsjahr">
          <thead><tr><th scope="col">Vertragsjahr</th><th scope="col">Zeitraum</th><th scope="col">Jahreskosten {nbWord}</th></tr></thead>
          <tbody>{years.map((year) => <tr key={year.index}><th scope="row">Jahr {year.index}</th><td>{formatDate(year.start)} – {formatDate(year.end)}</td><td>{euro(pick(glance(year.amount)!), currency)}</td></tr>)}</tbody>
        </table>
      </section> : showPeriods ? <div className="fin-years">
        <div className="fin-caption"><span>{allYears ? "Kosten je Vertragsjahr" : "Jahreskosten je Zeitraum"} ({nbWord}{pa.kind === "percent" ? ", ohne Preisanpassung" : ""})</span>{main?.expense.total_term ? <span>Summe {euro(pick(glance(main.expense.total_term)!), currency)}</span> : null}</div>
        <div className="fin-bars" aria-hidden="true">
          {yearly.map((row) => <div key={row.item.id} className={`fin-bar${row.phase === "current" ? " is-now" : row.phase === "past" ? " is-past" : ""}`}>
            <span className="fin-track"><span className="fin-fill" style={{ width: `${maxYearly > 0 ? (pick(row.value) / maxYearly) * 100 : 0}%` }} /></span>
            <span className="fin-bar-label"><span>{row.label}</span><span>{euro(pick(row.value), currency)}</span></span>
          </div>)}
        </div>
        <table className="visually-hidden" aria-label={allYears ? "Kosten je Vertragsjahr" : "Jahreskosten je Zeitraum"}>
          <thead><tr><th scope="col">Zeitraum</th><th scope="col">Jahreskosten {nbWord}</th><th scope="col">Stand</th></tr></thead>
          <tbody>{yearly.map((row) => <tr key={row.item.id}><th scope="row">{formatDate(row.item.valid_from)} – {row.item.valid_to ? formatDate(row.item.valid_to) : "offen"}</th><td>{euro(pick(row.value), currency)}</td><td>{row.phase === "current" ? "aktuell" : row.phase === "past" ? "abgelaufen" : "künftig"}</td></tr>)}</tbody>
        </table>
      </div> : null}
      {withoutIncrease && totalTerm && main?.projected_adjustment ? <dl className="fin-increase">
        <div><dt>Ohne Erhöhung ({years.length} {years.length === 1 ? "Jahr" : "Jahre"})</dt><dd className="num">{euro(pick(withoutIncrease), currency)}</dd></div>
        <div><dt>Mehrkosten über {years.length} {years.length === 1 ? "Jahr" : "Jahre"}</dt><dd className="num fin-increase-up">+{euro(pick(totalTerm) - pick(withoutIncrease), currency)}</dd></div>
        {lastFactor > 1 && lastYear ? <div><dt>Preissteigerung bis Jahr {lastYear.index}</dt><dd className="num fin-increase-up">+{((lastFactor - 1) * 100).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %</dd></div> : null}
      </dl> : null}
      {main ? <div className="fin-glance-foot">
        <span>Alle Beträge {nbWord}, sofern nicht anders angegeben.{main.projected_adjustment ? " Jährlich aufgezinst;" : ""} Anzeige auf Cent gerundet.</span>
      </div> : null}
      {!hasEntries ? <p className="fin-foot">
        {suggestionCount > 0
          ? <span>Noch nicht gepflegt – {suggestionCount === 1 ? "ein KI-Vorschlag liegt" : `${suggestionCount} KI-Vorschläge liegen`} unter „Zu prüfen“ bereit.</span>
          : <span>Noch nicht gepflegt.{editable ? <> <button type="button" className="rg-link" onClick={() => openEntryForm()}>Eintrag erfassen</button></> : null}</span>}
      </p> : null}
    </CollapsibleSection>

    {message ? <p role={message.tone === "error" ? "alert" : "status"} className={message.tone === "error" ? "rg-error" : "rg-ok"}>{message.text}</p> : null}

    {reviewCount > 0 ? <CollapsibleSection id="fin-ai" className="rg-ai" title="Zu prüfen" tone="ai" icon={tileIcon("spark")}
      description="Angaben aus dem Vertrag. Erst übernommene Vorschläge fließen in die Berechnung ein; Annahmen sind gekennzeichnet."
      summary={`${reviewCount} ${reviewCount === 1 ? "Angabe" : "Angaben"} zu prüfen`}>
      {suggestionCount > 0 ? <ul>{data.suggestions.entries.map(suggestionRow)}</ul> : null}
      {availability ? <div className="cw-finance-availability">
        <p><strong>Warum die Kosten noch nicht berechnet sind:</strong> {availability.summary_de}{availability.explanation_de ? ` ${availability.explanation_de}` : ""}</p>
        {availability.found_facts.length > 0 ? <div><strong>Gefunden</strong><ul>{availability.found_facts.map((fact) => <li key={fact.key}>{fact.label_de}: {fact.value}{fact.period_hint ? ` · ${fact.period_hint}` : ""}</li>)}</ul></div> : null}
        {availability.missing_inputs.length > 0 ? <div><strong>Fehlt noch</strong><ul>{availability.missing_inputs.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
        {editable ? <button type="button" className="btn" onClick={() => openEntryForm()}>Eintrag erfassen</button> : null}
      </div> : null}
    </CollapsibleSection> : null}

    <CollapsibleSection id="fin-entries" title="Finanzeinträge" tone="cost" icon={tileIcon("list")}
      description={`Laufende Kosten mit Gültigkeitszeitraum.${taxLine}${pa.kind === "percent" && pa.percent ? ` Beträge wie vereinbart; die Preisanpassung (+${Number(pa.percent).toLocaleString("de-DE")} % ${adjustmentRhythm(pa.interval_months)}) ist in „Kosten auf einen Blick“ eingerechnet.` : ""}`}
      summary={hasEntries ? `${data.entries.length} ${data.entries.length === 1 ? "Eintrag" : "Einträge"} · ${activeCount} aktuell` : "Keine Einträge"}
      actions={editable && !showEntryForm ? <button type="button" className="btn btn-primary" onClick={() => openEntryForm()}><Icon name="plus" />Eintrag erstellen</button> : undefined}>
      {showEntryForm ? renderEntryForm(editingEntry ? "Finanzeintrag bearbeiten" : "Finanzeintrag anlegen") : null}
      {changing && priceChange ? <form className="rg-transition fin-form" aria-label={`Preis ändern: ${changing.label}`} onSubmit={(event) => { event.preventDefault(); void changePrice(changing, priceChange.amount, priceChange.from); }}>
        <p className="cw-muted">„{shortTitle(changing.label)}“ bisher {formatCurrency(changing.amount, changing.currency)} {changing.amount_basis === "net" ? "netto" : "brutto"}, {INTERVAL_LABEL[changing.interval]}. Der bisherige Eintrag endet am Vortag; alle übrigen Angaben werden übernommen.</p>
        <div className="rg-form-grid">
          <label>Neuer Betrag *<input required inputMode="decimal" value={priceChange.amount} onChange={(event) => setPriceChange((current) => current && ({ ...current, amount: event.target.value }))} /></label>
          <label>Gültig ab *<input type="date" required min={changing.valid_from} max={changing.valid_to ?? undefined} value={priceChange.from} onChange={(event) => setPriceChange((current) => current && ({ ...current, from: event.target.value }))} /></label>
        </div>
        <div className="rg-actions"><button type="button" className="btn" onClick={() => setPriceChange(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Neuen Preis speichern</button></div>
      </form> : null}
      {paying && payment ? <form className="rg-transition fin-form" aria-label={`Zahlung erfassen: ${paying.label}`} onSubmit={(event) => { event.preventDefault(); void savePayment(paying, payment.timing, payment.reminder); }}>
        <p className="cw-muted">Wann wird „{shortTitle(paying.label)}“ bezahlt? Mit Erinnerung erscheint jede Zahlung als Termin unter „Fristen &amp; Aufgaben“ (14 Tage vorher).</p>
        <div className="rg-form-grid">
          <label>Zahlungszeitpunkt<select value={payment.timing} onChange={(event) => setPayment((current) => current && ({ ...current, timing: event.target.value, reminder: event.target.value ? current.reminder : false }))}><option value="">nicht erfasst</option>{(Object.keys(PAYMENT_TIMING_LABEL) as PaymentTiming[]).map((key) => <option key={key} value={key}>{PAYMENT_TIMING_LABEL[key]}</option>)}</select></label>
          <label className="rg-check"><input type="checkbox" checked={payment.reminder} disabled={!payment.timing} onChange={(event) => setPayment((current) => current && ({ ...current, reminder: event.target.checked }))} />An Zahlung erinnern</label>
        </div>
        <div className="rg-actions">{paying.payment_reminder ? <Link scroll={false} className="rg-link" href={contractHref(contractId, { tab: "deadlines" })}>Termin ansehen</Link> : null}<button type="button" className="btn" onClick={() => setPayment(null)}>Abbrechen</button><button type="submit" className="btn btn-primary" disabled={busy}>Speichern</button></div>
      </form> : null}
      {deleteConfirm}
      {!hasEntries ? <p className="cw-muted">Keine Einträge.</p> : <div className="table-scroll"><table className="rg-table fin-table" aria-label="Finanzeinträge">
        <thead><tr><th scope="col">Gültig</th><th scope="col">Bezeichnung</th>{showCostType ? <th scope="col">Kostenart</th> : null}<th scope="col" className="num">Betrag {nbWord}</th><th scope="col">Intervall</th><th scope="col">Zahlung</th><th scope="col">Herkunft</th>{editable ? <th scope="col"><span className="sr-only">Aktionen</span></th> : null}</tr></thead>
        {anyIncome
          ? <>
            <tbody><tr className="fin-group"><th scope="rowgroup" colSpan={columnCount}>Ausgaben</th></tr>{expenses.map(entryRow)}</tbody>
            <tbody><tr className="fin-group"><th scope="rowgroup" colSpan={columnCount}>Einnahmen</th></tr>{data.entries.filter((item) => item.direction === "income").map(entryRow)}</tbody>
          </>
          : <tbody>{data.entries.map(entryRow)}</tbody>}
      </table></div>}
      {hasEntries && !showCostType ? <p className="fin-foot"><span className="fin-k"><Icon name="minus" />Kostenart: in keinem Eintrag gepflegt – Spalte ausgeblendet{editable ? <> · <button type="button" className="rg-link" onClick={() => editEntry(data.entries.find((item) => phases.get(item.id) === "current") ?? data.entries[0])}>Kostenart ergänzen</button></> : null}</span></p> : null}
    </CollapsibleSection>

    <div className="fin-pair">
    <CollapsibleSection id="fin-alloc" title="Kostenstellen-Aufteilung" tone="department" icon={tileIcon("pie")}
      description={splitBasis}
      summary={data.allocations.length ? `${data.allocations.length} Kostenstellen` : primaryCenter ? `${primaryCenter.code} · ${primaryCenter.name} · 100 %` : "Keine Kostenstelle"}
      actions={editable && !splitting ? <button type="button" className="btn" onClick={() => {
        setSplitting(true);
        if (data.allocations.length === 0) {
          // Erste Aufteilung: mit der Kostenstelle aus der Organisationszuordnung beginnen, dann weitere ergänzen.
          setAllocations(primaryCenter
            ? [{ cost_center_id: primaryCenter.cost_center_id, share_percent: "100", recharge_mode: "" }, { cost_center_id: "", share_percent: "", recharge_mode: "" }]
            : [{ cost_center_id: "", share_percent: "100", recharge_mode: "" }]);
        }
      }}><Icon name={data.allocations.length ? "pen" : "split"} />{data.allocations.length ? "Aufteilung ändern" : "Aufteilen"}</button> : undefined}>
      {splitRows.length ? <div className="fin-split">
        <div className="fin-bar100" aria-hidden="true">
          {splitRows.map((row, index) => <span key={row.id} className={`fin-segment fin-segment--${index % 4}`} style={{ width: `${row.share}%` }} title={`${row.code} · ${row.name}`}>{row.share.toLocaleString("de-DE")} %</span>)}
        </div>
        <table className="rg-table fin-split-table" aria-label="Kostenstellen-Aufteilung">
          <thead><tr><th scope="col">Kostenstelle</th><th scope="col" className="num">Anteil</th><th scope="col" className="num">Betrag / Jahr {nbWord}</th></tr></thead>
          <tbody>{splitRows.map((row, index) => <tr key={row.id}>
            <th scope="row"><span className="fin-split-name"><span className={`fin-swatch fin-swatch--${index % 4}`} aria-hidden="true" />{row.code} · {row.name}{row.primary ? " (Hauptkostenstelle)" : ""}</span></th>
            <td className="num">{row.share.toLocaleString("de-DE")} %</td>
            <td className="num">{splitAmounts[index] != null ? euro(splitAmounts[index]!, "EUR") : "–"}</td>
          </tr>)}</tbody>
          <tfoot><tr><th scope="row">Summe</th><td className="num">{splitShare.toLocaleString("de-DE")} %</td><td className="num">{splitAmount != null ? euro(splitAmount, "EUR") : "–"}</td></tr></tfoot>
        </table>
        {data.allocations.length === 0 ? <p className="fin-foot"><span>Hauptkostenstelle aus der Organisationszuordnung.</span><Link scroll={false} className="fin-k" href={contractHref(contractId, { tab: "register", section: "ownership" })}><Icon name="link" />In der Organisationszuordnung ändern</Link></p> : null}
      </div> : <p className="cw-muted">Noch keine Kostenstelle festgelegt. <Link scroll={false} className="rg-link" href={contractHref(contractId, { tab: "register", section: "ownership" })}>In der Organisationszuordnung festlegen</Link>{editable ? " oder hier aufteilen." : "."}</p>}
      {editable && splitting ? <form className="rg-transition fin-form" aria-label="Kostenstellen aufteilen" onSubmit={(event) => { event.preventDefault(); void run(() => setCostAllocations(orgSlug, contractId, allocations.filter((item) => item.cost_center_id).map((item) => ({ ...item, recharge_mode: item.recharge_mode || null }))), "Aufteilung gespeichert.").then((ok) => { if (ok) setSplitting(false); }); }}>
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
          {allocations.length > 0 ? <span className={Math.abs(allocationSum - 100) < 0.001 ? "cw-muted" : "rg-error"}>Summe {allocationSum.toLocaleString("de-DE")} %</span> : null}
          <button type="button" className="btn" onClick={() => setAllocations((rows) => [...rows, { cost_center_id: "", share_percent: "", recharge_mode: "" }])}>Kostenstelle hinzufügen</button>
          <button type="button" className="btn" onClick={() => { setSplitting(false); apply(data); }}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={busy || (allocations.length > 0 && Math.abs(allocationSum - 100) >= 0.001)}>Aufteilung speichern</button>
        </div>
      </form> : null}
    </CollapsibleSection>

    <CollapsibleSection id="fin-basis" title="Berechnungsgrundlage" tone="accent" icon={tileIcon("doc")}
      description={!hasEntries && basisRows ? "Laut Dokument (KI), noch nicht gepflegt." : undefined}
      summary={[...(basisRows ?? []).map(([, value]) => value), `Preisanpassung: ${paText}`].join(" · ")}>
      <dl className="fin-basis">
        {(basisRows ?? []).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
        {paRow}
      </dl>
      {basisRows ? <Link scroll={false} className="rg-link fin-basis-link" href={contractHref(contractId, { tab: "documents" })}><Icon name="doc" />Dokumentdetails ansehen<Icon name="arrow" /></Link> : null}
    </CollapsibleSection>
    </div>

    <p className="fin-legend">
      <span>Kennfarben:</span>
      <Chip kind="cost" icon="euro" small>Laufende Kosten</Chip>
      <Chip kind="dept" icon="pie" small>Kostenstelle</Chip>
      <AiReviewContext.Provider value={null}><AiOrigin state="confirmed" />
      <AiOrigin state="unreviewed" /></AiReviewContext.Provider>
      <span className="fin-legend-gap">Zahlung:</span>
      <Signal tone="neutral" size="sm" icon={signalIcon("minus")}>Keine Zahlung</Signal>
      <Signal tone="warning" size="sm" icon={signalIcon("pay")}>Nicht erfasst</Signal>
      <Signal tone="info" size="sm" icon={signalIcon("cal")}>Fällig</Signal>
    </p>
  </div>;
}
