import { expect, test } from "@playwright/test";

// Bildvergleich der Hauptseiten (Desktop 1440 px und Telefon). Dynamische
// Inhalte (Datum, Begruessung nach Uhrzeit, verbleibende Tage) werden maskiert.
const PAGES: [string, string][] = [
  ["start", "/"],
  ["vertragsliste", "/register"],
  ["fristen", "/fristen"],
  ["entscheidungen", "/fristen?ansicht=entscheidungen"],
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
      mask: [
        page.locator("time"),
        page.getByText(/Stand \d{2}\.\d{2}\.\d{4}|Datenstand/),
        page.locator(".my-day-head, #my-deadlines, .my-day-date, .badge"),
        page.getByText(/^\d+ Tage$|^in \d+ Tagen$|^vor \d+ Tagen?$/),
      ],
    });
  });
}
