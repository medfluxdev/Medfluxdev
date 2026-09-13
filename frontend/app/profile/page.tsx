"use client";

import Image from "next/image";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROLE_LABELS, type UserProfileDto } from "@/lib/auth-types";
import { logoutAllSessions } from "@/lib/domain-api/security";

const EMPTY: UserProfileDto = {
  id: "",
  email: "",
  display_name: "",
  phone: null,
  job_title: null,
  department: null,
  bio: null,
  profile_photo_data_url: null,
};

export default function ProfilePage() {
  const { role, refresh, logout } = useAuth();
  const [profile, setProfile] = useState<UserProfileDto>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<UserProfileDto>("/api/profile")
      .then(setProfile)
      .catch((err) => setError(err instanceof Error ? err.message : "Profil konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  function setField<K extends keyof UserProfileDto>(key: K, value: UserProfileDto[K]) {
    setProfile((current) => ({ ...current, [key]: value }));
  }

  function choosePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    if (!file.type.startsWith("image/")) {
      setError("Bitte wählen Sie eine Bilddatei aus.");
      return;
    }
    if (file.size > 600_000) {
      setError("Das Profilbild darf maximal 600 KB groß sein.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") setField("profile_photo_data_url", reader.result);
    };
    reader.readAsDataURL(file);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await apiPatch<UserProfileDto>("/api/profile", {
        display_name: profile.display_name,
        phone: profile.phone ?? "",
        job_title: profile.job_title ?? "",
        department: profile.department ?? "",
        bio: profile.bio ?? "",
        profile_photo_data_url: profile.profile_photo_data_url ?? "",
      });
      setProfile(saved);
      await refresh();
      setMessage("Profil wurde gespeichert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Profil konnte nicht gespeichert werden.");
    } finally {
      setSaving(false);
    }
  }

  async function endAllSessions() {
    setSessionBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await logoutAllSessions();
      setMessage(`${result.revoked_sessions} Sitzung(en) wurden beendet. Sie werden abgemeldet.`);
      await logout();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sitzungen konnten nicht beendet werden.");
    } finally {
      setSessionBusy(false);
    }
  }

  if (loading) return <div className="page profile-page"><p className="cw-muted">Profil wird geladen…</p></div>;

  return (
    <div className="page profile-page">
      <header className="profile-header">
        <div>
          <span className="profile-kicker">Persönlicher Bereich</span>
          <h1>Mein Profil</h1>
          <p>Persönliche Angaben, Profilbild und Kontositzungen verwalten.</p>
        </div>
        <span className="profile-role-badge">{role ? ROLE_LABELS[role] : "Benutzer"}</span>
      </header>

      <form className="profile-layout" onSubmit={save}>
        <aside className="profile-photo-card">
          <div className="profile-photo-wrap">
            {profile.profile_photo_data_url ? (
              <Image src={profile.profile_photo_data_url} alt="Profilbild" width={160} height={160} unoptimized />
            ) : (
              <span>{profile.display_name?.slice(0, 1).toUpperCase() || "M"}</span>
            )}
          </div>
          <label className="profile-photo-button">
            Foto auswählen
            <input type="file" accept="image/*" onChange={choosePhoto} />
          </label>
          {profile.profile_photo_data_url ? (
            <button type="button" className="profile-photo-remove" onClick={() => setField("profile_photo_data_url", null)}>Foto entfernen</button>
          ) : null}
          <small>JPG, PNG oder WebP · max. 600 KB</small>
        </aside>

        <section className="profile-form-card">
          <div className="profile-form-grid">
            <label>Name<input value={profile.display_name} onChange={(e) => setField("display_name", e.target.value)} required /></label>
            <label>E-Mail<input value={profile.email} disabled readOnly /></label>
            <label>Position / Funktion<input value={profile.job_title ?? ""} onChange={(e) => setField("job_title", e.target.value)} placeholder="z. B. Vertragsmanager" /></label>
            <label>Abteilung<input value={profile.department ?? ""} onChange={(e) => setField("department", e.target.value)} placeholder="z. B. Medizintechnik" /></label>
            <label>Telefon<input value={profile.phone ?? ""} onChange={(e) => setField("phone", e.target.value)} placeholder="Telefonnummer" /></label>
            <label className="profile-wide">Über mich<textarea rows={5} value={profile.bio ?? ""} onChange={(e) => setField("bio", e.target.value)} placeholder="Kurze persönliche Beschreibung oder interne Kontaktinformation …" maxLength={2000} /></label>
          </div>

          {error ? <div className="profile-message error" role="alert">{error}</div> : null}
          {message ? <div className="profile-message" role="status">{message}</div> : null}

          <div className="profile-actions">
            <button type="submit" disabled={saving}>{saving ? "Speichern…" : "Änderungen speichern"}</button>
          </div>

          <section className="profile-security" aria-labelledby="profile-security-heading">
            <h2 id="profile-security-heading">Sicherheit</h2>
            <p>Beendet alle widerrufbaren Anmeldesitzungen dieses Kontos auf allen Geräten.</p>
            <button type="button" className="profile-photo-remove" disabled={sessionBusy} onClick={() => void endAllSessions()}>
              {sessionBusy ? "Sitzungen werden beendet…" : "Alle Sitzungen beenden"}
            </button>
          </section>
        </section>
      </form>
    </div>
  );
}
