"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import AppSidebar from "@/components/shell/AppSidebar";
import AppTopbar from "@/components/shell/AppTopbar";
import FloatingAssistant from "@/components/assistant/FloatingAssistant";

export default function ClientNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { account, loading } = useAuth();

  if (pathname === "/login" || pathname === "/select-organization") {
    return <>{children}</>;
  }

  if (loading) {
    return <div className="auth-loading" role="status">MedFlux wird geladen…</div>;
  }

  if (!account) {
    return (
      <div className="auth-login-required">
        <p>Sie sind nicht angemeldet.</p>
        <Link href="/login">Anmelden</Link>
      </div>
    );
  }

  return (
    <div className="app">
      <AppSidebar />
      <main className="main" id="main-content">
        <AppTopbar />
        {children}
      </main>
    </div>
  );
}
