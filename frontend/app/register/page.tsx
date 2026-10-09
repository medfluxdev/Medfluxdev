"use client";

import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import AddContractMenu from "@/components/register/AddContractMenu";
import RegisterGrid from "@/components/register/RegisterGrid";

export default function RegisterPage() {
  const { organizationSlug } = useAuth();
  return (
    <div className="page">
      <PageHeader
        title="Vertragsliste"
        description="Alle Verträge mit frei wählbaren Spalten, Filtern, Gruppen und gespeicherten Ansichten."
        actions={organizationSlug ? <AddContractMenu /> : undefined}
      />
      {organizationSlug ? <RegisterGrid organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
    </div>
  );
}
