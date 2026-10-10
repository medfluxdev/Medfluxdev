import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Die klassische Vertragsliste ist in der Vertragsliste (Register) aufgegangen.
export default function ContractsRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/register", searchParams));
}
