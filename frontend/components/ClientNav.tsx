"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import AppSidebar from "@/components/shell/AppSidebar";
import AppTopbar from "@/components/shell/AppTopbar";
import CommandPalette from "@/components/shell/CommandPalette";
import ShortcutHelp from "@/components/shell/ShortcutHelp";
import { usePreferences } from "@/components/shell/preferences";
import { useShortcuts } from "@/components/shell/useShortcuts";
import FloatingAssistant from "@/components/assistant/FloatingAssistant";

// Anwendungsrahmen: Seitenleiste, Kopfzeile, Befehlspalette, Tastenkuerzel (UX-Plan U3).
export default function ClientNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { account, organizationSlug, loading } = useAuth();
  const [prefs, updatePrefs] = usePreferences();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const openHelp = useCallback(() => setHelpOpen(true), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  useShortcuts(openPalette, openHelp);

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
    <div className={`shell${prefs.sidebarCollapsed ? " shell--collapsed" : ""}`}>
      <AppSidebar
        collapsed={prefs.sidebarCollapsed}
        mobileOpen={mobileOpen}
        onToggleCollapsed={() => updatePrefs({ sidebarCollapsed: !prefs.sidebarCollapsed })}
        onCloseMobile={closeMobile}
      />
      <div className="shell-main">
        <AppTopbar onOpenMenu={() => setMobileOpen(true)} onOpenPalette={openPalette} />
        <main className="main shell-content" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onShowShortcuts={openHelp} />
      <ShortcutHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
      {organizationSlug && <FloatingAssistant key={`${account.id}:${organizationSlug}`} />}
    </div>
  );
}
