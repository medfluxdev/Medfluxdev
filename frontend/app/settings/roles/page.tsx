"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import PermissionMatrixView from "@/components/access/PermissionMatrixView";

export default function RolesPage() {
  const { organizationSlug } = useAuth();

  if (!organizationSlug) {
    return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  }

  return <div className="page org-settings-page">
    <div className="org-settings-head">
      <div>
        <span>Administration</span>
        <h1>Rollen & Rechte</h1>
        <p>Welche Rolle was in MedFlux darf. Rollen werden unter „Benutzer“ vergeben.</p>
      </div>
      <Link href="/settings">Zurück zu Einstellungen</Link>
    </div>
    <PermissionMatrixView organizationSlug={organizationSlug} />
  </div>;
}
