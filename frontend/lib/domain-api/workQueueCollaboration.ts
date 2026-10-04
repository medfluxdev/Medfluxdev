import { apiGet, apiPost, apiPut } from "@/lib/api";

export interface WorkItemComment {
  id: string;
  account_id?: string | null;
  display_name: string;
  body: string;
  created_at: string | null;
}

export interface WorkItemCollaboration {
  assignee_account_id: string | null;
  assignee_display_name?: string | null;
  owner_note: string | null;
  remind_at: string | null;
  escalation_level: number;
  comments?: WorkItemComment[];
}

export interface WorkItemCollaborationUpdate {
  assignee_account_id: string | null;
  owner_note: string | null;
  remind_at: string | null;
  escalation_level: number;
}

function path(organizationSlug: string, workItemId: string, suffix: string) {
  const params = new URLSearchParams({ organization_slug: organizationSlug });
  return `/api/work-queue/${encodeURIComponent(workItemId)}${suffix}?${params.toString()}`;
}

export function getWorkItemCollaboration(organizationSlug: string, workItemId: string) {
  return apiGet<WorkItemCollaboration>(path(organizationSlug, workItemId, "/collaboration"));
}

export function updateWorkItemCollaboration(organizationSlug: string, workItemId: string, update: WorkItemCollaborationUpdate) {
  return apiPut<WorkItemCollaboration>(path(organizationSlug, workItemId, "/collaboration"), update);
}

export function addWorkItemComment(organizationSlug: string, workItemId: string, body: string) {
  return apiPost<WorkItemComment>(path(organizationSlug, workItemId, "/comments"), { body });
}
