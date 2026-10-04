"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import OrganizationScopePicker from "@/components/OrganizationScopePicker";
import { useAuth } from "@/components/auth/AuthProvider";
import NotificationCenter from "@/components/shell/NotificationCenter";
import Breadcrumbs, { type Crumb } from "@/components/ui/Breadcrumbs";
import { ROLE_LABELS } from "@/lib/auth-types";
import { Icon, pageFor } from "./navigation";
import { usePreferences, type Density, type TextSize, type ThemePreference } from "./preferences";

interface Props {
  onOpenMenu: () => void;
  onOpenPalette: () => void;
}

export default function AppTopbar({ onOpenMenu, onOpenPalette }: Props) {
  const pathname = usePathname();
  const { account, membership, role, logout } = useAuth();
  const [prefs, updatePrefs] = usePreferences();
  const menuRef = useRef<HTMLDetailsElement>(null);
  const page = pageFor(pathname);

  useEffect(() => {
    const menu = menuRef.current;
    if (!menu) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !menu.open) return;
      menu.open = false;
      menu.querySelector<HTMLElement>("summary")?.focus();
    };
    menu.addEventListener("keydown", onKey);
    return () => menu.removeEventListener("keydown", onKey);
  }, [account?.id]);

  useEffect(() => { if (menuRef.current) menuRef.current.open = false; }, [pathname]);

  const crumbs: Crumb[] = [];
  if (page.group && page.item && page.item.href !== "/") crumbs.push({ label: page.group.label });
  if (page.item && page.title !== page.item.label) crumbs.push({ label: page.item.label, href: page.item.href });
  crumbs.push({ label: page.title });

  return (
    <header className="shell-topbar">
      <button type="button" className="btn btn-ghost btn-icon shell-menu-button" onClick={onOpenMenu} aria-label="Navigation öffnen">
        <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
      </button>
      <div className="shell-topbar-title">{pathname === "/" ? null : <Breadcrumbs items={crumbs} />}</div>

      <button type="button" className="shell-search" onClick={onOpenPalette} aria-label="Suchen und Befehle (Strg+K)">
        <Icon name="search" />
        <span>Suchen…</span>
        <kbd>Strg K</kbd>
      </button>

      <div className="shell-topbar-actions">
        {membership ? <OrganizationScopePicker /> : null}
        {membership ? (
          <button type="button" className="btn btn-ghost shell-assistant-button" onClick={() => window.dispatchEvent(new Event("medflux:assistant-toggle"))}>
            <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" /></svg>
            <span>KI-Assistent</span>
          </button>
        ) : null}
        {account && membership ? <NotificationCenter /> : null}
        {account && role ? (
          <details ref={menuRef} className="shell-menu">
            <summary className="shell-user" aria-label="Kontomenü öffnen">
              <span className="shell-avatar">
                {account.profile_photo_data_url ? <Image src={account.profile_photo_data_url} alt="" width={32} height={32} unoptimized /> : account.display_name.slice(0, 1).toUpperCase()}
              </span>
              <span className="shell-user-text"><strong>{account.display_name}</strong><small>{account.is_developer ? "Entwicklung" : ROLE_LABELS[role]}</small></span>
            </summary>
            <div className="shell-menu-panel">
              <div className="shell-menu-head"><strong>{account.display_name}</strong><small>{account.email}</small></div>
              <Link href="/profile">Mein Profil</Link>
              {role === "admin" || account.is_developer ? <Link href="/admin">Verwaltung</Link> : null}
              <fieldset className="shell-prefs">
                <legend>Darstellung</legend>
                <label>Design
                  <select value={prefs.theme} onChange={(event) => updatePrefs({ theme: event.target.value as ThemePreference })}>
                    <option value="system">Wie System</option>
                    <option value="light">Hell</option>
                    <option value="dark">Dunkel</option>
                  </select>
                </label>
                <label>Textgröße
                  <select value={prefs.textSize} onChange={(event) => updatePrefs({ textSize: event.target.value as TextSize })}>
                    <option value="normal">Normal (100 %)</option>
                    <option value="large">Groß (112,5 %)</option>
                    <option value="xlarge">Sehr groß (125 %)</option>
                  </select>
                </label>
                <label>Dichte
                  <select value={prefs.density} onChange={(event) => updatePrefs({ density: event.target.value as Density })}>
                    <option value="comfortable">Komfortabel</option>
                    <option value="compact">Kompakt</option>
                  </select>
                </label>
              </fieldset>
              <button type="button" className="btn" onClick={() => void logout()}>Abmelden</button>
            </div>
          </details>
        ) : null}
      </div>
    </header>
  );
}
