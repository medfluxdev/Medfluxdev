import { redirect } from "next/navigation";

// Die klassische Vertragsliste ist im Vertragsregister aufgegangen (UX-Plan U4).
export default function ContractsRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = typeof searchParams.q === "string" ? searchParams.q.trim() : "";
  redirect(q ? `/register?q=${encodeURIComponent(q)}` : "/register");
}
