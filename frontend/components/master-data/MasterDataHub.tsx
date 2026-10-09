"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import KpiTile from "@/components/ui/KpiTile";
import Skeleton from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { formatDate } from "@/lib/format";
import {
  listContractTypes,
  listLookups,
  listPartners,
  loadDefaultCatalogs,
  type ContractCategoryDto,
  type ContractTypeDto,
  type LookupDto,
} from "@/lib/domain-api/catalogs";
import { getMasterDataSummary, type MasterDataSummary } from "@/lib/domain-api/masterData";
import { searchOrganizationStructure } from "@/lib/domain-api/organizations";
import {
  MASTER_DATA_GROUPS,
  MASTER_DATA_SECTIONS,
  masterDataSection,
  masterDataSectionForLookup,
} from "@/lib/master-data";
import { usePermissions } from "@/lib/use-permissions";

interface Hit {
  key: string;
  section: string;
  href: string;
  title: string;
  detail: string;
  inactive: boolean;
}

interface CatalogCache {
  types: ContractTypeDto[];
  categories: ContractCategoryDto[];
  lookups: LookupDto[];
}

function entryHref(slug: string, id: string) {
  const section = masterDataSection(slug);
  return `${section?.href ?? "/stammdaten"}?id=${encodeURIComponent(id)}`;
}

async function searchAll(organizationSlug: string, needle: string, catalogs: CatalogCache, signal: AbortSignal): Promise<Hit[]> {
  const lower = needle.toLocaleLowerCase("de");
  const [partners, structure] = await Promise.all([
    listPartners(organizationSlug, { q: needle, includeInactive: true, limit: 8 }).catch(() => ({ items: [], total: 0 })),
    searchOrganizationStructure(organizationSlug, needle, signal).catch(() => ({ items: [], query: needle })),
  ]);
  const hits: Hit[] = [];
  for (const item of partners.items) {
    hits.push({ key: `p-${item.id}`, section: "Vertragspartner", href: entryHref("vertragspartner", item.id), title: item.short_name, detail: [item.display_name, item.city].filter(Boolean).join(", "), inactive: !item.is_active });
  }
  for (const item of structure.items) {
    const slug = item.kind === "cost_center" ? "kostenstellen" : "abteilungen";
    hits.push({ key: `s-${item.id}`, section: item.kind === "cost_center" ? "Kostenstellen" : "Abteilungen", href: entryHref(slug, item.id), title: `${item.code} – ${item.name}`, detail: [item.path_label, item.hospital_name].filter(Boolean).join(" · "), inactive: !item.is_active });
  }
  for (const item of catalogs.types.filter((row) => row.label.toLocaleLowerCase("de").includes(lower))) {
    hits.push({ key: `t-${item.id}`, section: "Vertragstypen", href: entryHref("vertragstypen", item.id), title: item.label, detail: item.description ?? "", inactive: !item.is_active });
  }
  for (const item of catalogs.categories.filter((row) => row.label.toLocaleLowerCase("de").includes(lower))) {
    hits.push({ key: `c-${item.id}`, section: "Kategorien", href: entryHref("kategorien", item.id), title: item.label, detail: item.description ?? "", inactive: !item.is_active });
  }
  for (const item of catalogs.lookups.filter((row) => row.label.toLocaleLowerCase("de").includes(lower)).slice(0, 10)) {
    const section = masterDataSectionForLookup(item.field_key);
    if (!section) continue;
    hits.push({ key: `l-${item.id}`, section: section.label, href: `${section.href}?id=${encodeURIComponent(item.id)}`, title: item.label, detail: "Auswahlliste", inactive: !item.is_active });
  }
  return hits;
}

