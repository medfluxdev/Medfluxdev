import { redirect } from "next/navigation";
import { withParams } from "@/lib/redirect-params";

// Organisationsstruktur wird in den Stammdaten gepflegt.
export default function Redirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  redirect(withParams("/stammdaten/abteilungen", searchParams, { ansicht: "struktur" }));
}
