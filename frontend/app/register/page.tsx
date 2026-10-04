"use client";

import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import RegisterGrid from "@/components/register/RegisterGrid";

export default function RegisterPage() {
  const { organizationSlug } = useAuth();
  return (
    <div className="page">
      <PageHeader title="Vertragsregister" description="Alle Verträge mit frei wählbaren Spalten, Filtern, Gruppen und gespeicherten Ansichten." />
      {organizationSlug ? <RegisterGrid organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
    </div>
  );
}
