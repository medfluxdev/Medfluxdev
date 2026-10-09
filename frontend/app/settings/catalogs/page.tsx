import { redirect } from "next/navigation";

// Kataloge liegen jetzt in den Stammdaten; der Nummernkreis unter /settings/nummernkreis.
export default function CatalogSettingsRedirect() {
  redirect("/stammdaten/vertragstypen");
}
