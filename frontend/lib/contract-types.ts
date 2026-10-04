// TS-Abbild der STEP-13-Vertrags-Portfolio-DTOs (Backend app/contracts/search).
// Nur lesbare Anzeige-Daten; keine rohen OCR-/Vertrags-Körper/Pfade.

export interface SearchFreshness {
  request_as_of_date: string;
  warning_evaluation_as_of_date: string | null;
  data_freshness: "current" | "stale" | "none";
}

export interface ContractFinance {
  currency: string | null;
  amount: string | null;
  unreliable: boolean;
}

export interface ContractWarningSummary {
  warning_type: string | null;
  severity: string | null;
  title_de: string | null;
  target_date: string | null;
}

export interface ContractListItem {
  contract_id: string;
  contract_number: string | null;
  contract_title: string | null;
  supplier: string | null;
  register_number?: string | null;
  business_status?: string | null;
  equipment_summary: string | null;
  status: string | null;
  risk_level: string | null;
  automatic_renewal: boolean | null;
  contract_end_date: string | null;
  latest_cancellation_date: string | null;
  annual_cost: ContractFinance | null;
  primary_warning: ContractWarningSummary | null;
  requires_action: boolean;
  requires_review: boolean;
  is_archived: boolean;
  archived_at: string | null;
}

export interface ContractFacets {
  status_counts: Record<string, number>;
  requires_action: number;
  requires_review: number;
  critical_cancellation: number;
}

export interface ContractListResponse {
  organization_slug: string;
  freshness: SearchFreshness;
  total_count: number;
  page: number;
  page_size: number;
  has_more: boolean;
  facets: ContractFacets;
  items: ContractListItem[];
}

// URL-/Filter-Freiheitsgrad (Client-seitige Anfrageparameter).
export interface ContractsQuery {
  q: string;
  status: string[];
  risk: string[];
  warning_type: string[];
  requires_action: boolean | null;
  requires_review: boolean | null;
  critical_cancellation: boolean | null;
  automatic_renewal: boolean | null;
  archived: boolean | null;
  supplier: string;
  contract_number: string;
  currency: string;
  annual_cost_min: string;
  annual_cost_max: string;
  start_date_from: string;
  start_date_to: string;
  end_date_from: string;
  end_date_to: string;
  cancellation_from: string;
  cancellation_to: string;
  sort: string;
  direction: "asc" | "desc";
  page: number;
  page_size: 25 | 50 | 100;
}
