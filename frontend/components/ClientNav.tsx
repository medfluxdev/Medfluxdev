"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { watchBoxes } from "@/lib/box-collapse";
import { useAuth } from "@/components/auth/AuthProvider";
import AppSidebar from "@/components/shell/AppSidebar";
import AppTopbar from "@/components/shell/AppTopbar";
import CommandPalette from "@/components/shell/CommandPalette";
import ShortcutHelp from "@/components/shell/ShortcutHelp";
import DeveloperPanel from "@/components/shell/DeveloperPanel";
import { usePreferences, useServerPreferenceSync } from "@/components/shell/preferences";
import { useShortcuts } from "@/components/shell/useShortcuts";
import FloatingAssistant from "@/components/assistant/FloatingAssistant";
import { ROLE_LABELS } from "@/lib/auth-types";

// Anwendungsrahmen: Seitenleiste, Kopfzeile, Befehlspalette, Tastenkuerzel (UX-Plan U3).
export default function ClientNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Jeder Kasten im Inhaltsbereich lässt sich einklappen (lib/box-collapse.ts).
  const stopBoxes = useRef<(() => void) | null>(null);
  const mainRef = useCallback((node: HTMLElement | null) => {
    stopBoxes.current?.();
    stopBoxes.current = node ? watchBoxes(node) : null;
  }, []);
  const { account, organizationSlug, loading, role, previewOf, setPreviewRole } = useAuth();
  const [prefs, updatePrefs] = usePreferences();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [developerOpen, setDeveloperOpen] = useState(false);
  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const openHelp = useCallback(() => setHelpOpen(true), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  useShortcuts(openPalette, openHelp);
  useServerPreferenceSync(account?.id ?? null);

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
        <AppTopbar onOpenMenu={() => setMobileOpen(true)} onOpenPalette={openPalette} onOpenDeveloper={() => setDeveloperOpen(true)} />
        {previewOf && role ? (
          <div className="shell-preview-banner" role="status">
            <span>Vorschau: Sie sehen MedFlux wie die Rolle <strong>{ROLE_LABELS[role]}</strong>. Nur die Darstellung ändert sich – Ihre Rechte bleiben unverändert.</span>
            <button type="button" className="btn btn-sm" onClick={() => setPreviewRole(null)}>Vorschau beenden</button>
          </div>
        ) : null}
        <main ref={mainRef} className="main shell-content" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onShowShortcuts={openHelp} />
      <ShortcutHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
      {account.is_developer && prefs.developerMode ? <DeveloperPanel open={developerOpen} onClose={() => setDeveloperOpen(false)} /> : null}
      {organizationSlug && <FloatingAssistant key={`${account.id}:${organizationSlug}`} />}
    </div>
  );
}
