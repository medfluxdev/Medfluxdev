"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import InboxView from "@/components/deadlines/InboxView";
import PageHeader from "@/components/ui/PageHeader";

// Früher „Postfach“: jetzt das vollständige Benachrichtigungsprotokoll (Glocke → „Alle Benachrichtigungen“).
// Alte Links auf die Wiedervorlage führen zu den eigenen offenen Terminen.
export default function InboxPage() {
  const { organizationSlug } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (window.location.hash === "#wiedervorlage" || new URLSearchParams(window.location.search).get("bereich") === "wiedervorlage") {
      router.replace("/fristen?ansicht=termine&nur=meine");
    }
  }, [router]);

  if (!organizationSlug) return <div className="page"><p>Bitte zuerst eine Organisation auswählen.</p></div>;
  return <div className="page">
    <PageHeader title="Benachrichtigungen" description="Erinnerungen und Eskalationen zu Ihren Terminen – vollständiges Protokoll." />
    <InboxView organizationSlug={organizationSlug} />
  </div>;
}
