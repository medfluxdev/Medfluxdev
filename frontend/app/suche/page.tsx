"use client";

import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/components/auth/AuthProvider";
import ContentSearch from "@/components/search/ContentSearch";

export default function ContentSearchPage() {
  const { organizationSlug } = useAuth();
  return (
    <div className="page">
      <PageHeader title="Inhaltssuche" description="Welche Verträge enthalten eine bestimmte Regelung? Jeder Treffer mit Dokument und Seite." />
      {organizationSlug ? <ContentSearch organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
    </div>
  );
}
