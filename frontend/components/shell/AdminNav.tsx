"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import { AreaNav, type AreaNavItem } from "./AreaNav";

// Bereichsnavigation „Verwaltung“: alle Verwaltungsseiten an einem Ort.
export default function AdminNav() {
  const { role, account } = useAuth();
  const admin = Boolean(account?.is_developer || role === "admin");
  const only = (allowed: boolean, item: AreaNavItem) => (allowed ? [item] : []);
  return <AreaNav
    label="Verwaltung"
    groups={[
      { items: only(admin, { href: "/admin", label: "Übersicht" }) },
      { title: "Benutzer & Rechte", items: [
        ...only(admin, { href: "/settings/users", label: "Benutzer" }),
        { href: "/settings/roles", label: "Rollen & Rechte" },
      ] },
      { title: "Verträge", items: [
        { href: "/stammdaten", label: "Stammdaten" },
        ...only(admin, { href: "/settings/nummernkreis", label: "Nummernkreis" }),
        ...only(admin, { href: "/admin/deletion", label: "Vertragslöschung" }),
      ] },
      { title: "System", items: [
        ...only(admin, { href: "/settings", label: "Einstellungen" }),
        { href: "/sicherheit", label: "Sicherheit & Datenschutz" },
        ...only(Boolean(account?.is_developer), { href: "/developer", label: "Entwicklung" }),
      ] },
    ]}
  />;
}
