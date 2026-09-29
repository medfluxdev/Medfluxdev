"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { apiPost } from "@/lib/api";

type Evidence = { field_ref: string; document_version_id: string; page: number | null; source_text: string; requires_review: boolean };
type Reply = { answer: string; contract_id: string | null; evidence: Evidence[] };
type Message = { sender: "user" | "assistant"; text: string; evidence?: Evidence[] };

export default function FloatingAssistant() {
  const { organizationSlug, account } = useAuth();
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const contractId = segments.length === 2 && segments[0] === "contracts" &&
    /^[0-9a-f-]{36}$/i.test(segments[1]) ? segments[1] : null;
  const contextKey = [account?.id, organizationSlug, contractId].join(":");
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    generation.current += 1;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setMessages([]);
    setDraft("");
    setError("");
    setBusy(false);
    return () => { activeRequest.current?.abort(); };
  }, [contextKey]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !organizationSlug || busy) return;
    const current = generation.current;
    const controller = new AbortController();
    activeRequest.current = controller;
    setDraft("");
    setError("");
    setBusy(true);
    setMessages(previous => [...previous, { sender: "user", text: message }]);
    try {
      const query = new URLSearchParams({ organization_slug: organizationSlug });
      const result = await apiPost<Reply>(`/api/ai/assistant?${query}`, {
        message,
        contract_id: contractId,
      }, 180000, controller.signal);
      if (current === generation.current) {
        setMessages(previous => [...previous, { sender: "assistant", text: result.answer, evidence: result.evidence }]);
      }
    } catch (failure) {
      if (current === generation.current && !controller.signal.aborted) {
        setError(failure instanceof Error ? failure.message : "Die Anfrage ist fehlgeschlagen.");
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
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
        {messages.map((item, index) => <div key={index} className="medflux-assistant-message"><p><strong>{item.sender === "user" ? "Sie" : "Assistent"}:</strong> {item.text}</p>{item.evidence && item.evidence.length > 0 && <details><summary>Quellenauszüge ({item.evidence.length})</summary>{item.evidence.map((source, i) => <div key={`${source.document_version_id}:${source.field_ref}:${i}`}><strong>{source.field_ref}</strong> · {source.page == null ? "Keine Seitenangabe" : `Seite ${source.page}`} · {source.requires_review ? "Prüfung erforderlich" : "Extraktionsbeleg (nicht unabhängig verifiziert)"}<p>{source.source_text}</p>{contractId && <a href={`/contracts/${encodeURIComponent(contractId)}`}>Vertrag öffnen</a>}</div>)}</details>}</div>)}
        {busy && <p role="status">Lokales Modell antwortet… <button type="button" onClick={() => { generation.current += 1; activeRequest.current?.abort(); activeRequest.current = null; setBusy(false); }}>Abbrechen</button></p>}
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
