import { expect, test } from "@playwright/test";
import { checkA11y } from "./helpers";

// U6: jede Seite der Navigation ohne schwere axe-Verstoesse, hell und dunkel.
const PAGES = [
  "/", "/postfach", "/register", "/partners", "/equipment", "/termine", "/verlaengerungen", "/work-queue",
  "/import", "/review", "/nachweise", "/archiv", "/analysen", "/audit", "/admin", "/suche", "/contracts/new",
  "/settings", "/profile", "/settings/users", "/settings/organization", "/settings/catalogs", "/settings/roles",
  "/developer", "/developer/components",
];

for (const theme of ["light", "dark"] as const) {
  test.describe(`Barrierefreiheit (${theme === "light" ? "hell" : "dunkel"})`, () => {
    test.use({ colorScheme: theme });
    for (const path of PAGES) {
      test(`${path}`, async ({ page }, info) => {
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
  for (const path of ["/", "/register", "/settings/catalogs"]) {
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
