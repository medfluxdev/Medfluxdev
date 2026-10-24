/**
 * Vorauswahl in der Entscheidung zu einem Feld (Panel „Angaben prüfen“).
 *
 * Ein Feld kann mehrere Werte haben (Hauptvertrag und Nachtrag sagen Verschiedenes). Vorgeschlagen wird – nur als Vorauswahl,
 * nie als Entscheidung – der Wert, der im Dokumentenbestand zuletzt gilt: ein Nachtrag schlägt den Hauptvertrag, danach zählt die
 * höhere Seite. Bei Gleichstand bleibt der gespeicherte Wert; ohne jeden Beleg wird nichts vorgeschlagen, wenn es mehrere gibt.
 */

export interface PreselectEvidence {
  /** Rolle des Dokuments (z. B. „main“, „amendment“); null = unbekannt. */
  role: string | null;
  page: number | null;
}

export interface PreselectCandidate {
  key: string;
  /** Der aktuell gespeicherte Wert. */
  isCurrent: boolean;
  /** Nicht ausgeschlossene Belege dieses Werts. */
  evidence: PreselectEvidence[];
}

/** Rang eines Dokuments: Nachträge und Vereinbarungen vor dem Hauptvertrag vor Anlagen. */
export function documentRank(role: string | null): number {
  if (role === "amendment" || role === "price_adjustment" || role === "renewal_letter") return 3;
  if (role === "main") return 2;
  return 1;
}

function strength(candidate: PreselectCandidate): [number, number] | null {
  if (candidate.evidence.length === 0) return null;
  let best: [number, number] = [0, 0];
  for (const entry of candidate.evidence) {
    const rank = documentRank(entry.role);
    const page = entry.page ?? 0;
    if (rank > best[0] || (rank === best[0] && page > best[1])) best = [rank, page];
  }
  return best;
}

/** Schlüssel des vorzuwählenden Werts; null, wenn es nichts Eindeutiges gibt. */
export function preselectCandidate(candidates: PreselectCandidate[]): string | null {
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0].key;
  let winner: PreselectCandidate | null = null;
  let winnerStrength: [number, number] | null = null;
  let tie = false;
  for (const candidate of candidates) {
    const value = strength(candidate);
    if (!value) continue;
    if (!winnerStrength || value[0] > winnerStrength[0] || (value[0] === winnerStrength[0] && value[1] > winnerStrength[1])) {
      winner = candidate; winnerStrength = value; tie = false;
    } else if (value[0] === winnerStrength[0] && value[1] === winnerStrength[1]) {
      tie = true;
    }
  }
  if (!winner) return candidates.find((candidate) => candidate.isCurrent)?.key ?? null;
  if (tie) return candidates.find((candidate) => candidate.isCurrent)?.key ?? winner.key;
  return winner.key;
}
