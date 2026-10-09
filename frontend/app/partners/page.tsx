import { redirect } from "next/navigation";

// Frueherer Ort der Vertragspartner; Suchbegriff wird mitgenommen.
export default function PartnersRedirect({ searchParams }: { searchParams: { q?: string } }) {
  redirect(searchParams.q ? `/stammdaten/vertragspartner?q=${encodeURIComponent(searchParams.q)}` : "/stammdaten/vertragspartner");
}
