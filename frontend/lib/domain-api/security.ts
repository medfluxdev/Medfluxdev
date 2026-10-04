import { apiPost } from "@/lib/api";

export interface LogoutAllResponse {
  ok: boolean;
  revoked_sessions: number;
}

export function logoutAllSessions() {
  return apiPost<LogoutAllResponse>("/api/auth/logout-all", {});
}
