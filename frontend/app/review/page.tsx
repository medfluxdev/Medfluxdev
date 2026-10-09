"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import RegisterGrid from "@/components/register/RegisterGrid";
import PageHeader from "@/components/ui/PageHeader";

// Zu prüfende Verträge: dieselbe Vertragsliste mit der Ansicht „Zu prüfen“ und „Prüfen“ je Zeile.
export default function ReviewPage() {
  const { organizationSlug } = useAuth();
  return <div className="page">
    <PageHeader title="Prüfungen" description="Verträge, deren KI-Analyse noch nicht geprüft ist. „Prüfen“ öffnet die Prüfung mit Belegen." />
    {organizationSlug ? <RegisterGrid organizationSlug={organizationSlug} initialViewKey="review" /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </div>;
}
