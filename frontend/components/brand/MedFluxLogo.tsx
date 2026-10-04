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

  // Zwei Fassungen: Im dunklen Design ist das Marineblau ("Flux", rechter Bogen)
  // aufgehellt; Tuerkis bleibt unveraendert. Sichtbar ist per CSS immer nur eine.
  return (
    <span className={classes}>
      <Image
        className="medflux-logo__image medflux-logo__image--light"
        src="/brand/medflux-main-logo.png"
        width={733}
        height={499}
        alt="MedFlux"
        priority={priority}
      />
      <Image
        className="medflux-logo__image medflux-logo__image--dark"
        src="/brand/medflux-main-logo-dark.png"
        width={733}
        height={499}
        alt="MedFlux"
        priority={priority}
      />
    </span>
  );
}
