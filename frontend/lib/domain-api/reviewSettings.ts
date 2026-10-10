import { apiGet, apiPut } from "@/lib/api";

export type ReviewMode = "manual" | "auto_noncritical";

export interface ReviewSettingsDto {
  review_mode: ReviewMode;
  review_mode_label: string;
  options: { value: ReviewMode; label: string }[];
  can_edit: boolean;
}

function orgQuery(organizationSlug: string) {
  return `organization_slug=${encodeURIComponent(organizationSlug)}`;
}

export function getReviewSettings(organizationSlug: string) {
  return apiGet<ReviewSettingsDto>(`/api/review-settings?${orgQuery(organizationSlug)}`);
}

export function updateReviewSettings(organizationSlug: string, reviewMode: ReviewMode) {
  return apiPut<ReviewSettingsDto>(`/api/review-settings?${orgQuery(organizationSlug)}`, { review_mode: reviewMode });
}
