"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

function DocumentIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M13 5h14l9 9v27H13a4 4 0 0 1-4-4V9a4 4 0 0 1 4-4Z" />
      <path d="M27 5v10h9M17 23h12M17 30h12M17 16h4" />
    </svg>
  );
}

function ShieldIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 4.8 2.8 8.2 7 10 4.2-1.8 7-5.2 7-10V6l-7-3Z" /></svg>;
}

function BoltIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m13 2-8 12h6l-1 8 9-13h-6V2Z" /></svg>;
}

function EyeIcon({ hidden }: { hidden: boolean }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.9 4.2A10.8 10.8 0 0 1 12 4c5.2 0 8.6 4.4 9.5 6-.5.9-1.8 2.7-3.9 4.1M6.2 6.2C4.3 7.4 3.1 9.1 2.5 10c.9 1.6 4.3 6 9.5 6 1.1 0 2.2-.2 3.1-.5" /></svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="2.5" /></svg>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { account, refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(params.get("error") === "organization" ? "Ihr Benutzer hat keinen Zugriff auf diesen Arbeitsbereich." : null);

  useEffect(() => {
    if (account) router.replace("/");
  }, [account, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiPost<{ ok: boolean }>("/api/auth/login", { email, password });
      const current = await refresh();
      if (!current) {
        setError("Anmeldung war erfolgreich, die Sitzung konnte aber nicht geladen werden.");
        return;
      }
      router.replace(current.is_developer ? "/developer" : current.memberships.some((item) => item.role === "admin") ? "/admin" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page" id="main-content">
      <div className="auth-login-shell">
        <header className="auth-login-brand">
          <span className="auth-login-logo"><DocumentIcon /></span>
          <h1>Medflux</h1>
          <p>Intelligentes Vertragsmanagement</p>
        </header>

        <section className="auth-card" aria-labelledby="login-title">
          <h2 id="login-title">Willkommen</h2>
          <p className="auth-intro">Melden Sie sich bei Ihrem Medflux-Konto an.</p>
          <form className="auth-form" onSubmit={submit}>
            <label>
              E-Mail
              <input type="email" autoComplete="username" placeholder="E-Mail-Adresse eingeben" value={email} onChange={(event) => setEmail(event.target.value)} required autoFocus />
            </label>
            <label>
              Passwort
              <span className="auth-password-field">
                <input type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="Passwort eingeben" value={password} onChange={(event) => setPassword(event.target.value)} required />
                <button type="button" className="auth-password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Passwort ausblenden" : "Passwort anzeigen"} aria-pressed={showPassword}>
                  <EyeIcon hidden={showPassword} />
                </button>
              </span>
            </label>
            {error ? <p className="auth-error" role="alert">{error}</p> : null}
            <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Anmeldung läuft…" : "Anmelden"}</button>
          </form>
          <div className="auth-benefits" aria-label="Medflux Vorteile">
            <div><ShieldIcon /><span>Sicher</span></div>
            <div><BoltIcon /><span>Schnell</span></div>
            <div><DocumentIcon /><span>Intelligent</span></div>
          </div>
        </section>
      </div>
    </main>
  );
}
