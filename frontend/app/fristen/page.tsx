"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import DeadlineList from "@/components/deadlines/DeadlineList";
import RenewalOverview from "@/components/deadlines/RenewalOverview";
import PageHeader from "@/components/ui/PageHeader";
import Tabs, { TabPanel } from "@/components/ui/Tabs";
import TaskQueue from "@/components/work-queue/TaskQueue";

type View = "termine" | "entscheidungen" | "aufgaben";

const VIEWS: { key: View; label: string; description: string }[] = [
  { key: "termine", label: "Termine", description: "Kündigungsfristen, Vertragsenden und Wiedervorlagen – berechnet aus den gepflegten Vertragsdaten oder manuell angelegt." },
  { key: "entscheidungen", label: "Kündigungsentscheidungen", description: "Was vor der Kündigungsfrist ansteht, was es kostet und welche Entscheidung erfasst ist." },
  { key: "aufgaben", label: "Aufgaben", description: "Prüfbedarf, fehlende Kosten und Geräte-Zuordnungen aus der KI-Analyse." },
];

const TASK_ROLES = new Set(["admin", "contract_manager", "reviewer"]);

function readView(): View {
  try {
    const value = new URLSearchParams(window.location.search).get("ansicht");
    return VIEWS.some((item) => item.key === value) ? (value as View) : "termine";
  } catch {
    return "termine";
  }
}

// Ein Ort für alles, was ansteht: Termine, Kündigungsentscheidungen und Aufgaben.
export default function DeadlinesAndTasksPage() {
  const { organizationSlug, role, account } = useAuth();
  const [view, setView] = useState<View>("termine");
  const canSeeTasks = Boolean(account?.is_developer || (role && TASK_ROLES.has(role)));
  const views = VIEWS.filter((item) => item.key !== "aufgaben" || canSeeTasks);
  const current = views.find((item) => item.key === view) ?? views[0];

  useEffect(() => { setView(readView()); }, []);

  function change(next: View) {
    setView(next);
    try {
      const params = new URLSearchParams(window.location.search);
      if (next === "termine") params.delete("ansicht"); else params.set("ansicht", next);
      if (next !== "termine") params.delete("nur");
      const query = params.toString();
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    } catch {
      // Adresse ist nur Komfort.
    }
  }

  return <div className="page">
    <PageHeader title="Fristen & Aufgaben" description={current.description} />
    {organizationSlug ? <>
      <Tabs label="Fristen & Aufgaben" idPrefix="fristen" items={views.map(({ key, label }) => ({ key, label }))} active={current.key} onChange={change} />
      <TabPanel idPrefix="fristen" active={current.key}>
        {current.key === "termine" ? <DeadlineList organizationSlug={organizationSlug} /> : null}
        {current.key === "entscheidungen" ? <RenewalOverview organizationSlug={organizationSlug} /> : null}
        {current.key === "aufgaben" ? <TaskQueue /> : null}
      </TabPanel>
    </> : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </div>;
}
