import type { ReactNode } from "react";
import AdminNav from "@/components/shell/AdminNav";
import { AreaLayout } from "@/components/shell/AreaNav";

export default function AdminAreaLayout({ children }: { children: ReactNode }) {
  return <AreaLayout nav={<AdminNav />}>{children}</AreaLayout>;
}
