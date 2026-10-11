import { expect, test } from "@playwright/test";

// U9: keine waagerechte Seitenverschiebung – breite Tabellen scrollen in ihrem eigenen Rahmen.
const PAGES = [
  "/", "/postfach", "/register", "/equipment", "/fristen", "/fristen?ansicht=entscheidungen", "/fristen?ansicht=aufgaben",
  "/import", "/register?ansicht=review", "/register?ansicht=archive", "/analysen", "/audit", "/admin", "/suche", "/contracts/new",
  "/settings", "/profile", "/settings/users", "/stammdaten", "/stammdaten/vertragspartner", "/stammdaten/abteilungen", "/stammdaten/kostenstellen", "/stammdaten/vertragstypen", "/stammdaten/vertragsregeln", "/stammdaten/auswahllisten/storage_location", "/sicherheit", "/settings/nummernkreis", "/settings/roles",
];

for (const [name, width, height] of [["Desktop", 1440, 900], ["Tablet", 900, 1100], ["Telefon", 390, 844]] as const) {
  test.describe(`Layout ${name} (${width}px)`, () => {
    test.use({ viewport: { width, height } });
    for (const path of PAGES) {
      test(path, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(() => {
          const vw = document.documentElement.clientWidth;
          if (document.documentElement.scrollWidth <= vw + 1) return [];
          return Array.from(document.querySelectorAll("main *"))
            .filter((el) => {
              const right = el.getBoundingClientRect().right;
              const parent = el.parentElement?.getBoundingClientRect().right ?? 0;
              return right > vw + 1 && parent <= vw + 1;
            })
            .slice(0, 5)
            .map((el) => `${el.tagName.toLowerCase()}.${String((el as HTMLElement).className).split(" ").join(".")}`);
        });
        expect(overflow).toEqual([]);
      });
    }
  });
}

// Vertragsliste: Tabellenkopf und erste Zeile ohne Scrollen sichtbar (Suche, Schnellfilter und Ergebniszeile darüber).
for (const [width, height] of [[1366, 768], [1920, 1080]] as const) {
  test(`Vertragsliste ${width}×${height}: erste Zeile ohne Scrollen`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto("/register");
    const firstRow = page.locator("table tbody tr").first();
    await expect(firstRow).toBeVisible();
    const box = await firstRow.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(height);
  });
}
