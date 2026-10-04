"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { listPartners } from "@/lib/domain-api/catalogs";
import { getGrid } from "@/lib/domain-api/registerGrid";
import { useFocusTrap } from "@/components/ui/useFocusTrap";
import { allowed, EXTRA_PAGES, Icon, NAV_GROUPS, type IconName } from "./navigation";
import { usePreferences } from "./preferences";

interface Command {
  id: string;
  section: "Aktionen" | "Seiten" | "Verträge" | "Vertragspartner" | "Inhalte";
  label: string;
  hint?: string;
  icon: IconName;
  run: () => void;
}

function normalize(text: string) {
  return text.toLocaleLowerCase("de-DE").normalize("NFD").replace(/[̀-ͯ]/g, "");
}

// Befehlspalette (Strg+K): Seiten, Aktionen, Vertraege, Partner und Inhaltssuche.
export default function CommandPalette({ open, onClose, onShowShortcuts }: { open: boolean; onClose: () => void; onShowShortcuts: () => void }) {
  const router = useRouter();
  const { role, account, organizationSlug } = useAuth();
  const [, updatePrefs] = usePreferences();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [remote, setRemote] = useState<Command[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  const listId = useId();
  useFocusTrap(ref, open, onClose);

  useEffect(() => { if (open) { setQuery(""); setActive(0); setRemote([]); } }, [open]);

  const go = (href: string) => () => { onClose(); router.push(href); };
  const isDeveloper = Boolean(account?.is_developer);

  const local = useMemo<Command[]>(() => {
    const pages = [...NAV_GROUPS.flatMap((group) => group.items), ...EXTRA_PAGES]
      .filter((item) => allowed(item, role, isDeveloper))
      .map((item) => ({ id: `page:${item.href}`, section: "Seiten" as const, label: item.label, hint: item.keywords, icon: item.icon, run: go(item.href) }));
    const editor = isDeveloper || role === "admin" || role === "contract_manager";
    const actions: Command[] = [
      ...(editor ? [
        { id: "act:new", section: "Aktionen" as const, label: "Vertrag anlegen", icon: "contracts" as const, run: go("/contracts/new") },
        { id: "act:import", section: "Aktionen" as const, label: "Dokumente importieren", icon: "import" as const, run: go("/import") },
      ] : []),
      { id: "act:theme-dark", section: "Aktionen", label: "Dunkles Design einschalten", icon: "settings", run: () => { updatePrefs({ theme: "dark" }); onClose(); } },
      { id: "act:theme-light", section: "Aktionen", label: "Helles Design einschalten", icon: "settings", run: () => { updatePrefs({ theme: "light" }); onClose(); } },
      { id: "act:shortcuts", section: "Aktionen", label: "Tastenkürzel anzeigen", hint: "?", icon: "settings", run: () => { onClose(); onShowShortcuts(); } },
    ];
    return [...actions, ...pages];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, isDeveloper]);

  useEffect(() => {
    const q = query.trim();
    if (!open || !organizationSlug || q.length < 2) { setRemote([]); return; }
    let cancelled = false;
    const handle = window.setTimeout(() => {
      Promise.allSettled([
        getGrid(organizationSlug, { q, columns: ["register_number", "short_description", "partner"] }, { offset: 0, limit: 6 }),
        listPartners(organizationSlug, { q, limit: 4 }),
      ]).then(([contracts, partners]) => {
        if (cancelled) return;
        const found: Command[] = [];
        if (contracts.status === "fulfilled") {
          for (const item of contracts.value.items) {
            found.push({ id: `contract:${item.contract_id}`, section: "Verträge", label: `${item.values.register_number ?? "–"} · ${item.values.short_description ?? ""}`, hint: String(item.values.partner ?? ""), icon: "contracts", run: go(`/contracts/${item.contract_id}?tab=register`) });
          }
        }
        if (partners.status === "fulfilled") {
          for (const item of partners.value.items) {
            found.push({ id: `partner:${item.id}`, section: "Vertragspartner", label: item.short_name, hint: item.name1, icon: "partners", run: go(`/partners?q=${encodeURIComponent(item.short_name)}`) });
          }
        }
        found.push({ id: "content", section: "Inhalte", label: `In allen Vertragsdokumenten suchen: „${q}“`, icon: "search", run: go(`/suche?q=${encodeURIComponent(q)}`) });
        setRemote(found);
      });
    }, 200);
    return () => { cancelled = true; window.clearTimeout(handle); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, organizationSlug, query]);

  const results = useMemo(() => {
    const q = normalize(query.trim());
    const matches = q ? local.filter((command) => normalize(`${command.label} ${command.hint ?? ""}`).includes(q)) : local.filter((command) => command.section === "Aktionen" || command.section === "Seiten").slice(0, 12);
    return [...matches.slice(0, 10), ...remote];
  }, [local, query, remote]);

  useEffect(() => { setActive(0); }, [query]);

  if (!open) return null;

  function onKey(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((index) => Math.min(index + 1, results.length - 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setActive((index) => Math.max(index - 1, 0)); }
    else if (event.key === "Enter") { event.preventDefault(); results[active]?.run(); }
  }

  let lastSection = "";
  return (
    <div className="dialog-backdrop shell-palette-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={ref} className="shell-palette" role="dialog" aria-modal="true" aria-label="Befehle und Suche">
        <div className="shell-palette-input">
          <Icon name="search" />
          <input
            data-autofocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={results[active] ? `${listId}-${active}` : undefined}
            aria-label="Suchen oder Befehl eingeben"
            placeholder="Vertrag, Partner, Seite oder Befehl suchen…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKey}
          />
          <kbd>Esc</kbd>
        </div>
        <ul id={listId} role="listbox" aria-label="Ergebnisse" className="shell-palette-list">
          {results.length === 0 ? <li className="shell-palette-empty" role="presentation">Keine Treffer. Für Vertragsinhalte mindestens zwei Zeichen eingeben.</li> : null}
          {results.map((command, index) => {
            const heading = command.section !== lastSection ? command.section : null;
            lastSection = command.section;
            return (
              <li key={command.id} role="presentation">
                {heading ? <div className="shell-palette-section" aria-hidden="true">{heading}</div> : null}
                <div
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className="shell-palette-option"
                  onMouseEnter={() => setActive(index)}
                  onClick={() => command.run()}
                >
                  <Icon name={command.icon} />
                  <span>{command.label}</span>
                  {command.hint && command.section !== "Seiten" ? <small>{command.hint}</small> : null}
                </div>
              </li>
            );
          })}
        </ul>
        <p className="shell-palette-foot"><kbd>↑</kbd><kbd>↓</kbd> auswählen · <kbd>Enter</kbd> öffnen · <kbd>?</kbd> alle Tastenkürzel</p>
      </div>
    </div>
  );
}
