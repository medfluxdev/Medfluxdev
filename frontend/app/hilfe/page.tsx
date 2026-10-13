"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import ShortcutTable from "@/components/shell/ShortcutTable";
import { SHORTCUTS } from "@/components/shell/useShortcuts";
import { HELP_SECTIONS, normalizeHelpText, searchHelp } from "@/lib/help-content";

const SHORTCUTS_ID = "tastenkuerzel";

// Hilfe: Antworten aus lib/help-content.ts plus Tastenkürzel aus derselben Liste wie der Dialog „?“.
export default function HelpPage() {
  const [query, setQuery] = useState("");
  const [hash, setHash] = useState("");
  useEffect(() => {
    const read = () => setHash(decodeURIComponent(window.location.hash.slice(1)));
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  useEffect(() => {
    if (hash) document.getElementById(hash)?.scrollIntoView({ block: "start" });
  }, [hash]);

  const term = normalizeHelpText(query.trim());
  const sections = useMemo(() => searchHelp(query), [query]);
  const shortcutRows = Boolean(term) && SHORTCUTS.some((item) => normalizeHelpText(`${item.keys} ${item.label} ${item.group}`).includes(term));
  const shortcutHits = !term || shortcutRows || normalizeHelpText("tastenkürzel tastatur kürzel").includes(term);
  const total = sections.reduce((sum, section) => sum + section.entries.length, 0) + (shortcutHits && term ? 1 : 0);

  return <div className="page help-page">
    <PageHeader title="Hilfe" description="Antworten zur Arbeit mit MedFlux und alle Tastenkürzel." />

    <div className="help-layout">
      <nav className="help-toc" aria-label="Themen">
        <ul>
          {HELP_SECTIONS.map((section) => <li key={section.id}><a href={`#${section.id}`}>{section.title}</a></li>)}
          <li><a href={`#${SHORTCUTS_ID}`}>Tastenkürzel</a></li>
        </ul>
        <p className="help-toc-note">Sicherheit und Datenschutz: <Link href="/sicherheit">eigene Seite</Link></p>
      </nav>

      <div className="help-main">
        <div className="help-search">
          <label htmlFor="help-search">Hilfe durchsuchen</label>
          <input id="help-search" type="search" placeholder="z. B. Kündigungsfrist, Import, Strg" value={query} onChange={(event) => setQuery(event.target.value)} />
          {term ? <p role="status" className="help-count">{total === 0 ? "Keine Treffer." : total === 1 ? "1 Treffer" : `${total} Treffer`}</p> : null}
        </div>

        {sections.map((section) => <section key={section.id} id={section.id} className="card card-pad help-section" aria-labelledby={`${section.id}-heading`}>
          <h2 id={`${section.id}-heading`} className="card-title">{section.title}</h2>
          <p className="help-section-intro">{section.description}</p>
          <div className="help-entries">
            {section.entries.map((entry) => <details key={entry.id} id={entry.id} className="help-entry" open={Boolean(term) || hash === entry.id}>
              <summary>{entry.question}</summary>
              <div className="help-answer">
                {entry.answer.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
                {entry.steps?.length ? <ol>{entry.steps.map((step) => <li key={step}>{step}</li>)}</ol> : null}
                {entry.links?.length ? <p className="help-links">{entry.links.map((link) => <Link key={link.href} href={link.href}>{link.label} →</Link>)}</p> : null}
              </div>
            </details>)}
          </div>
        </section>)}

        {shortcutHits ? <section id={SHORTCUTS_ID} className="card card-pad help-section" aria-labelledby={`${SHORTCUTS_ID}-heading`}>
          <h2 id={`${SHORTCUTS_ID}-heading`} className="card-title">Tastenkürzel</h2>
          <p className="help-section-intro">Funktionieren überall, außer beim Tippen in einem Feld (dort nur Strg + K und Strg + S). Mit ? öffnen Sie diese Liste jederzeit.</p>
          <ShortcutTable query={shortcutRows ? query : ""} />
        </section> : null}
      </div>
    </div>
  </div>;
}
