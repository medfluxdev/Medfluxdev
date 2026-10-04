import type { CalcBasis } from "@/lib/contract-detail-types";

interface Props {
  title: string;
  basis: CalcBasis | null | undefined;
}

export function hasCalculationBasis(basis: CalcBasis | null | undefined): boolean {
  return Boolean(basis?.explanation || Object.keys(basis?.inputs ?? {}).length > 0);
}

export default function CalculationBasisPanel({ title, basis }: Props) {
  if (!hasCalculationBasis(basis)) return null;
  const inputs = Object.entries(basis?.inputs ?? {});

  return (
    <article className="cw-calc-basis">
      <div className="cw-calc-basis-head">
        <span className="cw-origin-badge cw-origin-calculated">Berechnet</span>
        <strong>{title}</strong>
      </div>
      {basis?.explanation ? <p>{basis.explanation}</p> : null}
      {inputs.length > 0 ? (
        <dl>
          {inputs.map(([key, value]) => (
            <div key={key}>
              <dt>{key.replace(/_/g, " ")}</dt>
              <dd>{value || "Nicht verfügbar"}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <small>Vom System aus den Vertragsdaten berechnet – nicht von der KI geschätzt.</small>
    </article>
  );
}
