import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Die UI-Bausteine sind ein Reiter der Entwicklung.
export default function ComponentReferenceRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/developer", searchParams, { tab: "bausteine" }));
}
