"use client";

import { evidenceGroupLabel } from "@/lib/contract-detail-types";
import type { EvidenceRef, SourceNavigationTarget } from "@/lib/contract-detail-types";
import { evidencePrecision } from "@/lib/source-geometry";

interface Props {
  evidence: EvidenceRef[];
  activeEvidenceId: string | null;
  onNavigate: (ref: EvidenceRef) => void;
}

function fieldLabel(fieldRef: string | null): string {
  if (!fieldRef) return "Quellenangabe";
  const last = fieldRef.split(".").pop() ?? fieldRef;
  return last.replace(/_/g, " ");
}

function toTarget(ref: EvidenceRef): SourceNavigationTarget {
  return {
    document_version_id: ref.document_version_id,
    page: ref.page,
    bbox: ref.bbox,
    bbox_space: ref.bbox_space,
    supports_exact_navigation: ref.supports_exact_navigation,
    label: `${fieldLabel(ref.field_ref)} · ${sourceLabel(ref)}`,
    field_ref: ref.field_ref,
    evidence_id: ref.evidence_id,
  };
}

function isCoarseBbox(ref: EvidenceRef): boolean {
  if (!ref.bbox || ref.page == null) return false;
  return evidencePrecision(ref.bbox, ref.bbox_space) === "coarse";
}

function precisionLabel(ref: EvidenceRef): string {
  if (ref.bbox && ref.page != null) {
    return isCoarseBbox(ref) ? "Ungefähre Lage" : "Positionsbestimmt";
  }
  if (ref.page != null) return "Seite, ohne Position";
  return "Ohne Positionsangabe";
}

function sourceLabel(ref: EvidenceRef): string {
  if (ref.page != null) return `Seite ${ref.page}`;
  if (ref.paragraph_index != null) return `Absatz ${ref.paragraph_index}`;
  if (ref.table_index != null) return `Tabelle ${ref.table_index}`;
  return "Quelle";
}

function confidenceLabel(value: number | null): string | null {
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return null;
  return `Konfidenz ${Math.round(value * 100)}%`;
}

export default function EvidencePane({ evidence, activeEvidenceId, onNavigate }: Props) {
  if (evidence.length === 0) {
    return <p className="evidence-empty">Keine Quellenangaben vorhanden.</p>;
  }

  return (
    <ul className="evidence-list">
      {evidence.map((ref) => {
        const active = ref.evidence_id === activeEvidenceId;
        const exactPosition = Boolean(ref.bbox && ref.page != null && ref.supports_exact_navigation && !isCoarseBbox(ref));
        const confidence = confidenceLabel(ref.confidence);
        void toTarget;
        return (
          <li key={ref.evidence_id}>
            <button
              type="button"
              className={`evidence-item${active ? " active" : ""}`}
              aria-pressed={active}
              onClick={() => onNavigate(ref)}
            >
              <span className="evidence-head">
                <span className="evidence-field">{fieldLabel(ref.field_ref)}</span>
                <span className={`evidence-pill${exactPosition ? " ok" : ""}`}>
                  {precisionLabel(ref)}
                </span>
              </span>
              {evidenceGroupLabel(ref.field_ref?.split(".")[0] ?? null) && (
                <span className="evidence-meta">
                  {evidenceGroupLabel(ref.field_ref?.split(".")[0] ?? null)}
                </span>
              )}
              {(ref.page != null || ref.paragraph_index != null || ref.table_index != null) && (
                <span className="evidence-meta">
                  {sourceLabel(ref)}
                  {ref.source_type ? ` · ${ref.source_type}` : ""}
                  {confidence ? ` · ${confidence}` : ""}
                </span>
              )}
              {ref.snippet && <span className="evidence-snippet">„{ref.snippet}“</span>}
              {ref.requires_review && <span className="evidence-review">Manuelle Prüfung empfohlen</span>}
              {!exactPosition && ref.page != null && !isCoarseBbox(ref) && (
                <span className="evidence-note">
                  Quelle auf Seite {ref.page}, aber ohne exakte Position (keine Wort-Hervorhebung).
                </span>
              )}
              {ref.page != null && isCoarseBbox(ref) && (
                <span className="evidence-note">
                  Seitenbereich grob markiert – die Quelle ist dort nur ungefähr lokalisiert (keine exakte Wort-Position).
                </span>
              )}
              {ref.page == null && (
                <span className="evidence-note">
                  Keine Seitenangabe – Quelle nicht im Original lokalisierbar.
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
