"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import CatalogManager from "@/components/catalogs/CatalogManager";

export default function CatalogSettingsPage() {
  const { role, organizationSlug, account } = useAuth();

  if (role !== "admin" && !account?.is_developer) {
    return <div className="page"><p>Dieser Bereich ist nur für Administratoren verfügbar.</p></div>;
  }
  if (!organizationSlug) {
    return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  }

  return <div className="page org-settings-page">
    <div className="org-settings-head">
      <div>
        <span>Administration</span>
        <h1>Kataloge & Nummernkreis</h1>
        <p>Vertragstypen, Kategorien, Auswahllisten und die Vergabe der Vertragsnummern pflegen.</p>
      </div>
      <Link href="/settings">Zurück zu Einstellungen</Link>
    </div>
    <CatalogManager organizationSlug={organizationSlug} />
  </div>;
}
