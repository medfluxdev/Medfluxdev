import type { ReactNode } from "react";

interface Props {
  title?: string;
  children: ReactNode;
  className?: string;
  pad?: boolean;
}

export default function SectionCard({
  title,
  children,
  className,
  pad = true,
}: Props) {
  return (
    <section
      className={`card${pad ? " card-pad" : ""}${className ? ` ${className}` : ""}`}
    >
      {title && (
        <h2 className="card-title">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}