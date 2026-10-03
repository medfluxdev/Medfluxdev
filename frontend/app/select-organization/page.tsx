"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROLE_LABELS } from "@/lib/auth-types";
import MedFluxLogo from "@/components/brand/MedFluxLogo";

export default function SelectOrganizationPage() {
  const router = useRouter();
  const { account, memberships, membership, loading, selectOrganization, logout } = useAuth();

  useEffect(() => {
    if (!loading && account && memberships.length === 1 && membership) router.replace("/");
  }, [account, loading, membership, memberships.length, router]);

  if (loading) return <div className="auth-loading">Arbeitsbereiche werden geladen…</div>;
  if (!account) return null;

  return (
    <main className="workspace-select-page" id="main-content">
      <section className="workspace-select-card" aria-labelledby="workspace-title">
        <div className="workspace-select-brand"><MedFluxLogo priority /></div>
        <p className="workspace-select-kicker">Arbeitsbereich</p>
        <h1 id="workspace-title">Organisation auswählen</h1>
        <p className="workspace-select-intro">Wählen Sie die Organisation, in der Sie jetzt arbeiten möchten.</p>
        <div className="workspace-select-list">
          {memberships.map((item) => (
            <button key={item.organization_id} type="button" className="workspace-option" onClick={() => { selectOrganization(item.organization_slug); router.replace("/"); }}>
              <span className="workspace-option-avatar">{item.organization_name.slice(0, 1).toUpperCase()}</span>
              <span className="workspace-option-copy"><strong>{item.organization_name}</strong><small>{ROLE_LABELS[item.role]} · {item.organization_slug}</small></span>
              <span className="workspace-option-arrow" aria-hidden="true">→</span>
            </button>
          ))}
        </div>
        {memberships.length === 0 ? <p className="auth-error">Für dieses Konto ist keine Organisation freigeschaltet.</p> : null}
        <div className="workspace-select-footer"><span>{account.display_name}</span><button type="button" onClick={() => void logout()}>Abmelden</button></div>
      </section>
    </main>
  );
}
