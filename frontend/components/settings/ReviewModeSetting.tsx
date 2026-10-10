"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { useToast } from "@/components/ui/Toast";
import { getReviewSettings, updateReviewSettings, type ReviewMode, type ReviewSettingsDto } from "@/lib/domain-api/reviewSettings";

// Prüfmodus der Organisation (WP3): kritische Angaben prüft immer ein Mensch.
export default function ReviewModeSetting() {
  const { organizationSlug } = useAuth();
  const toast = useToast();
  const [settings, setSettings] = useState<ReviewSettingsDto | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!organizationSlug) return;
    getReviewSettings(organizationSlug)
      .then((data) => { setSettings(data); setFailed(false); })
      .catch(() => { setSettings(null); setFailed(true); });
  }, [organizationSlug]);

  useEffect(load, [load]);

  async function change(mode: ReviewMode) {
    if (!organizationSlug || !settings || mode === settings.review_mode) return;
    setBusy(true);
    try {
      setSettings(await updateReviewSettings(organizationSlug, mode));
      toast("Prüfmodus gespeichert.", "success");
    } catch (error) {
      toast(error instanceof Error && error.message ? error.message : "Prüfmodus konnte nicht gespeichert werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  if (failed) {
    return <InlineAlert tone="warning" action={<Button size="sm" onClick={load}>Erneut laden</Button>}>Der Prüfmodus konnte nicht geladen werden.</InlineAlert>;
  }
  if (!settings) return <p role="status">Prüfmodus wird geladen…</p>;

  return <fieldset className="review-mode" disabled={busy || !settings.can_edit}>
    <legend>Prüfung der KI-Angaben</legend>
    {settings.options.map((option) => <label key={option.value} className="rg-check">
      <input type="radio" name="review-mode" value={option.value} checked={settings.review_mode === option.value} onChange={() => void change(option.value)} />
      {option.label}
    </label>)}
    <p className="field-hint">Kritische Angaben (z. B. Vertragspartner, Laufzeit, Kündigungsfrist) prüft immer ein Mensch. Automatisch übernommen werden nur nicht-kritische Angaben mit eindeutigem Quellbeleg; sie bleiben als „Automatisch übernommen“ gekennzeichnet und können jederzeit korrigiert werden.</p>
    {!settings.can_edit ? <p className="field-hint">Nur Administratoren können den Prüfmodus ändern.</p> : null}
  </fieldset>;
}
