type MedFluxLogoProps = {
  compact?: boolean;
  showDescriptor?: boolean;
  className?: string;
};

export default function MedFluxLogo({
  compact = false,
  showDescriptor = false,
  className = "",
}: MedFluxLogoProps) {
  const classes = ["medflux-logo", compact ? "medflux-logo--compact" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} aria-label="MedFlux">
      <svg
        className="medflux-logo__mark"
        viewBox="0 0 160 96"
        role="img"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id="medflux-mark-gradient" x1="8" y1="18" x2="152" y2="78" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#14B8A6" />
            <stop offset="0.48" stopColor="#0797A7" />
            <stop offset="1" stopColor="#0F4C81" />
          </linearGradient>
        </defs>
        <path
          d="M8 76C29 76 30 20 51 20C72 20 70 76 91 76C112 76 111 20 133 20C145 20 151 34 156 52"
          fill="none"
          stroke="url(#medflux-mark-gradient)"
          strokeWidth="22"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {!compact ? (
        <span className="medflux-logo__copy">
          <span className="medflux-logo__wordmark" aria-hidden="true">
            <span className="medflux-logo__med">Med</span>
            <span className="medflux-logo__flux">Flux</span>
          </span>
          {showDescriptor ? (
            <span className="medflux-logo__descriptor">Healthcare Intelligence Platform</span>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
