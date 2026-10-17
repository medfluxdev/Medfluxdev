// Reiter „Leistungen & SLA“: wann er erscheint und was die Kachel in der Übersicht zeigt.

export interface ServiceFacts {
  scope_text: string | null;
  availability_percent: string | null;
  penalty_terms: string | null;
}

/**
 * Sichtbar bei Vertragstypen mit Leistungsumfang/SLA (Wartung, Service, Dienstleistung …) oder sobald Angaben
 * vorliegen (gepflegt oder aus dem Dokument); sonst nur auf Wunsch („Leistungen & SLA hinzufügen“).
 */
export function servicesVisible({ sections, service, scopeHasData, slaHasData, revealed }: {
  sections: { scope: boolean; sla: boolean } | null | undefined;
  service: ServiceFacts | null | undefined;
  scopeHasData: boolean;
  slaHasData: boolean;
  revealed: boolean;
}): boolean {
  const byType = Boolean(sections && (sections.scope || sections.sla));
  const maintained = Boolean(service?.scope_text || service?.availability_percent || service?.penalty_terms);
  return byType || maintained || scopeHasData || slaHasData || revealed;
}
