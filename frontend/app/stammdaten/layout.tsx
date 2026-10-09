import type { ReactNode } from "react";
import MasterDataNav from "@/components/master-data/MasterDataNav";
import { AreaLayout } from "@/components/shell/AreaNav";

export default function MasterDataLayout({ children }: { children: ReactNode }) {
  return <AreaLayout nav={<MasterDataNav />}>{children}</AreaLayout>;
}
