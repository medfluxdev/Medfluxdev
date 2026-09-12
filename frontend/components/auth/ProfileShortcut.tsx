"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

export default function ProfileShortcut() {
  const pathname = usePathname();
  const { account, loading } = useAuth();
  if (loading || !account || pathname === "/login" || pathname === "/profile") return null;
  return (
    <Link href="/profile" className="profile-shortcut" aria-label="Mein Profil öffnen">
      <span>{account.display_name.slice(0, 1).toUpperCase()}</span>
      <strong>Mein Profil</strong>
    </Link>
  );
}
