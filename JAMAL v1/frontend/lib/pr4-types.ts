// TS-Abbild der PR-4-DTOs (Backend app/equipment + app/work_queue).
// Read-Only-Anzeige; alle Bewertungen (Identität, Beziehung, Review) und
// Arbeitspunkt-Ableitungen kommen autoritativ vom Backend – das Frontend
// rechnet nichts neu und erfindet keine Kennungen.

export interface EquipmentSummary {
  id: string;
  device_name: string | null;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  inventory_number: string | null;
  equipment_type: string | null;
  equipment_category: string | null;
  location: string | null;
  department: string | null;
  identification_quality: string;
  contract_count: number;
}

export interface EquipmentContractLink {
  contract_id: string;
  supplier: string | null;
  contract_number: string | null;
  relationship_quality: string | null;
  requires_review: boolean;
  service_scope: string | null;
}

export interface EquipmentDetail extends EquipmentSummary {
  contracts: EquipmentContractLink[];
}

export interface WorkItemSummary {
  id: string;
  contract_id: string;
  contract_number: string | null;
  supplier: string | null;
  equipment_id: string | null;
  contract_equipment_id: string | null;
  source_warning_id: string | null;
  item_type: string;
  severity: string;
  status: string;
  title_de: string;
  why_de: string | null;
  action_hint_de: string | null;
  target_date: string | null;
  days_remaining: number | null;
  requires_review: boolean;
  active: boolean;
  references: Record<string, unknown> | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  equipment_device_name: string | null;
  equipment_manufacturer: string | null;
  equipment_model: string | null;
  equipment_serial_number: string | null;
}

export interface WorkItemList {
  items: WorkItemSummary[];
  total: number;
}

// Deutsche Beschriftungen (reine Anzeige).
export const IDENTIFICATION_QUALITY_LABEL: Record<string, string> = {
  exact: "Eindeutig (Seriennr./Inventarnr.)",
  partial: "Teilweise (Name/Modell/Hersteller)",
  generic: "Generisch (Kategorie)",
  unknown: "Unbekannt",
};

export const RELATIONSHIP_QUALITY_LABEL: Record<string, string> = {
  exact: "Belegt exakt",
  partial: "Teilweise belegt",
  generic: "Generisch",
  ambiguous: "Mehrdeutig",
};

export const WORK_ITEM_STATUS_LABEL: Record<string, string> = {
  open: "Offen",
  acknowledged: "In Bearbeitung",
  resolved: "Erledigt",
};

export const SEVERITY_LABEL_PR4: Record<string, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
};

export const WORK_ITEM_TYPE_LABEL: Record<string, string> = {
  cancellation_deadline: "Kündigungsfrist",
  contract_expiry: "Vertragsende",
  automatic_renewal: "Automatische Verlängerung",
  contract_expired: "Vertrag ausgelaufen",
  manual_review: "Manuelle Prüfung",
  missing_cost: "Fehlende Kosten",
  equipment_coverage_review: "Geräte-/Leistungsabdeckung prüfen",
  equipment_relationship_ambiguous: "Geräte-Zuordnung mehrdeutig",
  sla_issue: "Service-Level-Konflikt",
};

export function identificationQualityLabel(q: string | null): string {
  return (q && IDENTIFICATION_QUALITY_LABEL[q]) || "Unbekannt";
}

export function relationshipQualityLabel(q: string | null): string {
  return (q && RELATIONSHIP_QUALITY_LABEL[q]) || "Unbekannt";
}

export function workItemStatusLabel(s: string | null): string {
  return (s && WORK_ITEM_STATUS_LABEL[s]) || "Unbekannt";
}

export function severityLabel(s: string | null): string {
  return (s && SEVERITY_LABEL_PR4[s]) || "Unbekannt";
}

export function workItemTypeLabel(t: string | null): string {
  return (t && WORK_ITEM_TYPE_LABEL[t]) || "Arbeitselement";
}
