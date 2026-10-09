"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import NumberRangeSettings from "@/components/settings/NumberRangeSettings";
import PageHeader from "@/components/ui/PageHeader";

export default function NumberRangePage() {
  const { role, organizationSlug, account } = useAuth();
  if (role !== "admin" && !account?.is_developer) {
    return <div className="page"><PageHeader title="Nummernkreis" /><p>Dieser Bereich ist nur für Administratoren verfügbar.</p></div>;
  }
  return <div className="page">
    <PageHeader
      title="Nummernkreis"
      description="Wie neue Verträge ihre Vertragsnummer erhalten."
      actions={<Link className="btn" href="/stammdaten">Zu den Stammdaten</Link>}
    />
    {organizationSlug ? <NumberRangeSettings organizationSlug={organizationSlug} /> : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </div>;
}
