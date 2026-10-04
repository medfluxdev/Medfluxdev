"use client";

interface Props {
  pageNumber: number;
  pageCount: number;
  zoom: number;
  canRender: boolean;
  onPrev: () => void;
  onNext: () => void;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onResetZoom: () => void;
}

export default function PageControls({
  pageNumber,
  pageCount,
  zoom,
  canRender,
  onPrev,
  onNext,
  onZoomOut,
  onZoomIn,
  onResetZoom,
}: Props) {
  return (
    <div className="pdf-controls" role="toolbar" aria-label="PDF-Ansicht steuern">
      <button
        type="button"
        aria-label="Vorherige Seite"
        disabled={!canRender || pageNumber <= 1}
        onClick={onPrev}
      >
        ←
      </button>
      <span className="page-indicator" aria-live="polite">
        Seite {pageNumber} / {pageCount}
      </span>
      <button
        type="button"
        aria-label="Nächste Seite"
        disabled={!canRender || pageNumber >= pageCount}
        onClick={onNext}
      >
        →
      </button>

      <span className="pdf-toolbar-sep" aria-hidden="true" />

      <button
        type="button"
        aria-label="Zoom verkleinern"
        disabled={!canRender}
        onClick={onZoomOut}
      >
        –
      </button>
      <button
        type="button"
        className="zoom-value"
        aria-label="Zoom zurücksetzen"
        disabled={!canRender}
        onClick={onResetZoom}
      >
        {Math.round(zoom * 100)}%
      </button>
      <button
        type="button"
        aria-label="Zoom vergrößern"
        disabled={!canRender}
        onClick={onZoomIn}
      >
        +
      </button>
    </div>
  );
}
