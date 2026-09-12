import { describe, expect, it } from "vitest";
import { formatDate } from "@/lib/format";

describe("formatDate – Invalid-date safety (UAT Defect: /archiv crash)", () => {
  it("formatet einen vollständigen ISO-Zeitstempel mit Zeitzone OHNE zu crashen", () => {
    // Exakter Wert aus dem Live-Backend nach dem Archivieren:
    // "2026-09-08T04:04:35.927313+02:00". Der alte Code hing T00:00:00 an ->
    // "Invalid time value".
    expect(() =>
      formatDate("2026-09-08T04:04:35.927313+02:00")
    ).not.toThrow();
    expect(formatDate("2026-09-08T04:04:35.927313+02:00")).toBe("08.09.2026");
  });

  it("formatet einen Zeitstempel ohne Zeitzone", () => {
    expect(formatDate("2026-09-08T04:04:35")).toBe("08.09.2026");
  });

  it("behält das Verhalten für reine Datumsangaben bei", () => {
    expect(formatDate("2029-03-31")).toBe("31.03.2029");
    expect(formatDate("2026-01-05")).toBe("05.01.2026");
  });

  it("liefert bei null, undefined und leerer Eingabe '–'", () => {
    expect(formatDate(null)).toBe("–");
    expect(formatDate(undefined)).toBe("–");
    expect(formatDate("")).toBe("–");
    expect(formatDate("   ")).toBe("–");
  });

  it("liefert bei fehlerhaften/unbrauchbaren Eingaben '–' statt zu crashen", () => {
    expect(() => formatDate("keine-echte-Ganzzahl")).not.toThrow();
    expect(formatDate("keine-echte-Ganzzahl")).toBe("–");
    expect(() => formatDate("31.12.2026")).not.toThrow();
    expect(formatDate("31.12.2026")).toBe("–");
  });
});