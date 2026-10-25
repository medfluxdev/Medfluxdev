import { beforeEach, describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, PREFERENCES_BOOTSTRAP, effectiveTextSize, stepTextSize } from "@/components/shell/preferences";

describe("Größe der Darstellung", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-text-size");
  });

  it("geht Stufe für Stufe und bleibt an den Enden stehen", () => {
    expect(stepTextSize("normal", -1)).toBe("small");
    expect(stepTextSize("small", -1)).toBe("xsmall");
    expect(stepTextSize("xsmall", -1)).toBe("xsmall");
    expect(stepTextSize("large", 1)).toBe("xlarge");
    expect(stepTextSize("xlarge", 1)).toBe("xlarge");
  });

  it("Listen und Tabellen können eine eigene Größe haben, Detailseiten behalten die Textgröße", () => {
    const prefs = { ...DEFAULT_PREFERENCES, textSize: "normal" as const, listTextSize: "small" as const };
    expect(effectiveTextSize(prefs, "/register")).toBe("small");
    expect(effectiveTextSize(prefs, "/fristen")).toBe("small");
    expect(effectiveTextSize(prefs, "/contracts/abc")).toBe("normal");
    expect(effectiveTextSize({ ...prefs, listTextSize: "same" }, "/register")).toBe("normal");
  });

  it("der Startskript setzt die Größe vor dem ersten Zeichnen (Liste vs. Detail)", () => {
    window.localStorage.setItem("medflux.preferences", JSON.stringify({ textSize: "large", listTextSize: "xsmall" }));
    window.history.pushState({}, "", "/register");
    new Function(PREFERENCES_BOOTSTRAP)();
    expect(document.documentElement.getAttribute("data-text-size")).toBe("xsmall");
    document.documentElement.removeAttribute("data-text-size");
    window.history.pushState({}, "", "/contracts/123");
    new Function(PREFERENCES_BOOTSTRAP)();
    expect(document.documentElement.getAttribute("data-text-size")).toBe("large");
  });
});
