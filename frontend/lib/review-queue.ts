/** Reihenfolge der Verträge aus „Zu prüfen“ für „Weiter zum nächsten Vertrag“ (sessionStorage, nur Komfort). */
export const REVIEW_QUEUE_KEY = "medflux.reviewQueue";

export function rememberReviewQueue(ids: string[]) {
  try { window.sessionStorage.setItem(REVIEW_QUEUE_KEY, JSON.stringify(ids)); } catch { /* nur Komfort */ }
}

export function readReviewQueue(): string[] {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(REVIEW_QUEUE_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}
