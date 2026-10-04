"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import InboxView from "@/components/deadlines/InboxView";
import PageHeader from "@/components/ui/PageHeader";

export default function InboxPage() {
  const { organizationSlug } = useAuth();
  if (!organizationSlug) return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  return <div className="page">
    <PageHeader title="Postfach" description="Erinnerungen, Eskalationen und Ihre offenen Termine." />
    <InboxView organizationSlug={organizationSlug} />
  </div>;
}
