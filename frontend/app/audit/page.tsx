"use client";

import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import OrganizationHistory from "@/components/history/OrganizationHistory";

export default function AuditPage() {
  const { organizationSlug, role, account } = useAuth();
  const allowed = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");

  return (
    <div className="page">
      <PageHeader title="Aktivitäten & Protokoll" description="Wer hat wann was geändert – organisationsweit, filterbar nach Benutzer, Bereich, Vertrag und Zeitraum. Technische Rohdaten lassen sich je Eintrag aufklappen." />
      {!allowed ? <p>Das Protokoll ist für Ihre Rolle nicht freigegeben.</p> : !organizationSlug ? <p>Bitte zuerst eine Organisation auswählen.</p> : <OrganizationHistory organizationSlug={organizationSlug} />}
    </div>
  );
}
