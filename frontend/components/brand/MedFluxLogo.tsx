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
        width={430}
        height={355}
        alt="MedFlux — Healthcare Intelligence Platform"
        priority={priority}
      />
    </span>
  );
}
