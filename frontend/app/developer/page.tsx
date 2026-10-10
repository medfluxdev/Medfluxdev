"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ComponentReference from "@/components/developer/ComponentReference";
import DeveloperOverview from "@/components/developer/DeveloperOverview";
import ProcessingRuns from "@/components/developer/ProcessingRuns";
import PageHeader from "@/components/ui/PageHeader";
import Tabs, { TabPanel } from "@/components/ui/Tabs";
import styles from "./developer.module.css";

type DeveloperTab = "uebersicht" | "verarbeitung" | "bausteine";
const TABS: { key: DeveloperTab; label: string }[] = [
  { key: "uebersicht", label: "Übersicht" },
  { key: "verarbeitung", label: "Dokumentverarbeitung" },
  { key: "bausteine", label: "UI-Bausteine" },
];

function readTab(): DeveloperTab {
  try {
    const value = new URLSearchParams(window.location.search).get("tab");
    return TABS.some((item) => item.key === value) ? (value as DeveloperTab) : "uebersicht";
  } catch {
    return "uebersicht";
  }
}

// Entwicklung: ein Bereich nur für das Developer-Konto (organisationsübergreifend, daher nicht in der Verwaltung).
export default function DeveloperPage() {
  const { account } = useAuth();
  const [tab, setTab] = useState<DeveloperTab>("uebersicht");

  useEffect(() => { setTab(readTab()); }, []);

  function change(next: DeveloperTab) {
    setTab(next);
    try {
      const params = new URLSearchParams(window.location.search);
      if (next === "uebersicht") params.delete("tab"); else params.set("tab", next);
      const query = params.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  if (!account?.is_developer) {
    return <section className="cw-section"><h1>Keine Berechtigung</h1><p className="cw-muted">Dieser Bereich ist ausschließlich für das MedFlux-Developer-Konto verfügbar.</p><Link href="/">Zur Übersicht</Link></section>;
  }

  return <div className={styles.page}>
    <PageHeader variant="highlight" eyebrow="Systemverwaltung" title="Entwicklung" description="Technischer Zustand, alle Organisationen, Dokumentverarbeitung und UI-Bausteine." />
    <Tabs label="Bereiche der Entwicklung" idPrefix="dev" items={TABS} active={tab} onChange={change} />
    <TabPanel idPrefix="dev" active={tab}>
      {tab === "uebersicht" ? <DeveloperOverview /> : tab === "verarbeitung" ? <ProcessingRuns /> : <ComponentReference />}
    </TabPanel>
  </div>;
}
