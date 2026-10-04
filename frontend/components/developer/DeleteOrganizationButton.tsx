"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Props = {
  organizationId: string;
  organizationName: string;
  onDeleted: () => void | Promise<void>;
  onMessage: (message: { error: boolean; text: string }) => void;
};

export default function DeleteOrganizationButton({ organizationId, organizationName, onDeleted, onMessage }: Props) {
  const [busy, setBusy] = useState(false);

  async function handleDelete() {
    if (!window.confirm(`Organisation „${organizationName}“ wirklich löschen?`)) return;
    setBusy(true);
    onMessage({ error: false, text: "" });
    try {
      const response = await fetch(`${API_BASE}/api/system/organizations/${encodeURIComponent(organizationId)}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(body?.detail || `Löschen fehlgeschlagen (${response.status}).`);
      }
      onMessage({ error: false, text: `Organisation „${organizationName}“ wurde gelöscht.` });
      await onDeleted();
    } catch (error) {
      onMessage({ error: true, text: error instanceof Error ? error.message : "Organisation konnte nicht gelöscht werden." });
    } finally {
      setBusy(false);
    }
  }

  return <button type="button" disabled={busy} onClick={() => void handleDelete()}>{busy ? "Wird gelöscht…" : "Löschen"}</button>;
}
