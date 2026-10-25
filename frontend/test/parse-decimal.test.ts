import { describe, expect, it } from "vitest";
import { parseDecimalInput } from "@/lib/format";

describe("parseDecimalInput", () => {
  it("liest Beträge aus dem Dokument und freie deutsche Eingaben", () => {
    expect(parseDecimalInput("2 060,00 €")).toBe("2060.00");
    expect(parseDecimalInput("2 060,00 €")).toBe("2060.00");
    expect(parseDecimalInput("2.060,00")).toBe("2060.00");
    expect(parseDecimalInput("2060.5")).toBe("2060.5");
    expect(parseDecimalInput("19 %")).toBe("19");
  });

  it("lehnt Unlesbares ab", () => {
    expect(parseDecimalInput("")).toBeNull();
    expect(parseDecimalInput("abc")).toBeNull();
    expect(parseDecimalInput("1,2,3")).toBeNull();
  });
});
