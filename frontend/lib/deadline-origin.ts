import { contractHref, type FixTarget } from "@/lib/fix-targets";
import type { DeadlineDto } from "@/lib/domain-api/deadlines";

/** Wo ein Termin herkommt: berechnete Termine führen zur Angabe in den Vertragsdaten, aus der sie entstehen. */
const SYSTEM_ORIGIN: Record<string, { target: FixTarget; label: string }> = {
  cancel_by: { target: { tab: "register", field: "notice_period" }, label: "Kündigungsfrist in den Vertragsdaten" },
  contract_end: { target: { tab: "register", field: "term_fixed_end_date" }, label: "Vertragsende in den Vertragsdaten" },
  price_adjustment: { target: { tab: "register", field: "price_adjustment_next_date" }, label: "Preisanpassung in den Vertragsdaten" },
  maintenance_due: { target: { tab: "register", field: "maintenance_next_date" }, label: "Wartung in den Vertragsdaten" },
  payment_due: { target: { tab: "finance" }, label: "Zahlung in den Finanzen" },
  retention_review: { target: { tab: "register", section: "retention" }, label: "Aufbewahrung & Löschung" },
  set_ended: { target: { tab: "overview", section: "status" }, label: "Vertragsstatus" },
};

export interface DeadlineOrigin { href: string; label: string }

export function deadlineOrigin(item: Pick<DeadlineDto, "contract_id" | "source" | "system_key">): DeadlineOrigin {
  const known = item.source === "system" && item.system_key ? SYSTEM_ORIGIN[item.system_key] : undefined;
  if (known) return { href: contractHref(item.contract_id, known.target), label: known.label };
  // Manuelle Termine (und unbekannte Schlüssel): Fristen & Aufgaben des Vertrags.
  return { href: contractHref(item.contract_id, { tab: "deadlines" }), label: "Fristen & Aufgaben des Vertrags" };
}
