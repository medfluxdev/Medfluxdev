"use client";

import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Tabs, { TabPanel } from "@/components/ui/Tabs";
import { useAuth } from "@/components/auth/AuthProvider";
import AddContractMenu from "@/components/register/AddContractMenu";
import RegisterGrid from "@/components/register/RegisterGrid";
import { getGridCounts } from "@/lib/domain-api/registerGrid";

type Tab = "bestand" | "review" | "archive";

const TABS: { key: Tab; label: string; viewKey?: string; description: string }[] = [
  { key: "bestand", label: "Bestand", description: "Alle Verträge mit frei wählbaren Spalten, Filtern, Gruppen und gespeicherten Ansichten." },
  { key: "review", label: "Zu prüfen", viewKey: "review", description: "Verträge, deren KI-Analyse noch nicht geprüft ist. „Prüfen“ öffnet die Prüfung mit Belegen." },
  { key: "archive", label: "Archiv", viewKey: "archive", description: "Abgelegte Verträge. Archivieren ist umkehrbar – es wird nichts gelöscht." },
];
const REVIEW_ROLES = new Set(["admin", "contract_manager", "reviewer"]);
const ARCHIVE_ROLES = new Set(["admin", "contract_manager"]);

function readTab(): Tab {
  try {
    const value = new URLSearchParams(window.location.search).get("ansicht");
    return value === "review" ? "review" : value === "archive" ? "archive" : "bestand";
  } catch {
    return "bestand";
  }
}

// Eine Vertragsliste mit drei Reitern: derselbe Datensatz, dieselben Kennungen, nur der Ausschnitt wechselt.
export default function RegisterPage() {
  const { organizationSlug, role, account } = useAuth();
  const [tab, setTab] = useState<Tab | null>(null);
  const [counts, setCounts] = useState<Record<Tab, number> | null>(null);
  const developer = Boolean(account?.is_developer);
  const tabs = TABS.filter((item) =>
    item.key === "bestand"
    || (item.key === "review" && (developer || (role && REVIEW_ROLES.has(role))))
    || (item.key === "archive" && (developer || (role && ARCHIVE_ROLES.has(role)))));

  useEffect(() => { setTab(readTab()); }, []);

  const loadCounts = useCallback(() => {
    if (!organizationSlug) return;
    getGridCounts(organizationSlug)
      .then((result) => setCounts({ bestand: result.bestand, review: result.review, archive: result.archive }))
      .catch(() => setCounts(null));
  }, [organizationSlug]);

  useEffect(loadCounts, [loadCounts]);
  useEffect(() => {
    window.addEventListener("medflux:register-changed", loadCounts);
    return () => window.removeEventListener("medflux:register-changed", loadCounts);
  }, [loadCounts]);

  function change(next: Tab) {
    setTab(next);
    try {
      // Reiterwechsel beginnt mit einer frischen Auswahl; Filter des alten Reiters gelten nicht weiter.
      const params = new URLSearchParams();
      if (next !== "bestand") params.set("ansicht", next);
      const query = params.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  const current = tabs.find((item) => item.key === tab) ?? tabs[0];
  return (
    <div className="page">
      <PageHeader
        title="Verträge"
        description={current.description}
        actions={organizationSlug ? <AddContractMenu /> : undefined}
      />
      {organizationSlug && tab ? <>
        <Tabs
          label="Vertragsbereiche"
          idPrefix="vertraege"
          items={tabs.map((item) => ({ key: item.key, label: item.label, badge: counts ? counts[item.key] : undefined }))}
          active={current.key}
          onChange={change}
        />
        <TabPanel idPrefix="vertraege" active={current.key}>
          <RegisterGrid key={current.key} organizationSlug={organizationSlug} initialViewKey={current.viewKey} tab={current.key} />
        </TabPanel>
      </> : organizationSlug ? null : <p>Bitte zuerst eine Organisation auswählen.</p>}
    </div>
  );
}
