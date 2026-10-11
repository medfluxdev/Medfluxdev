import { expect, test } from "@playwright/test";
import { checkA11y } from "./helpers";

// U6: jede Seite der Navigation ohne schwere axe-Verstoesse, hell und dunkel.
const PAGES = [
  "/", "/postfach", "/register", "/stammdaten/geraetearten", "/fristen", "/fristen?ansicht=termine", "/fristen?ansicht=entscheidungen",
  "/import", "/register?ansicht=review", "/register?ansicht=archive", "/analysen", "/audit", "/admin", "/suche", "/contracts/new",
  "/settings", "/profile", "/settings/users", "/stammdaten", "/stammdaten/vertragspartner", "/stammdaten/abteilungen", "/stammdaten/kostenstellen", "/stammdaten/vertragstypen", "/stammdaten/vertragsregeln", "/stammdaten/auswahllisten/storage_location", "/sicherheit", "/settings/nummernkreis", "/settings/roles",
  "/developer", "/developer?tab=bausteine",
];

for (const theme of ["light", "dark"] as const) {
  test.describe(`Barrierefreiheit (${theme === "light" ? "hell" : "dunkel"})`, () => {
    test.use({ colorScheme: theme });
    for (const path of PAGES) {
      test(`${path}`, async ({ page }, info) => {
        // Standard ist hell; das dunkle Design wird wie im Kontomenue gewaehlt.
        await page.addInitScript((value) => window.localStorage.setItem("medflux.preferences", JSON.stringify({ theme: value })), theme);
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        await checkA11y(page, info, `${theme}${path.replaceAll("/", "_") || "_start"}`);
      });
    }
  });
}

test.describe("Windows-Kontrastmodus", () => {
  test.use({ forcedColors: "active" });
  for (const path of ["/", "/register", "/stammdaten/vertragspartner"]) {
    test(`${path} bleibt bedienbar`, async ({ page }, info) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      await checkA11y(page, info, `forced${path.replaceAll("/", "_")}`);
      const current = page.locator('[aria-current="page"]').first();
      if (await current.count()) await expect(current).toHaveCSS("text-decoration-line", "underline");
    });
  }
});
