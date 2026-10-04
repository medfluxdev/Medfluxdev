"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import OrganizationStructureManager from "@/components/settings/OrganizationStructureManager";

export default function OrganizationSettingsPage() {
  const { role, organizationSlug } = useAuth();

  if (role !== "admin") {
    return <div className="page"><p>Dieser Bereich ist nur für Administratoren verfügbar.</p></div>;
  }

  if (!organizationSlug) {
    return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  }

  return <div className="page org-settings-page">
    <div className="org-settings-head">
      <div>
        <span>Administration</span>
        <h1>Organisationsstruktur</h1>
        <p>Krankenhäuser, Abteilungen und Kostenstellen innerhalb dieses Arbeitsbereichs verwalten.</p>
      </div>
      <Link href="/settings">Zurück zu Einstellungen</Link>
    </div>
    <OrganizationStructureManager organizationSlug={organizationSlug} />
  </div>;
}
