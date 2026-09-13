import Image from "next/image";

type MedFluxLogoProps = {
  compact?: boolean;
  className?: string;
  priority?: boolean;
};

export default function MedFluxLogo({
  compact = false,
  className = "",
  priority = false,
}: MedFluxLogoProps) {
  const classes = ["medflux-logo", compact ? "medflux-logo--compact" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes}>
      <Image
        className="medflux-logo__image"
        src="/brand/medflux-main-logo.png"
        width={860}
        height={536}
        alt="MedFlux"
        priority={priority}
      />
    </span>
  );
}
