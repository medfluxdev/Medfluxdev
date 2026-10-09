"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import MasterDataHub from "@/components/master-data/MasterDataHub";
import PageHeader from "@/components/ui/PageHeader";

export default function MasterDataPage() {
  const { organizationSlug } = useAuth();
  return <>
    <PageHeader
      title="Stammdaten"
      description="Vertragspartner, Organisation und Auswahllisten an einem Ort – gleiche Bedienung für alle Datenarten."
    />
    {organizationSlug ? <MasterDataHub organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </>;
}
