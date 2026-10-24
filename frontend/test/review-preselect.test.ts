import { describe, expect, it } from "vitest";
import { documentRank, preselectCandidate, type PreselectCandidate } from "@/lib/review/preselect";

const card = (key: string, isCurrent: boolean, evidence: PreselectCandidate["evidence"]): PreselectCandidate => ({ key, isCurrent, evidence });

describe("Vorauswahl in der Feldentscheidung", () => {
  it("ein einziger Wert wird vorgewählt, ohne Werte nichts", () => {
    expect(preselectCandidate([])).toBeNull();
    expect(preselectCandidate([card("a", true, [])])).toBe("a");
  });

  it("ein Nachtrag schlägt den Hauptvertrag, auch wenn der gespeicherte Wert aus dem Hauptvertrag stammt", () => {
    const stored = card("01.01", true, [{ role: "main", page: 3 }]);
    const later = card("01.02", false, [{ role: "amendment", page: 8 }]);
    expect(preselectCandidate([stored, later])).toBe("01.02");
    expect(documentRank("amendment")).toBeGreaterThan(documentRank("main"));
    expect(documentRank("main")).toBeGreaterThan(documentRank("attachment"));
  });

  it("im gleichen Dokument gewinnt die höhere Seite", () => {
    const early = card("a", true, [{ role: "main", page: 2 }]);
    const late = card("b", false, [{ role: "main", page: 9 }]);
    expect(preselectCandidate([early, late])).toBe("b");
  });

  it("bei Gleichstand bleibt der gespeicherte Wert", () => {
    const stored = card("a", true, [{ role: "main", page: 4 }]);
    const other = card("b", false, [{ role: "main", page: 4 }]);
    expect(preselectCandidate([other, stored])).toBe("a");
  });

  it("ohne Belege wird der gespeicherte Wert vorgeschlagen, sonst nichts erfunden", () => {
    expect(preselectCandidate([card("a", true, []), card("b", false, [])])).toBe("a");
    expect(preselectCandidate([card("a", false, []), card("b", false, [])])).toBeNull();
  });

  it("ein belegter Wert schlägt einen unbelegten", () => {
    expect(preselectCandidate([card("a", true, []), card("b", false, [{ role: null, page: 1 }])])).toBe("b");
  });
});
