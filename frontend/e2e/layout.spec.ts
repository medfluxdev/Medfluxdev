import { expect, test } from "@playwright/test";

// U9: keine waagerechte Seitenverschiebung – breite Tabellen scrollen in ihrem eigenen Rahmen.
const PAGES = [
  "/", "/postfach", "/register", "/partners", "/equipment", "/termine", "/verlaengerungen", "/work-queue",
  "/import", "/review", "/nachweise", "/archiv", "/analysen", "/audit", "/admin", "/suche", "/contracts/new",
  "/settings", "/profile", "/settings/users", "/settings/organization", "/settings/catalogs", "/settings/roles",
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
