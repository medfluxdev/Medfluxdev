import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Die Dokumentverarbeitung ist ein Reiter der Entwicklung.
export default function ProcessingRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/developer", searchParams, { tab: "verarbeitung" }));
}
