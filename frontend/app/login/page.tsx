"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import InlineAlert from "@/components/ui/InlineAlert";
import { apiPost } from "@/lib/api";

const DEFAULT_ORG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

type Identity = {
  user_id: string;
  organization_id: string;
  organization_slug: string;
  username: string;
  display_name: string;
  role: string;
};

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiPost<Identity>("/api/auth/login", {
        organization_slug: DEFAULT_ORG,
        username,
        password,
      });
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 560, margin: "80px auto" }}>
      <section className="panel" aria-labelledby="login-heading">
        <div className="panel-head">
          <div>
            <div className="section-caption">Lokale Anmeldung</div>
            <h2 id="login-heading">Medflux öffnen</h2>
            <p>Die Anmeldung wird ausschließlich auf diesem Medflux-System geprüft.</p>
          </div>
        </div>

        {error && <InlineAlert tone="critical" role="alert">{error}</InlineAlert>}

        <form onSubmit={submit} style={{ display: "grid", gap: 16, marginTop: 18 }}>
          <label className="field">
            <span>Benutzername</span>
            <input
              autoComplete="username"
              required
              maxLength={120}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Passwort</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              maxLength={512}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="btn" type="submit" disabled={pending}>
            {pending ? "Anmeldung wird geprüft…" : "Anmelden"}
          </button>
        </form>
      </section>
    </div>
  );
}
