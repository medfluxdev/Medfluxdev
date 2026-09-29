"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiPost } from "@/lib/api";

type Reply = { answer: string; contract_id: string | null; evidence: unknown[] };
type Message = { sender: "user" | "assistant"; text: string };

export default function FloatingAssistant() {
  const { organizationSlug, account } = useAuth();
  const pathname = usePathname();
  const match = /^\\/contracts\\/([0-9a-f-]{36})\\/?$/i.exec(pathname);
  const contractId = match?.[1] ?? null;
  const contextKey = [account?.id, organizationSlug, contractId].join(":");
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    setMessages([]);
    setDraft("");
    setError("");
    setBusy(false);
  }, [contextKey]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !organizationSlug || busy) return;
    const current = generation.current;
    setDraft("");
    setError("");
    setBusy(true);
    setMessages(previous => [...previous, { sender: "user", text: message }]);
    try {
      const query = new URLSearchParams({ organization_slug: organizationSlug });
      const result = await apiPost<Reply>(`/api/ai/assistant?${query}`, {
        message,
        contract_id: contractId,
      }, 180000);
      if (current === generation.current) {
        setMessages(previous => [...previous, { sender: "assistant", text: result.answer }]);
      }
    } catch (failure) {
      if (current === generation.current) {
        setError(failure instanceof Error ? failure.message : "Die Anfrage ist fehlgeschlagen.");
      }
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }

  if (!organizationSlug) return null;
  return <aside className="medflux-assistant" aria-label="Lokaler KI-Assistent">
    <button type="button" className="medflux-assistant-toggle" aria-expanded={open}
      aria-controls="medflux-assistant-panel" onClick={() => setOpen(value => !value)}>
      {open ? "Assistent schließen" : "KI-Assistent"}
    </button>
    {open && <section id="medflux-assistant-panel" className="medflux-assistant-panel" aria-label="KI-Chat">
      <header><strong>Lokaler MedFlux-Assistent</strong><small>{contractId ? "Aktueller Vertrag" : "Ohne Vertragskontext"}</small></header>
      <p className="medflux-assistant-notice">Nur Lesezugriff. Vertragsübersichten sind keine geprüften Originalbelege.</p>
      <div className="medflux-assistant-messages" role="log" aria-live="polite">
        {messages.map((item, index) => <p key={index}><strong>{item.sender === "user" ? "Sie" : "Assistent"}:</strong> {item.text}</p>)}
        {busy && <p role="status">Lokales Modell antwortet…</p>}
      </div>
      {error && <p role="alert" className="medflux-assistant-error">{error}</p>}
      <form onSubmit={event => void submit(event)}>
        <label htmlFor="medflux-assistant-input">Ihre Frage</label>
        <textarea id="medflux-assistant-input" value={draft} maxLength={2000} rows={3}
          onChange={event => setDraft(event.target.value)} disabled={busy} />
        <button type="submit" disabled={busy || !draft.trim()}>Frage senden</button>
      </form>
    </section>}
  </aside>;
}
