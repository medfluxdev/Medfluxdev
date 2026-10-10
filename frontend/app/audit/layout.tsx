import type { ReactNode } from "react";
import AdminNav from "@/components/shell/AdminNav";
import { AreaLayout } from "@/components/shell/AreaNav";

// Aktivitäten & Protokoll gehört zur Verwaltung (gleiche Bereichsnavigation).
export default function AuditAreaLayout({ children }: { children: ReactNode }) {
  return <AreaLayout nav={<AdminNav />}>{children}</AreaLayout>;
}
