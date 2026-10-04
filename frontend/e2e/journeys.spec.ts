import { expect, test } from "@playwright/test";
import { checkA11y, openContract } from "./helpers";

// Die acht Kernaufgaben aus dem UX-Plan (U0). Jede Aufgabe prueft auch die
// Barrierefreiheit der beteiligten Seite.

test("1 – Start: Arbeitsuebersicht laedt nach der Anmeldung", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("navigation").first()).toBeVisible();
  await checkA11y(page, info, "start");
});

test("2 – Vertrag finden: Suche in der Vertragsliste", async ({ page }, info) => {
  await page.goto("/register");
  await page.getByRole("searchbox", { name: /Suche/ }).fill("Reinigung");
  await expect(page.getByRole("link", { name: /^\d{6}$/ })).toHaveCount(1);
  await checkA11y(page, info, "vertragsliste");
});

test("3 – Vertrag oeffnen: Kopf zeigt Nummer, Status und Kosten", async ({ page }, info) => {
  await openContract(page, "Wartung CT Somatom");
  await expect(page.getByText(/In Arbeit|Gültig/).first()).toBeVisible();
  await checkA11y(page, info, "vertrag");
});

test("4 – Stammdaten bearbeiten und speichern", async ({ page }, info) => {
  await openContract(page, "Softwarepflege PACS");
  await page.getByRole("tab", { name: "Stammdaten" }).or(page.getByRole("button", { name: "Stammdaten", exact: true })).first().click();
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Stammdaten bearbeiten" }).click();
  const value = `INT-${Date.now() % 100000}`;
  await page.getByLabel("Interne Nummer").fill(value);
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText(value)).toBeVisible();
  await checkA11y(page, info, "stammdaten");
});

test("5 – Termin anlegen", async ({ page }, info) => {
  await openContract(page, "Reinigung OP-Bereich");
  await page.getByRole("tab", { name: /Fristen|Termine/ }).or(page.getByRole("button", { name: /^(Fristen|Termine)/ })).first().click();
  await page.getByRole("button", { name: "Termin hinzufügen" }).click();
  const form = page.getByRole("form", { name: /Termin/ });
  await form.getByLabel("Bezeichnung").fill("Angebot einholen");
  await form.getByLabel(/Fällig am/).fill(new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10));
  await form.getByRole("button", { name: /speichern|anlegen/i }).click();
  await expect(page.getByText("Angebot einholen").first()).toBeVisible();
  await checkA11y(page, info, "termine");

  // Aufraeumen ueber die Oberflaeche (prueft zugleich „Abbrechen“): offene Testtermine schliessen,
  // damit Folgelaeufe und Bildvergleich denselben Datenstand sehen.
  const open = page.locator("li.rg-deadline:not(.rg-inactive)").filter({ hasText: "Angebot einholen" });
  while (await open.count()) {
    const before = await open.count();
    await open.first().getByRole("button", { name: "Abbrechen" }).click();
    await expect(open).toHaveCount(before - 1);
  }
});

test("6 – Dokument ablegen (ohne KI-Analyse)", async ({ page }, info) => {
  await openContract(page, "Softwarepflege PACS");
  await page.getByRole("tab", { name: /Dokumente/ }).or(page.getByRole("button", { name: /^Dokumente/ })).first().click();
  await page.getByRole("tab", { name: /Anlagen/ }).or(page.getByRole("button", { name: /Anlagen/ })).first().click();
  const form = page.getByRole("form", { name: "Dokument hinzufügen" });
  await form.getByLabel("Dokumentart").selectOption({ index: 0 });
  const analyze = form.getByLabel(/Mit lokaler KI analysieren/);
  if (await analyze.isEnabled()) await analyze.uncheck();
  await form.getByLabel(/Dateien/).setInputFiles({ name: "laufzettel.pdf", mimeType: "application/pdf", buffer: Buffer.from(MINI_PDF) });
  await form.getByRole("button", { name: /hochladen|hinzufügen/i }).click();
  await expect(page.getByRole("list", { name: "Ergebnis des Uploads" })).toContainText("laufzettel.pdf");
  await checkA11y(page, info, "dokumente");
});

test("7 – Inhaltssuche liefert eine Antwort", async ({ page }, info) => {
  await page.goto("/suche");
  await page.getByLabel("Suchbegriff").fill("Wartung");
  await page.getByRole("button", { name: "Suchen", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Treffer|gefunden/ })).toBeVisible();
  await checkA11y(page, info, "suche");
});

test("8 – Vertragsliste als Excel exportieren", async ({ page }) => {
  await page.goto("/register");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /Excel exportieren/ }).click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
});

const MINI_PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 20 100 Td (Laufzettel Test) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF`;
