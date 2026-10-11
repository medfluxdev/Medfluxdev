import { redirect } from "next/navigation";

// Gerätearten werden am Vertrag gepflegt und unter Analysen verglichen (Plan GERAETEARTEN_PLAN_20261011);
// die frühere Geräteliste aus der KI-Analyse hat keinen eigenen Menüpunkt mehr.
export default function Redirect() {
  redirect("/analysen#geraetearten");
}
