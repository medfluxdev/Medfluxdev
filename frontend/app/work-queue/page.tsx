import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Teil von „Fristen & Aufgaben“ (Reiter Aufgaben).
export default function Redirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/fristen", searchParams, { ansicht: "aufgaben" }));
}
