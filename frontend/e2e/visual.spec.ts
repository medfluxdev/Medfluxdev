import { expect, test } from "@playwright/test";

// Bildvergleich der Hauptseiten (Desktop 1440 px und Telefon). Dynamische
// Inhalte (Datum, Zeitstempel) werden maskiert.
const PAGES: [string, string][] = [
  ["start", "/"],
  ["vertragsliste", "/register"],
  ["termine", "/termine"],
  ["verlaengerungen", "/verlaengerungen"],
  ["suche", "/suche"],
  ["analysen", "/analysen"],
  ["einstellungen", "/settings"],
  ["rollen", "/settings/roles"],
];

for (const [name, path] of PAGES) {
  test(`Ansicht ${name}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot(`${name}.png`, {
      fullPage: true,
      mask: [page.locator("time"), page.getByText(/Stand \d{2}\.\d{2}\.\d{4}|Datenstand/)],
    });
  });
}
