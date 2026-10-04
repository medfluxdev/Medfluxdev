// Platzhalter waehrend des Ladens; fuer Screenreader gibt es eine Statusmeldung.
export default function Skeleton({ lines = 3, label = "Wird geladen…" }: { lines?: number; label?: string }) {
  return (
    <div className="skeleton-stack" role="status" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className={`skeleton skeleton--${index % 3}`} aria-hidden="true" />
      ))}
    </div>
  );
}
