"use client";

import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import RenewalOverview from "@/components/deadlines/RenewalOverview";

export default function RenewalsPage() {
  const { organizationSlug } = useAuth();
  return (
    <div className="page">
      <PageHeader title="Verlängerungen" description="Kündigungsfristen im Blick: was ansteht, was es kostet und welche Entscheidung erfasst ist." />
      {organizationSlug ? <RenewalOverview organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
    </div>
  );
}
