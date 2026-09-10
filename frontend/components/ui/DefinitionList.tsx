import type { ReactNode } from "react";

export interface Rule {
  label: ReactNode;
  value: ReactNode;
  highlight?: boolean;
}

interface Props {
  rules: Rule[];
}

// Einheitliches Begriffs-/Wert-Raster (dl). Backend bleibt autoritativ; hier
// wird nur formatiert, nie berechnet.
export default function DefinitionList({ rules }: Props) {
  return (
    <dl className="rules">
      {rules.map((r, i) => (
        <div
          key={i}
          className={`rule${r.highlight ? " rule--highlight" : ""}`}
        >
          <dt>{r.label}</dt>
          <dd>{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}