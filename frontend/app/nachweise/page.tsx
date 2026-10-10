import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Nachweise gehören zum Vertrag (Dokumente → Nachweise, mit PDF daneben). Ohne Vertrag führt der Weg
// zu den Verträgen mit offener Prüfung, deren Belege dort geprüft werden.
export default function EvidenceRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const contract = typeof searchParams.contract === "string" ? searchParams.contract : null;
  if (contract && /^[0-9a-f-]{36}$/i.test(contract)) {
    const rest = Object.fromEntries(Object.entries(searchParams).filter(([key]) => key !== "contract"));
    redirect(withParams(`/contracts/${contract}`, rest, { tab: "documents", subtab: "evidence" }));
  }
  redirect("/register?ansicht=review");
}
