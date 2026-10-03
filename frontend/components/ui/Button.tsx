import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "ghost" | "primary" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "md" | "sm";
  loading?: boolean;
  loadingLabel?: ReactNode;
}

export default function Button({
  variant = "ghost",
  size = "md",
  loading = false,
  loadingLabel = "Wird verarbeitet…",
  className,
  type = "button",
  disabled,
  children,
  ...rest
}: Props) {
  const cls = [
    "btn",
    variant === "primary" ? "btn-primary" : "",
    variant === "danger" ? "btn-danger" : "",
    size === "sm" ? "btn-sm" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      className={cls}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <span className="loading-spinner" aria-hidden="true" />
          <span>{loadingLabel}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
