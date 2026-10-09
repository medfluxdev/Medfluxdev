"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import PermissionMatrixView from "@/components/access/PermissionMatrixView";
import PageHeader from "@/components/ui/PageHeader";

export default function RolesPage() {
  const { organizationSlug } = useAuth();

  if (!organizationSlug) {
    return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  }

  return <div className="page">
    <PageHeader title="Rollen & Rechte" description="Welche Rolle was in MedFlux darf. Rollen werden unter „Benutzer“ vergeben." />
    <PermissionMatrixView organizationSlug={organizationSlug} />
  </div>;
}
