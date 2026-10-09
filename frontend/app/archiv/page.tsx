"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import RegisterGrid from "@/components/register/RegisterGrid";
import PageHeader from "@/components/ui/PageHeader";

// Archiv: dieselbe Vertragsliste mit der Ansicht „Archiv“ und „Wiederherstellen“ je Zeile.
export default function ArchivePage() {
  const { organizationSlug } = useAuth();
  return <div className="page">
    <PageHeader title="Archiv" description="Abgelegte Verträge. Archivieren ist umkehrbar – es wird nichts gelöscht." />
    {organizationSlug ? <RegisterGrid organizationSlug={organizationSlug} initialViewKey="archive" /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </div>;
}
