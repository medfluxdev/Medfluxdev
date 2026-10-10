import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Organisationen werden in der Entwicklung (Übersicht) verwaltet.
export default function SystemOrganizationsRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/developer", searchParams));
}
