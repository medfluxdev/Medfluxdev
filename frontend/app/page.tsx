"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import MyDay from "@/components/dashboard/MyDay";
import PageHeader from "@/components/ui/PageHeader";

export default function StartPage() {
  const { organizationSlug } = useAuth();
  if (!organizationSlug) {
    return <div className="page"><PageHeader title="Mein Tag" description="Bitte zuerst eine Organisation auswählen." /></div>;
  }
  return <MyDay organizationSlug={organizationSlug} />;
}
