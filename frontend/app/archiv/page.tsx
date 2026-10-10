import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Das Archiv ist der Reiter „Archiv“ der Vertragsliste.
export default function ArchiveRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/register", searchParams, { ansicht: "archive" }));
}
