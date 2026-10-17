"use client";

import { Fragment, useState, type ReactNode } from "react";
import type { ContractAssignment } from "@/lib/contract-detail-types";
import TagChip from "@/components/ui/TagChip";

/** Unter 800 px sichtbare Chips je Zeile; der Rest steckt hinter „+N“. */
const VISIBLE_NARROW = 3;
/** Gerätearten: bis zu zwei Namen ausgeschrieben, der Rest als „+N“ (volle Liste im Titel). */
const DEVICE_NAMES_MAX = 2;

/** Ein Chip mit stabilem Schlüssel; `null` = Angabe fehlt und ist nicht verpflichtend (kein Chip, keine Lücke). */
export type ChipItem = { key: string; node: ReactNode } | null;

/**
 * Chip-Zeile im Vertragskopf (Name nur für Screenreader). Die Reihenfolge ist in allen Verträgen gleich; Chips einer
 * Familie (z. B. Abteilungen) stehen enger beieinander als die Familien. Unter 800 px nur die ersten drei Chips und „+N“ (per CSS).
 */
export function ChipRow({ label, families }: {
  label: string;
  families: ChipItem[][];
}) {
  const [expanded, setExpanded] = useState(false);
  let index = 0;
  const groups = families
    .map((family) => family.filter((item): item is NonNullable<ChipItem> => item !== null))
    .filter((family) => family.length > 0)
    .map((family) => family.map((item) => ({ ...item, extra: index++ >= VISIBLE_NARROW })));
  const hidden = index - VISIBLE_NARROW;
  return <div className="object-header-chips" role="group" aria-label={label} data-expanded={expanded ? "" : undefined}>
    {groups.map((family) => <span key={family[0].key} className={family.every((item) => item.extra) ? "chip-family chip-family--extra" : "chip-family"}>
      {family.map((item) => <Fragment key={item.key}>{item.extra ? <span className="chip-slot chip-slot--extra">{item.node}</span> : item.node}</Fragment>)}
    </span>)}
    {hidden > 0 && !expanded
      ? <button type="button" className="tag-chip chip-row-more" onClick={() => setExpanded(true)} aria-label={`${hidden} weitere Angaben zeigen`}>+{hidden}</button>
      : null}
  </div>;
}

export function deviceTypesLabel(names: string[]): string {
  return names.length > DEVICE_NAMES_MAX ? `${names.slice(0, DEVICE_NAMES_MAX).join(" · ")} +${names.length - DEVICE_NAMES_MAX}` : names.join(" · ");
}

/**
 * Zeile „Zuständigkeit“: Krankenhaus (nur bei mehreren Krankenhäusern) → Abteilungen → Kostenstelle → Gerätearten
 * → Hauptverantwortlich. Bearbeiten steht oben rechts bei den Kopfknöpfen. Pflichtangaben (Person, verantwortliche Abteilung, Kostenstelle) bleiben
 * leer als gestrichelter Chip an ihrem Platz. Jeder Chip führt zur Karte, aus der der Wert kommt
 * („Vertragsdaten → Organisationszuordnung“; dort ansehen oder – mit Recht – ändern).
 */
export default function ResponsibilityChips({ assignment, canEdit, onOpen, hospitalCount }: {
  assignment: ContractAssignment | null | undefined;
  canEdit: boolean;
  /** Öffnet die Organisationszuordnung (Quelle aller Angaben dieser Zeile). */
  onOpen: () => void;
  /** Aktive Krankenhäuser der Organisation; `null` = unbekannt (dann wird das Krankenhaus gezeigt). */
  hospitalCount: number | null;
}) {
  const a = assignment ?? null;
  const users = [...(a?.beneficiary_departments ?? []), ...(a?.other_departments ?? [])]
    .filter((name, position, all) => name !== a?.responsible_department && all.indexOf(name) === position);
  const devices = a?.device_types ?? [];
  const source = canEdit ? "in der Organisationszuordnung ansehen oder ändern" : "in der Organisationszuordnung ansehen";
  const tip = (label: string) => `${label} – ${source}`;
  const missing = (key: string, label: string): ChipItem => ({
    key,
    node: <button type="button" className="tag-chip tag-chip--missing" onClick={onOpen} title={tip(label)}>{label} –<span className="sr-only">{canEdit ? " festlegen" : " nicht festgelegt"}</span></button>,
  });

  return <ChipRow label="Zuständigkeit" families={[
    [a && (hospitalCount === null || hospitalCount > 1) ? { key: "hospital", node: <TagChip kind="hospital" as="button" onClick={onOpen} srLabel="Krankenhaus" title={tip("Krankenhaus")}>{a.hospital ?? "Organisationsweit"}</TagChip> } : null],
    [
      a?.responsible_department ? { key: "department", node: <TagChip kind="department" as="button" onClick={onOpen} srLabel="Verantwortliche Abteilung" title={tip("Verantwortliche Abteilung")}>{a.responsible_department}</TagChip> } : missing("department", "Verantwortliche Abteilung"),
      ...users.map((name) => ({ key: `user-${name}`, node: <TagChip kind="department" as="button" onClick={onOpen} className="tag-chip--secondary" srLabel="Nutzende Abteilung" title={tip("Nutzende Abteilung")}>{name}</TagChip> })),
    ],
    [a?.cost_center ? { key: "cost", node: <TagChip kind="cost" as="button" onClick={onOpen} srLabel="Kostenstelle" code={a.cost_center.code} title={tip("Kostenstelle")}>{a.cost_center.name}</TagChip> } : missing("cost", "Kostenstelle")],
    [devices.length ? { key: "devices", node: <TagChip kind="device" as="button" onClick={onOpen} srLabel="Gerätearten" title={`${devices.join(" · ")} – ${source}`}>{deviceTypesLabel(devices)}</TagChip> } : null],
    [a?.responsible
      ? { key: "responsible", node: <button type="button" className="tag-chip tag-chip--person" onClick={onOpen} title={tip("Hauptverantwortlich")}><span className="tag-avatar" aria-hidden="true">{a.responsible.trim().charAt(0).toLocaleUpperCase("de") || "?"}</span><span className="sr-only">Hauptverantwortlich: </span>{a.responsible}</button> }
      : missing("responsible", "Hauptverantwortlich")],
  ]} />;
}
