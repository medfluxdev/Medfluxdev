import { apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type DeadlineStatus = "open" | "done" | "cancelled";

export interface DeadlineDto {
  id: string;
  contract_id: string;
  contract_label: string | null;
  source: "manual" | "system";
  system_key: string | null;
  kind: string;
  title: string;
  due_date: string;
  remind_on: string;
  days_until_due: number;
  overdue: boolean;
  assignee_account_id: string | null;
  assignee_name: string | null;
  escalation_account_id: string | null;
  escalation_name: string | null;
  todo_text: string | null;
  note: string | null;
  status: DeadlineStatus;
  send_email: boolean;
  send_ics: boolean;
  done_by_name: string | null;
  done_at: string | null;
  basis_unconfirmed: boolean;
  editable_fields: string[];
}

export interface DeadlineValues {
  kind?: string;
  title?: string;
  due_date?: string;
  remind_on?: string;
  assignee_account_id?: string | null;
  escalation_account_id?: string | null;
  todo_text?: string | null;
  note?: string | null;
  send_email?: boolean;
  send_ics?: boolean;
}

export interface InboxNotification {
  id: string;
  kind: "deadline_reminder" | "deadline_overdue" | "deadline_escalation" | "deadline_assigned";
  title: string;
  body: string | null;
  contract_id: string | null;
  deadline_id: string | null;
  on_behalf_of_name: string | null;
  created_at: string | null;
  read_at: string | null;
}

export interface InboxDto {
  unread_count: number;
  notifications: InboxNotification[];
  deadlines: DeadlineDto[];
  representing: { account_id: string; display_name: string }[];
}

export interface NotificationSettingsDto {
  receives_notifications: boolean;
  receives_reminders: boolean;
  default_deputy_account_id: string | null;
  default_deputy_name: string | null;
  current_deputy_name: string | null;
  email: string;
}

export interface DeputyDto {
  id: string;
  account_id: string;
  account_name: string | null;
  deputy_account_id: string;
  deputy_name: string | null;
  valid_from: string;
  valid_to: string;
  is_active: boolean;
  current: boolean;
}

export interface JobRunDto {
  id: string;
  trigger: string;
  host: string | null;
  as_of_date: string;
  status: "running" | "succeeded" | "failed";
  started_at: string | null;
  finished_at: string | null;
  scope: "organization" | "global";
  counts: Record<string, number>;
  error: string | null;
}

export interface JobStatusDto {
  scheduler_enabled: boolean;
  run_hour: number;
  smtp_configured: boolean;
  last_success_at: string | null;
  stale: boolean;
  emails_pending: number;
  emails_failed: number;
  runs: JobRunDto[];
  counts?: Record<string, number>;
}

export const NOTIFICATION_KIND_LABEL: Record<InboxNotification["kind"], string> = {
  deadline_reminder: "Erinnerung",
  deadline_overdue: "Überfällig",
  deadline_escalation: "Eskalation",
  deadline_assigned: "Neu zugewiesen",
};

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function listContractDeadlines(organizationSlug: string, contractId: string) {
  return apiGet<{ items: DeadlineDto[] }>(`/api/contracts/${encodeURIComponent(contractId)}/deadlines?${orgQuery(organizationSlug)}`);
}

export function createContractDeadline(organizationSlug: string, contractId: string, values: DeadlineValues) {
  return apiPost<{ items: DeadlineDto[] }>(`/api/contracts/${encodeURIComponent(contractId)}/deadlines?${orgQuery(organizationSlug)}`, { values });
}

export function updateDeadline(organizationSlug: string, deadlineId: string, values: DeadlineValues) {
  return apiPatch<{ items: DeadlineDto[] }>(`/api/deadlines/${encodeURIComponent(deadlineId)}?${orgQuery(organizationSlug)}`, { values });
}

export function deadlineAction(organizationSlug: string, deadlineId: string, action: "done" | "cancel" | "reopen", note?: string) {
  return apiPost<{ items: DeadlineDto[] }>(`/api/deadlines/${encodeURIComponent(deadlineId)}/${action}?${orgQuery(organizationSlug)}`, { note: note || null });
}

export function listDeadlines(organizationSlug: string, options: { status?: DeadlineStatus | "all"; mine?: boolean; dueBefore?: string } = {}) {
  const params = new URLSearchParams({ organization_slug: organizationSlug, status: options.status ?? "open" });
  if (options.mine) params.set("mine", "true");
  if (options.dueBefore) params.set("due_before", options.dueBefore);
  return apiGet<{ items: DeadlineDto[] }>(`/api/deadlines?${params.toString()}`);
}

export function getInbox(organizationSlug: string) {
  return apiGet<InboxDto>(`/api/inbox?${orgQuery(organizationSlug)}`);
}

export function markNotificationRead(organizationSlug: string, notificationId: string) {
  return apiPost<{ marked: number }>(`/api/inbox/${encodeURIComponent(notificationId)}/read?${orgQuery(organizationSlug)}`, {});
}

export function markAllNotificationsRead(organizationSlug: string) {
  return apiPost<{ marked: number }>(`/api/inbox/read-all?${orgQuery(organizationSlug)}`, {});
}

export function getNotificationSettings(organizationSlug: string) {
  return apiGet<NotificationSettingsDto>(`/api/me/notification-settings?${orgQuery(organizationSlug)}`);
}

export function updateNotificationSettings(organizationSlug: string, values: Partial<Pick<NotificationSettingsDto, "receives_notifications" | "receives_reminders" | "default_deputy_account_id">>) {
  return apiPut<NotificationSettingsDto>(`/api/me/notification-settings?${orgQuery(organizationSlug)}`, { values });
}

export function listDeputies(organizationSlug: string) {
  return apiGet<{ items: DeputyDto[] }>(`/api/deputies?${orgQuery(organizationSlug)}`);
}

export function createDeputy(organizationSlug: string, payload: { account_id?: string; deputy_account_id: string; valid_from: string; valid_to: string }) {
  return apiPost<{ items: DeputyDto[] }>(`/api/deputies?${orgQuery(organizationSlug)}`, payload);
}

export function deactivateDeputy(organizationSlug: string, deputyId: string) {
  return apiPost<{ items: DeputyDto[] }>(`/api/deputies/${encodeURIComponent(deputyId)}/deactivate?${orgQuery(organizationSlug)}`, {});
}

export function getJobStatus(organizationSlug: string) {
  return apiGet<JobStatusDto>(`/api/jobs/daily?${orgQuery(organizationSlug)}`);
}

export function runDailyJob(organizationSlug: string) {
  return apiPost<JobStatusDto>(`/api/jobs/daily/run?${orgQuery(organizationSlug)}`, {}, 120000);
}
