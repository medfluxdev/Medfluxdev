"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import MedFluxLogo from "@/components/brand/MedFluxLogo";
import type { AIStatus } from "@/lib/ai-types";
import { Icon, isActive, visibleGroups } from "./navigation";

const STATUS_REFRESH_MS = 60_000;

interface Props {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
}

// Hauptnavigation: sechs Bereiche, als Icon-Leiste einklappbar, auf dem
// Telefon als ueberlagernde Leiste (UX-Plan U3).
export default function AppSidebar({ collapsed, mobileOpen, onToggleCollapsed, onCloseMobile }: Props) {
  const pathname = usePathname();
  const { account, membership, role } = useAuth();
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    let mounted = true;
    async function refresh() {
      const [api, ai] = await Promise.allSettled([apiGet<{ status: string }>("/health"), apiGet<AIStatus>("/api/ai/status")]);
      if (!mounted) return;
      setApiHealthy(api.status === "fulfilled" ? api.value.status === "ok" : false);
      setAiStatus(ai.status === "fulfilled" ? ai.value : null);
    }
    void refresh();
    const timer = window.setInterval(refresh, STATUS_REFRESH_MS);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => { onCloseMobile(); }, [pathname, onCloseMobile]);

  const groups = useMemo(() => visibleGroups(role, Boolean(account?.is_developer)), [account?.is_developer, role]);
  const aiReady = Boolean(aiStatus?.available && aiStatus?.model_available);
  const statusText = apiHealthy === false ? "Server nicht erreichbar" : aiReady ? `Lokale KI bereit (${aiStatus?.model})` : aiStatus ? "Lokale KI nicht bereit" : "Status wird geprüft…";
  const statusTone = apiHealthy === false ? "danger" : aiReady ? "success" : "warning";

  return (
    <>
      {mobileOpen ? <div className="shell-scrim" onClick={onCloseMobile} aria-hidden="true" /> : null}
      <aside className={`shell-sidebar${collapsed ? " is-collapsed" : ""}${mobileOpen ? " is-open" : ""}`} aria-label="Seitenleiste">
        <div className="shell-sidebar-head">
          <Link href="/" className="shell-brand" aria-label="MedFlux – Mein Tag">
            <MedFluxLogo priority />
          </Link>
          <button type="button" className="btn btn-ghost btn-icon btn-sm shell-collapse" onClick={onToggleCollapsed} aria-label={collapsed ? "Seitenleiste ausklappen" : "Seitenleiste einklappen"} aria-expanded={!collapsed}>
            <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d={collapsed ? "m9 6 6 6-6 6" : "m15 6-6 6 6 6"} /></svg>
          </button>
        </div>

        <nav className="shell-nav" aria-label="Hauptnavigation">
          {groups.map((group) => (
            <div key={group.label} className="shell-nav-group">
              <h2 className="shell-nav-label">{group.label}</h2>
              <ul>
                {group.items.map((item) => {
                  const current = isActive(pathname, item.href) || (item.href === "/register" && pathname.startsWith("/contracts/"));
                  return (
                    <li key={item.href}>
                      <Link href={item.href} className={`shell-nav-item${current ? " is-active" : ""}`} aria-current={current ? "page" : undefined} title={collapsed ? item.label : undefined}>
                        <Icon name={item.icon} />
                        <span className="shell-nav-text">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="shell-sidebar-foot">
          <p className={`shell-status shell-status--${statusTone}`} role="status" title={statusText}>
            <span className="shell-status-dot" aria-hidden="true" />
            <span className="shell-nav-text">{statusText}</span>
          </p>
          <p className="shell-org shell-nav-text">{membership?.organization_name ?? (account?.is_developer ? "Systemverwaltung" : "Krankenhaus")}</p>
        </div>
      </aside>
    </>
  );
}
