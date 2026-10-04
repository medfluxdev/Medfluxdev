"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import PartnerManager from "@/components/catalogs/PartnerManager";
import PageHeader from "@/components/ui/PageHeader";

export default function PartnersPage() {
  const { organizationSlug } = useAuth();
  if (!organizationSlug) {
    return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  }
  return <div className="page">
    <PageHeader title="Vertragspartner" description="Lieferanten, Dienstleister und Kooperationspartner als gemeinsame Stammdaten." />
    <PartnerManager organizationSlug={organizationSlug} />
  </div>;
}
