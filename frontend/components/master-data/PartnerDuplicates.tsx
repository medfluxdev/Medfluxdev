"use client";

import { useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import { useToast } from "@/components/ui/Toast";
import { listPartnerDuplicates, type PartnerDto } from "@/lib/domain-api/catalogs";
import { mergePartners } from "@/lib/domain-api/masterData";
import type { ManagerApi } from "./types";

function count(value: number | undefined) {
  const n = value ?? 0;
  return `${n} ${n === 1 ? "Vertrag" : "Verträge"}`;
}

function DuplicateGroup({ group, organizationSlug, api }: { group: PartnerDto[]; organizationSlug: string; api: ManagerApi<PartnerDto> }) {
  const toast = useToast();
  const [keep, setKeep] = useState(() => [...group].sort((a, b) => (b.contract_count ?? 0) - (a.contract_count ?? 0))[0].id);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const target = group.find((item) => item.id === keep) ?? group[0];
  const sources = group.filter((item) => item.id !== target.id);
  const moved = sources.reduce((sum, item) => sum + (item.contract_count ?? 0), 0);

  async function merge() {
    setBusy(true);
    setError(null);
    try {
      await mergePartners(organizationSlug, target.id, sources.map((item) => item.id));
      toast(`Zusammengeführt in „${target.short_name}“.`, "success");
      await api.reload();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Zusammenführen fehlgeschlagen.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return <li className="md-duplicate">
    <fieldset disabled={!api.canEdit || busy}>
      <legend>{group.map((item) => item.short_name).join(" · ")}</legend>
      {group.map((item) => <label key={item.id} className="md-check">
        {api.canEdit ? <input type="radio" name={`keep-${group[0].id}`} checked={item.id === keep} onChange={() => { setKeep(item.id); setConfirming(false); }} /> : null}
        <span><strong>{item.short_name}</strong> – {item.display_name}{item.city ? `, ${item.city}` : ""} · {count(item.contract_count)}</span>
      </label>)}
    </fieldset>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {api.canEdit ? confirming ? <InlineAlert
      tone="warning"
      role="alert"
      action={<span className="btn-group">
        <Button size="sm" variant="primary" loading={busy} onClick={() => void merge()}>Zusammenführen</Button>
        <Button size="sm" onClick={() => setConfirming(false)}>Abbrechen</Button>
      </span>}
    >
      {moved > 0 ? `${count(moved)} werden „${target.short_name}“ zugeordnet. ` : ""}
      {sources.map((item) => `„${item.short_name}“`).join(", ")} {sources.length === 1 ? "wird" : "werden"} deaktiviert. Die Änderung steht in der Historie der Verträge.
    </InlineAlert> : <Button size="sm" onClick={() => setConfirming(true)}>„{target.short_name}“ behalten und zusammenführen</Button> : null}
  </li>;
}

// Moegliche Dubletten (sehr aehnliche Namen) mit Zusammenfuehren.
export default function PartnerDuplicates({ organizationSlug, api, rows }: { organizationSlug: string; api: ManagerApi<PartnerDto>; rows: PartnerDto[] }) {
  const [groups, setGroups] = useState<PartnerDto[][]>([]);

  useEffect(() => {
    let active = true;
    listPartnerDuplicates(organizationSlug)
      .then((data) => {
        if (!active) return;
        // Vertragsanzahl aus der aktuellen Liste uebernehmen (die Dublettenliste liefert sie nicht).
        const byId = new Map(rows.map((row) => [row.id, row]));
        setGroups(data.groups.map((group) => group.map((item) => ({ ...item, contract_count: byId.get(item.id)?.contract_count ?? item.contract_count }))));
      })
      .catch(() => { if (active) setGroups([]); });
    return () => { active = false; };
  }, [organizationSlug, rows]);

  if (groups.length === 0) return null;
  return <details className="md-duplicates" open>
    <summary>{groups.length === 1 ? "1 mögliche Dublette" : `${groups.length} mögliche Dubletten`} – sehr ähnliche Namen prüfen</summary>
    <p className="field-hint">Wählen Sie den Eintrag, der bleiben soll. Verträge der anderen werden ihm zugeordnet, die anderen deaktiviert (nicht gelöscht).</p>
    <ul>{groups.map((group) => <DuplicateGroup key={group.map((item) => item.id).join("-")} group={group} organizationSlug={organizationSlug} api={api} />)}</ul>
  </details>;
}
