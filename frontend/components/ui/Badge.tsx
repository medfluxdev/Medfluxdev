import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "ai";

// Kurzes Kennzeichen; der Text traegt die Bedeutung, Farbe unterstuetzt nur.
export default function Badge({ tone = "neutral", children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  return <span className={`badge${tone === "neutral" ? "" : ` badge--${tone}`}`} title={title}>{children}</span>;
}
