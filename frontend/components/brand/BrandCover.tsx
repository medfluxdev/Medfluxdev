// Titelbild der Richtung "Sachlich-institutionell": flache Navy-Flaechen, ein Blatt mit
// Haarlinien statt Schatten, eine einzige Teal-Marke. Rein dekorativ, Text bleibt lesbar.
export default function BrandCover({ className }: { className?: string }) {
  return (
    <div className={["brand-cover", className].filter(Boolean).join(" ")}>
      <svg className="brand-cover-art" viewBox="0 0 960 288" aria-hidden="true" focusable="false">
        <rect className="brand-cover-panel" x="496.5" y="48.5" width="192" height="192" rx="4" />
        <rect className="brand-cover-navy" x="736" y="0" width="224" height="288" />
        <rect className="brand-cover-deep" x="704" y="144" width="32" height="144" />
        <rect className="brand-cover-mark" x="496" y="0" width="48" height="24" />
        <line className="brand-cover-rule" x1="512" y1="96.5" x2="672" y2="96.5" />
        <line className="brand-cover-rule" x1="512" y1="120.5" x2="672" y2="120.5" />
        <line className="brand-cover-rule" x1="512" y1="144.5" x2="640" y2="144.5" />
        <line className="brand-cover-rule" x1="512" y1="168.5" x2="608" y2="168.5" />
        <line className="brand-cover-rule-inverse" x1="760" y1="96.5" x2="960" y2="96.5" />
        <line className="brand-cover-rule-inverse" x1="760" y1="120.5" x2="960" y2="120.5" />
        <line className="brand-cover-rule-inverse" x1="760" y1="144.5" x2="960" y2="144.5" />
      </svg>
      <div className="brand-cover-text">
        <p className="brand-cover-name">MedFlux</p>
        <p className="brand-cover-tagline">Ruhige, nachvollziehbare Vertragsarbeit für öffentliche Krankenhäuser.</p>
      </div>
    </div>
  );
}
