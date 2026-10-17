// Erinnerungen vor Kündigungstermin/Vertragsende: Vorlaufzeiten lesen, anzeigen und speichern
// (erste = längste in Monaten als Feld `reminder_lead_months`, alle übrigen als weitere Erinnerungen).
import type { ContractRegister, ReminderLead, ReminderUnit } from "@/lib/domain-api/register";

const LEAD_UNIT: Record<ReminderUnit, [string, string]> = { days: ["Tag", "Tage"], weeks: ["Woche", "Wochen"], months: ["Monat", "Monate"] };
export const LEAD_MAX: Record<ReminderUnit, number> = { days: 365, weeks: 104, months: 60 };

export function leadText(lead: ReminderLead): string {
  const [singular, plural] = LEAD_UNIT[lead.unit];
  return `${lead.value} ${lead.value === 1 ? singular : plural} vorher`;
}

/** Eigene Erinnerungen: erste (Monate, leer = Standard) und weitere, als eine Liste. */
export function leadsOf(register: ContractRegister): ReminderLead[] {
  const first = register.fields?.reminder_lead_months?.value;
  return [...(first != null && first !== "" ? [{ value: Number(first), unit: "months" as const }] : []), ...(register.reminders?.extra_leads ?? [])];
}

/** Die längste Erinnerung in Monaten wird die erste (eigenes Feld), alle übrigen sind weitere Erinnerungen. */
export function splitLeads(leads: ReminderLead[]): { first: number | null; extra: ReminderLead[] } {
  const months = leads.filter((lead) => lead.unit === "months");
  if (!months.length) return { first: null, extra: leads };
  const longest = months.reduce((best, lead) => (lead.value > best.value ? lead : best));
  const index = leads.indexOf(longest);
  return { first: longest.value, extra: leads.filter((_, position) => position !== index) };
}

export function sameLeads(left: ReminderLead[], right: ReminderLead[]) {
  const key = (leads: ReminderLead[]) => leads.map((lead) => `${lead.value}${lead.unit}`).sort().join(",");
  return key(left) === key(right);
}

/** Anzeige: ohne eigene Erinnerung in Monaten gilt der Standard (Vertragstyp bzw. Organisation) als erste Erinnerung. */
export function reminderChips(leads: ReminderLead[], standard: ReminderLead[]): { label: string; lead: ReminderLead | null }[] {
  const chips = leads.map((lead) => ({ label: leadText(lead), lead }));
  if (leads.some((lead) => lead.unit === "months")) return chips;
  const own = new Set(leads.map((lead) => leadText(lead)));
  return [...standard.filter((lead) => !own.has(leadText(lead))).map((lead) => ({ label: leadText(lead), lead: null })), ...chips];
}

/** Standard-Erinnerungen aus dem Register (Vertragstyp, sonst Organisation). */
export function standardLeads(register: ContractRegister): ReminderLead[] {
  return register.reminders?.default_leads ?? [{ value: register.reminders?.default_lead_months ?? 4, unit: "months" }];
}