function SearchAll({ organizationSlug }: { organizationSlug: string }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const catalogs = useRef<Promise<CatalogCache> | null>(null);

  useEffect(() => {
    const needle = query.trim();
    if (needle.length < 2) { setHits(null); setState("idle"); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setState("loading");
      try {
        catalogs.current ??= Promise.all([listContractTypes(organizationSlug), listLookups(organizationSlug, undefined, true)])
          .then(([types, lookups]) => ({ types: types.contract_types, categories: types.contract_categories, lookups: lookups.items }));
        const result = await searchAll(organizationSlug, needle, await catalogs.current, controller.signal);
        if (!controller.signal.aborted) { setHits(result); setState("idle"); }
      } catch {
        catalogs.current = null;
        if (!controller.signal.aborted) setState("error");
      }
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [organizationSlug, query]);

  return <section className="md-search-all" aria-labelledby="md-search-heading">
    <h2 id="md-search-heading">In allen Stammdaten suchen</h2>
    <label className="md-search">
      <span className="visually-hidden">Suchbegriff</span>
      <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="z. B. Siemens, 471120, Kardiologie, Lagerort" />
    </label>
    {state === "loading" ? <p className="state-loading" role="status">Suche läuft…</p> : null}
    {state === "error" ? <InlineAlert tone="critical" role="alert">Die Suche ist fehlgeschlagen. Bitte erneut versuchen.</InlineAlert> : null}
    {hits && state === "idle" ? hits.length === 0
      ? <p role="status" className="field-hint">Keine Treffer für „{query.trim()}“.</p>
      : <ul className="md-hits" aria-label="Suchergebnisse">
        {hits.map((hit) => <li key={hit.key}>
          <Link href={hit.href}><strong>{hit.title}</strong></Link>
          <span>{hit.section}{hit.detail ? ` · ${hit.detail}` : ""}{hit.inactive ? " · deaktiviert" : ""}</span>
        </li>)}
      </ul> : null}
  </section>;
}

// Einstieg: alle Datenarten mit Bestand, letzter Aenderung und offenen Hinweisen.
export default function MasterDataHub({ organizationSlug }: { organizationSlug: string }) {
  const toast = useToast();
  const { can } = usePermissions();
  const [summary, setSummary] = useState<MasterDataSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSummary(await getMasterDataSummary(organizationSlug));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Die Übersicht konnte nicht geladen werden.");
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  async function addDefaults() {
    setBusy(true);
    try {
      const result = await loadDefaultCatalogs(organizationSlug);
      const created = Object.values(result.created).reduce((sum, value) => sum + value, 0);
      toast(created ? `${created} Standardeinträge ergänzt.` : "Alle Standardeinträge sind bereits vorhanden.", "success");
      await load();
    } catch (err) {
      toast(err instanceof Error && err.message ? err.message : "Standardeinträge konnten nicht ergänzt werden.", "error");
    } finally {
      setBusy(false);
    }
  }

  const lookupSections = MASTER_DATA_SECTIONS.filter((section) => section.fieldKey);
  return <div className="md-hub">
    <SearchAll organizationSlug={organizationSlug} />

    {error ? <InlineAlert tone="critical" role="alert" action={<Button size="sm" onClick={() => void load()}>Erneut laden</Button>}>{error}</InlineAlert> : null}
    {!summary && !error ? <Skeleton lines={6} label="Übersicht wird geladen…" /> : null}

    {summary ? <>
      {summary.hints.partner_duplicate_groups > 0 ? <InlineAlert
        tone="warning"
        role="status"
        action={<Link className="btn btn-sm" href="/stammdaten/vertragspartner">Prüfen</Link>}
      >
        {summary.hints.partner_duplicate_groups === 1 ? "1 mögliche Dublette" : `${summary.hints.partner_duplicate_groups} mögliche Dubletten`} bei den Vertragspartnern.
      </InlineAlert> : null}

      {MASTER_DATA_GROUPS.map((group) => <section key={group} className="md-hub-group" aria-labelledby={`md-group-${group}`}>
        <h2 id={`md-group-${group}`}>{group}</h2>
        <div className="md-tiles">
          {MASTER_DATA_SECTIONS.filter((section) => section.group === group && !section.fieldKey).map((section) => {
            const count = summary.kinds[section.kind] ?? { total: 0, active: 0, inactive: 0, last_change: null };
            const hints = [
              count.inactive ? `${count.inactive} deaktiviert` : null,
              count.last_change ? `geändert ${formatDate(count.last_change)}` : null,
              section.kind === "partner" && summary.hints.partners_without_contracts ? `${summary.hints.partners_without_contracts} ohne Vertrag` : null,
            ].filter(Boolean).join(" · ");
            return <KpiTile key={section.slug} label={section.label} value={count.active} hint={hints || section.description} href={section.href} linkLabel={`${section.label} öffnen`} />;
          })}
        </div>
        {group === "Vertragsdaten" ? <div className="md-lookups">
          <h3>Auswahllisten</h3>
          <ul>
            {lookupSections.map((section) => {
              const list = summary.lookup_lists.find((item) => item.field_key === section.fieldKey);
              return <li key={section.slug}>
                <Link href={section.href}>{section.label}</Link>
                <span>{list ? `${list.active} Einträge${list.inactive ? `, ${list.inactive} deaktiviert` : ""}` : "keine Einträge"}</span>
              </li>;
            })}
          </ul>
        </div> : null}
      </section>)}

      {can("catalog.admin") ? <section className="md-hub-admin" aria-labelledby="md-admin-heading">
        <h2 id="md-admin-heading">Für Administratoren</h2>
        <div className="btn-group">
          <Button onClick={() => void addDefaults()} loading={busy} loadingLabel="Wird ergänzt…">Fehlende Standardeinträge ergänzen</Button>
          <Link className="btn" href="/settings/nummernkreis">Nummernkreis der Vertragsnummern</Link>
        </div>
        <p className="field-hint">Ergänzt nur fehlende Vertragstypen, Kategorien und Auswahlwerte; Bestehendes bleibt unverändert.</p>
      </section> : null}
    </> : null}
  </div>;
}
