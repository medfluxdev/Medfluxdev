import Link from "next/link";
import type { ReactNode } from "react";

export type TagKind = "type" | "partner" | "department" | "cost" | "device";

export const TAG_ICON_PATHS: Record<TagKind, string> = {
  type: "M7 3h7l5 5v13H7zM14 3v5h5",
  partner: "M4 21V7l6-4 6 4v14M16 11h4v10M8 9h4M8 13h4M8 17h4",
  department: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M3 20a6 6 0 0 1 12 0M16 5a3 3 0 0 1 0 6M18 20a6 6 0 0 0-3-5",
  cost: "M9 4 7 20M17 4l-2 16M4 9h16M3 15h16",
  device: "M5 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 20h8M12 16v4",
};

/** Symbol einer Kennfarbe (dekorativ; die Bedeutung trägt das Wort). */
export function TagIcon({ kind, className = "tag-chip-icon" }: { kind: TagKind; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={TAG_ICON_PATHS[kind]} /></svg>;
}

/** Person mit Initiale in der Kontofarbe (Initiale dekorativ; der Name trägt die Bedeutung). */
export function PersonTag({ name }: { name: string }) {
  return <span className="tag-person"><span className="tag-avatar" aria-hidden="true">{name.trim().charAt(0).toLocaleUpperCase("de") || "?"}</span>{name}</span>;
}

type Props = {
  /** Kennfarbe + Symbol: Vertragstyp, Vertragspartner, Abteilung, Kostenstelle, Geräteart. */
  kind: TagKind;
  children: ReactNode;
  /** Nummer vor dem Namen (Kostenstelle), in Mono mit feinem Trenner. */
  code?: string;
  /** Unsichtbares Präfix für Screenreader, z. B. „Vertragstyp“. */
  srLabel?: string;
  /** Zusätzliche Klassen, z. B. `tag-chip--missing`. */
  className?: string;
  title?: string;
} & (
  | { as?: "span"; onClick?: never; href?: never }
  | { as: "button"; onClick: () => void; href?: never }
  | { as: "link"; href: string; onClick?: never }
);

/**
 * Hauptangabe mit Kennfarbe, Symbol und Wort (nie Farbe allein). Kennfarben stehen für die Art
 * der Angabe, nie für einen Zustand; Zustände zeigt `Signal`.
 */
export default function TagChip(props: Props) {
  const { kind, children, code, srLabel, className, title } = props;
  const classes = ["tag-chip", `tag-chip--${kind}`, className ?? ""].filter(Boolean).join(" ");
  const content = <>
    <TagIcon kind={kind} />
    {srLabel ? <span className="sr-only">{srLabel}: </span> : null}
    {code ? <><span className="tag-chip-code mono">{code}</span><span className="sr-only"> </span></> : null}
    {children}
  </>;
  if (props.as === "button") return <button type="button" className={classes} onClick={props.onClick} title={title}>{content}</button>;
  if (props.as === "link") return <Link className={classes} href={props.href} title={title}>{content}</Link>;
  return <span className={classes} title={title}>{content}</span>;
}
