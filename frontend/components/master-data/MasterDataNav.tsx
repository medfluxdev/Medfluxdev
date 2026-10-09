"use client";

import { AreaNav } from "@/components/shell/AreaNav";
import { MASTER_DATA_GROUPS, MASTER_DATA_HOME, MASTER_DATA_SECTIONS } from "@/lib/master-data";

// Bereichsnavigation der Stammdaten: Übersicht, dann je Gruppe die Datenarten.
export default function MasterDataNav() {
  const lookups = MASTER_DATA_SECTIONS.filter((section) => section.fieldKey);
  return <AreaNav
    label="Stammdaten"
    groups={[
      { items: [{ href: MASTER_DATA_HOME, label: "Übersicht" }] },
      ...MASTER_DATA_GROUPS.map((group) => ({
        title: group,
        items: MASTER_DATA_SECTIONS.filter((section) => section.group === group && !section.fieldKey).map((section) => ({ href: section.href, label: section.label })),
        more: group === "Vertragsdaten" ? { label: "Auswahllisten", items: lookups.map((section) => ({ href: section.href, label: section.label })) } : undefined,
      })),
    ]}
  />;
}
