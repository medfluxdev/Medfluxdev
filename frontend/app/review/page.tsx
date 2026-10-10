import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// „Prüfungen“ ist der Reiter „Zu prüfen“ der Vertragsliste.
export default function ReviewRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/register", searchParams, { ansicht: "review" }));
}
