// Typisierte Abbilder der STEP-12-Dashboard-DTOs (backend/app/dashboard/models.py).

export interface MoneyTotal {
  currency: string;
  amount: string;
  contract_count: number;
}

export interface KpiCard {
  label_de: string;
  value: number;
  secondary_de: string | null;
  status_de: string | null;
}

export interface DataFreshness {
  requested_as_of_date: string;
  warning_evaluation_as_of_date: string | null;
  data_freshness: "current" | "stale" | "none";
  last_calculation_at: string | null;
}

export interface DeadlineBucket {
  threshold_days: number | null;
  label_de: string;
  contract_count: number;
  cancellation: number;
  contract_end: number;
}

export interface ActionItem {
  severity: string;
  warning_type: string;
  title_de: string;
  contract_title: string | null;
  supplier: string | null;
  target_date: string | null;
  days_remaining: number | null;
  requires_review: boolean;
  requires_action: boolean;
  annual_cost: MoneyTotal | null;
  cost_unreliable: boolean;
}

export interface DataQualityItem {
  label_de: string;
  count: number;
  severity: string;
}

export interface FinancialSummary {
  annual_recurring: MoneyTotal[];
  total_contract_value: MoneyTotal[];
  contracts_without_reliable_annual_cost: number;
  contracts_without_reliable_total_value: number;
  multi_currency: boolean;
}

export interface DashboardOverview {
  as_of_date: string;
  freshness: DataFreshness;
  kpis: Record<string, KpiCard>;
  deadlines: DeadlineBucket[];
  action_items: ActionItem[];
  total_action_items: number;
  financial: FinancialSummary;
  data_quality: DataQualityItem[];
}
