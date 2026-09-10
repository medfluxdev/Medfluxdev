import type { ButtonHTMLAttributes } from "react";

type Variant = "ghost" | "primary" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "md" | "sm";
}

export default function Button({
  variant = "ghost",
  size = "md",
  className,
  type = "button",
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
  return <button type={type} className={cls} {...rest} />;
}