import { redirect } from "next/navigation";

// Krankenhaeuser, Abteilungen und Kostenstellen liegen jetzt in den Stammdaten.
export default function OrganizationSettingsRedirect() {
  redirect("/stammdaten/abteilungen?ansicht=struktur");
}
