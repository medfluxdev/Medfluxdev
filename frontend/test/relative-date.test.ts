import { describe, expect, it } from "vitest";
import { buildIcs, escapeIcsText } from "@/lib/ics";
import { daysBetween, formatLeadTime, formatRelativeDate } from "@/lib/relative-date";

const TODAY = "2026-10-14";

describe("formatRelativeDate", () => {
  it("heute, morgen, gestern", () => {
    expect(formatRelativeDate("2026-10-14", TODAY)).toBe("heute");
    expect(formatRelativeDate("2026-10-15", TODAY)).toBe("morgen");
    expect(formatRelativeDate("2026-10-13", TODAY)).toBe("gestern");
  });

  it("Tage bis 14, dann Wochen bis 12, dann Monate, dann Jahre", () => {
    expect(formatRelativeDate("2026-10-16", TODAY)).toBe("in 2 Tagen");
    expect(formatRelativeDate("2026-10-28", TODAY)).toBe("in 14 Tagen");
    expect(formatRelativeDate("2026-10-29", TODAY)).toBe("in 2 Wochen");
    expect(formatRelativeDate("2026-12-09", TODAY)).toBe("in 8 Wochen");
    expect(formatRelativeDate("2027-01-06", TODAY)).toBe("in 12 Wochen");
    expect(formatRelativeDate("2027-01-07", TODAY)).toBe("in 3 Monaten");
    expect(formatRelativeDate("2027-10-20", TODAY)).toBe("in 1 Jahr");
    expect(formatRelativeDate("2027-11-14", TODAY)).toBe("in 1 Jahr, 1 Monat");
    expect(formatRelativeDate("2029-03-31", TODAY)).toBe("in 2 Jahren, 5 Monaten");
  });

  it("Vergangenes mit „vor …“ und Einzahl", () => {
    expect(formatRelativeDate("2026-10-11", TODAY)).toBe("vor 3 Tagen");
    expect(formatRelativeDate("2026-10-07", TODAY)).toBe("vor 7 Tagen");
    expect(formatRelativeDate("2026-09-01", TODAY)).toBe("vor 6 Wochen");
    expect(formatRelativeDate("2026-06-14", TODAY)).toBe("vor 4 Monaten");
    expect(formatRelativeDate("2025-10-01", TODAY)).toBe("vor 1 Jahr");
  });

  it("zählt Kalendertage über die Zeitumstellung", () => {
    expect(daysBetween("2026-03-28", "2026-03-30")).toBe(2);
  });
});

describe("formatLeadTime", () => {
  it("ganze Monate, Wochen, sonst Tage – vor dem genannten Termin", () => {
    expect(formatLeadTime("2028-11-30", "2029-03-31", "Vertragsende")).toBe("4 Monate vor Vertragsende");
    expect(formatLeadTime("2029-03-03", "2029-03-31", "Vertragsende")).toBe("4 Wochen vor Vertragsende");
    expect(formatLeadTime("2029-03-24", "2029-03-31", "Kündbar bis")).toBe("1 Woche vor Kündbar bis");
    expect(formatLeadTime("2029-03-28", "2029-03-31", "Kündbar bis")).toBe("3 Tage vor Kündbar bis");
    expect(formatLeadTime("2028-03-31", "2029-03-31", "Vertragsende")).toBe("1 Jahr vor Vertragsende");
    expect(formatLeadTime("2029-02-28", "2029-03-31", "Vertragsende")).toBe("1 Monat vor Vertragsende");
  });
});

describe("buildIcs", () => {
  it("ganztägiger Termin mit maskiertem Text und CRLF", () => {
    const ics = buildIcs({ uid: "d-1", date: "2029-03-31", title: "Kündigung; Vertrag, prüfen", description: "Zeile 1\nZeile 2" }, new Date("2026-10-14T08:00:00Z"));
    expect(ics).toContain("DTSTART;VALUE=DATE:20290331\r\n");
    expect(ics).toContain("DTEND;VALUE=DATE:20290401\r\n");
    expect(ics).toContain("SUMMARY:Kündigung\\; Vertrag\\, prüfen\r\n");
    expect(ics).toContain("DESCRIPTION:Zeile 1\\nZeile 2\r\n");
    expect(ics).toContain("DTSTAMP:20261014T080000Z");
    expect(ics.startsWith("BEGIN:VCALENDAR\r\n")).toBe(true);
    expect(escapeIcsText("a\\b")).toBe("a\\\\b");
  });

  it("faltet lange Zeilen auf höchstens 75 Oktette", () => {
    const ics = buildIcs({ uid: "d-2", date: "2029-12-31", title: "Ä".repeat(80) });
    const encoder = new TextEncoder();
    for (const line of ics.split("\r\n")) expect(encoder.encode(line).length).toBeLessThanOrEqual(75);
  });
});
