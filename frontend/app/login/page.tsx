"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { account, refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("error") === "organization"
      ? "Ihr Benutzer hat keinen Zugriff auf diesen Arbeitsbereich."
      : null
  );

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
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand">
          <span className="auth-brand-mark" aria-hidden="true" />
          <span>
            <strong>Medflux</strong>
            <small>Intelligentes Vertragsmanagement</small>
          </span>
        </div>
        <h1 id="login-title">Anmelden</h1>
        <p className="auth-intro">
          Melden Sie sich mit Ihrem Medflux-Benutzerkonto an.
        </p>
        <form className="auth-form" onSubmit={submit}>
          <label>
            E-Mail
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus
            />
          </label>
          <label>
            Passwort
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? <p className="auth-error" role="alert">{error}</p> : null}
          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Anmeldung läuft…" : "Anmelden"}
          </button>
        </form>
      </section>
    </main>
  );
}
