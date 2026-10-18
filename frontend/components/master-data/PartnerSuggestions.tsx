"use client";

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  applyPartnerSuggestion,
  dismissPartnerSuggestion,
  getPartnerSuggestions,
  type PartnerSuggestion,
} from "@/lib/domain-api/catalogs";

const SPARK = <svg className="ps-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M12 8l2 4-2 4-2-4z" /></svg>;

function message(error: unknown, fallback: string) {
  return error instanceof ApiError && error.message ? error.message : fallback;
}

/**
 * „Für den Vertragspartner gefunden“: Angaben, die eine Vertragsanalyse belegt gefunden hat und die in die
 * Stammdaten des Partners gehören (E-Mail, Telefon, Anschrift). Nichts wird automatisch geschrieben:
 * „Beim Partner übernehmen“ oder „Ignorieren“ (derselbe Wert kommt dann nicht wieder).
 * Auf der Vertragsseite (`contractId`) aus diesem Vertrag, in den Stammdaten aus allen Verträgen des Partners.
 */
export default function PartnerSuggestions({ orgSlug, partnerId, partnerName, contractId, variant = "contract", onApplied }: {
  orgSlug: string;
  partnerId: string;
  partnerName?: string | null;
  contractId?: string;
  variant?: "contract" | "drawer";
  /** Nach einer Übernahme (z. B. Formular im Stammdaten-Fenster neu laden). */
  onApplied?: () => void;
}) {
  const toast = useToast();
  const [items, setItems] = useState<PartnerSuggestion[] | null>(null);
  const [canApply, setCanApply] = useState(false);
  const [name, setName] = useState<string | null>(partnerName ?? null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getPartnerSuggestions(orgSlug, partnerId, contractId)
      .then((result) => { setItems(result.items); setCanApply(result.can_apply); setName((current) => current ?? result.partner.short_name); })
      .catch(() => setItems([]));
  }, [contractId, orgSlug, partnerId]);
  useEffect(load, [load]);

  if (!items || items.length === 0) return null;

  async function act(item: PartnerSuggestion | null, work: () => Promise<unknown>, done: string) {
    setBusy(item ? `${item.field}:${item.value}` : "all");
    setError(null);
    try {
      await work();
      toast(done, "success");
      load();
      if (onApplied) onApplied();
    } catch (err) {
      setError(message(err, "Die Stammdaten konnten nicht geändert werden."));
    } finally {
      setBusy(null);
    }
  }

  const fresh = items.filter((item) => item.kind === "new");
  const applyAll = () => act(null, async () => {
    for (const item of fresh) await applyPartnerSuggestion(orgSlug, partnerId, item);
  }, `${fresh.length} Angaben beim Vertragspartner ergänzt.`);

  const list = <ul className="ps-list">
    {items.map((item) => {
      const key = `${item.field}:${item.value}`;
      return <li key={key} className="ps-item">
        <span className="ps-what">
          <Signal tone={item.kind === "new" ? "ai" : "warning"} size="sm">{item.kind === "new" ? "Neu" : "Abweichend"}</Signal>
          <strong>{item.label}</strong>
          <span className="ps-value">{item.value}</span>
          {item.current ? <span className="ps-current">bisher: {item.current}</span> : null}
        </span>
        <span className="ps-source" title={item.quote ? `„${item.quote}“` : undefined}>
          {variant === "drawer" && item.register_number ? `Vertrag ${item.register_number}` : "Aus dem Vertrag"}
          {item.page != null ? ` · S. ${item.page}` : ""}
          {item.sources > 1 ? ` · in ${item.sources} Verträgen` : ""}
        </span>
        {canApply ? <span className="ps-actions">
          <Button size="sm" onClick={() => act(item, () => applyPartnerSuggestion(orgSlug, partnerId, item), `${item.label} beim Vertragspartner ${item.kind === "new" ? "ergänzt" : "geändert"}.`)} loading={busy === key} disabled={busy !== null}>
            {item.kind === "new" ? "Beim Partner ergänzen" : "Beim Partner ersetzen"}
          </Button>
          <Button size="sm" className="btn-ghost" onClick={() => act(item, () => dismissPartnerSuggestion(orgSlug, partnerId, item), "Vorschlag ignoriert.")} disabled={busy !== null}>Ignorieren</Button>
        </span> : null}
      </li>;
    })}
  </ul>;

  if (variant === "drawer") {
    return <section className="ps ps--drawer" aria-labelledby={`ps-${partnerId}-heading`}>
      <h3 id={`ps-${partnerId}-heading`} className="ps-title">{SPARK}Aus Verträgen gefunden</h3>
      <p className="ps-intro">Diese Angaben stehen in Verträgen dieses Partners. Nichts wird automatisch übernommen.</p>
      {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
      {list}
      {canApply && fresh.length > 1 ? <div><Button size="sm" onClick={applyAll} disabled={busy !== null}>Alle neuen ergänzen ({fresh.length})</Button></div> : null}
    </section>;
  }

  return <section className="cw-section ps" aria-labelledby="ps-contract-heading">
    <div className="cw-section-head"><div>
      <h2 id="ps-contract-heading">Für den Vertragspartner gefunden</h2>
      <p>{`Die KI hat in diesem Vertrag Angaben zu „${name ?? "dem Vertragspartner"}“ gefunden, die in den Stammdaten fehlen oder abweichen. Nichts wird automatisch übernommen.`}</p>
    </div></div>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {list}
    {canApply && fresh.length > 1 ? <div><Button size="sm" onClick={applyAll} disabled={busy !== null}>Alle neuen ergänzen ({fresh.length})</Button></div>
      : !canApply ? <p className="cw-muted">Vertragspartner pflegen dürfen Administration und Vertragsmanagement.</p> : null}
  </section>;
}
