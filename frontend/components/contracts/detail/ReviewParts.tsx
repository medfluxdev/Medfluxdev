import type { ReactNode } from "react";
import type { EvidenceSection } from "@/lib/evidence";

/** Gemeinsame Bausteine der geführten Prüfungen (Felder, Analyse-Vorschläge): Abschnittsmarke und Wortvergleich. */

export const icon = (body: ReactNode, className = "erm-icon") => <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;

export const SECTION_ICON: Record<string, ReactNode> = {
  partner: <><rect x="4" y="3" width="16" height="18" rx="1.5" /><path d="M8 7h3M13 7h3M8 11h3M13 11h3M8 15h3M13 15h3M10 21v-3h4v3" /></>,
  term: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  cost: <><circle cx="12" cy="12" r="9" /><path d="M15 8.5a4 4 0 1 0 0 7M7 11h6M7 13.5h6" /></>,
  services: <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z" />,
  device: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>,
  other: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></>,
};

export function SectionChip({ section }: { section: EvidenceSection }) {
  return <span className={`erm-section erm-tone--${section.tone}`}>{icon(SECTION_ICON[section.key] ?? SECTION_ICON.other, "erm-section-icon")}{section.label}</span>;
}

export function Diff({ tokens }: { tokens: { text: string; changed: boolean }[] }) {
  return <>{tokens.map((token, index) => <span key={index}>{index ? " " : ""}{token.changed ? <mark className="erm-diff">{token.text}</mark> : token.text}</span>)}</>;
}
