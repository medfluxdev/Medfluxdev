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

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { account, refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
      router.replace("/");
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
              <input type="password" autoComplete="current-password" placeholder="Passwort eingeben" value={password} onChange={(event) => setPassword(event.target.value)} required />
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
