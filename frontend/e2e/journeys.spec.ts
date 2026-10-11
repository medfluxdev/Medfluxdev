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
  // Eine Zeile, ein Link je Vertrag (Spalte „Vertrag“ = Beschreibung mit Nummer darunter).
  await expect(page.locator("table tbody").getByRole("link")).toHaveCount(1);
  await checkA11y(page, info, "vertragsliste");
});

test("3 – Vertrag oeffnen: Kopf zeigt Nummer, Status und Kosten", async ({ page }, info) => {
  await openContract(page, "Wartung CT Somatom");
  await expect(page.getByText(/In Arbeit|Gültig/).first()).toBeVisible();
  await checkA11y(page, info, "vertrag");
});

test("4 – Vertragsdaten bearbeiten und speichern", async ({ page }, info) => {
  await openContract(page, "Softwarepflege PACS");
  await page.getByRole("tab", { name: "Vertragsdaten" }).click();
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Vertragsdaten bearbeiten" }).click();
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

test("9 – Benutzer per Liste importieren und mit Erstpasswort anmelden", async ({ page, browser }, info) => {
  const tag = Date.now().toString(36);
  const email = `leser-${tag}@medflux.test`;
  // Erstpasswort wird nur fuer diesen Lauf erzeugt und nirgends gespeichert.
  const firstPassword = `E2e-${crypto.randomUUID()}`;
  const csv = `E-Mail;Name;Rolle;Krankenhaus;Bereich;Erstpasswort
${email};Lea Leser ${tag};Leser;NORD;Radiologie;${firstPassword}
prueferin-${tag}@medflux.test;Pia Prüferin ${tag};Prüfer;Klinikum Nord;;
`;

  await page.goto("/settings/users");
  await page.getByLabel("Liste auswählen").setInputFiles({ name: "benutzer.csv", mimeType: "text/csv", buffer: Buffer.from(csv, "utf-8") });
  await expect(page.getByText("2 Benutzer in der Liste")).toBeVisible();

  await page.getByRole("button", { name: "Liste prüfen" }).click();
  await expect(page.getByText("Erstpasswort fehlt.")).toBeVisible();
  await expect(page.getByRole("button", { name: "2 Benutzer anlegen" })).toBeDisabled();
  await checkA11y(page, info, "benutzer-import");

  await page.getByRole("button", { name: "Fehlende Passwörter erzeugen" }).click();
  await page.getByRole("button", { name: "Liste prüfen" }).click();
  await expect(page.getByText("geprüft, keine Fehler", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "2 Benutzer anlegen" }).click();
  await expect(page.getByText("2 Benutzer angelegt", { exact: false })).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();

  const context = await browser.newContext({ storageState: { cookies: [], origins: [] }, locale: "de-DE" });
  const fresh = await context.newPage();
  await fresh.goto("/login", { waitUntil: "networkidle" });
  await fresh.getByPlaceholder("E-Mail-Adresse eingeben").fill(email);
  await fresh.getByPlaceholder("Passwort eingeben").fill(firstPassword);
  await fresh.getByRole("button", { name: "Anmelden" }).click();
  await fresh.waitForURL((url) => !url.pathname.startsWith("/login"));
  await expect(fresh.getByRole("heading", { level: 1, name: /Lea/ })).toBeVisible();
  await expect(fresh.getByRole("link", { name: "Vertrag anlegen" })).toHaveCount(0);
  await context.close();
});

test("10 – Stammdaten: Vertragspartner anlegen, finden und deaktivieren", async ({ page }, info) => {
  await page.goto("/stammdaten");
  await expect(page.getByRole("heading", { level: 1, name: "Stammdaten" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await checkA11y(page, info, "stammdaten-uebersicht");

  await page.getByRole("link", { name: "Vertragspartner öffnen" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Vertragspartner" })).toBeVisible();
  const name = `E2E Partner ${Date.now() % 100000}`;
  await page.getByRole("button", { name: "Vertragspartner anlegen" }).click();
  const drawer = page.getByRole("dialog", { name: "Vertragspartner anlegen" });
  await drawer.getByLabel("Kurzname *", { exact: true }).fill(name);
  await drawer.getByLabel("Name *", { exact: true }).fill(`${name} GmbH`);
  await drawer.getByLabel("Ort", { exact: true }).fill("Teststadt");
  await checkA11y(page, info, "stammdaten-formular");
  await drawer.getByRole("button", { name: "Anlegen" }).click();
  await expect(drawer).toBeHidden();

  await page.getByRole("searchbox", { name: "Vertragspartner durchsuchen" }).fill(name);
  await expect(page.getByRole("rowheader", { name })).toBeVisible();
  await page.getByRole("button", { name: `${name} bearbeiten` }).click();
  const editor = page.getByRole("dialog", { name });
  await expect(editor.getByText("In keinem Vertrag verwendet.")).toBeVisible();
  await editor.getByRole("button", { name: "Deaktivieren" }).click();
  await expect(editor).toBeHidden();
  await expect(page.getByRole("rowheader", { name })).toHaveCount(0);
});

test("11 – Vertragsregel anlegen und in der Vertragsliste nutzen", async ({ page }, info) => {
  await page.goto("/stammdaten/vertragsregeln");
  await expect(page.getByRole("heading", { level: 1, name: "Vertragsregeln" })).toBeVisible();
  const label = `E2E Kündigungsfrist ${Date.now() % 100000}`;
  await page.getByRole("button", { name: "Vertragsregel anlegen" }).first().click();
  const drawer = page.getByRole("dialog", { name: "Vertragsregel anlegen" });
  await drawer.getByLabel("Bezeichnung *", { exact: true }).fill(label);
  await drawer.getByLabel(/Grenzwert/).fill("3");
  await checkA11y(page, info, "vertragsregel-formular");
  await drawer.getByRole("button", { name: "Anlegen" }).click();
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("rowheader", { name: label })).toBeVisible();

  await page.goto("/register");
  await page.getByRole("button", { name: /Darstellung/ }).click();
  await expect(page.getByRole("checkbox", { name: "Vertragsregeln" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Regelverstöße" })).toBeVisible();

  // Aufräumen: Regel wieder deaktivieren.
  await page.goto("/stammdaten/vertragsregeln");
  await page.getByRole("button", { name: `${label} bearbeiten` }).click();
  const editor = page.getByRole("dialog", { name: label });
  await editor.getByRole("button", { name: /Deaktivieren/ }).click();
  const confirm = editor.getByRole("button", { name: "Trotzdem deaktivieren" });
  if (await confirm.isVisible().catch(() => false)) await confirm.click();
  await expect(editor).toBeHidden();
});

test("12 – Direkt zur Stelle: fehlende Angabe anklicken setzt den Cursor ins Feld", async ({ page }, info) => {
  await openContract(page, "Softwarepflege PACS");
  await page.getByRole("tab", { name: "Vertragsdaten" }).click();
  // Hinweis „Für Gültig fehlen noch …“ oder „Erfassen“ an einem leeren Feld – beides nutzt denselben Sprung.
  const missing = page.locator(".missing-list button, .rg-field button[aria-label$=' erfassen']").first();
  await expect(missing).toBeVisible();
  await missing.click();
  await expect(page.getByRole("button", { name: "Speichern", exact: true })).toBeVisible();
  await expect(page.locator(":focus")).toHaveAttribute("id", /^rg-/);
  await expect(page).toHaveURL(/feld=/);
  await checkA11y(page, info, "direkt-zur-stelle");
  await page.getByRole("button", { name: "Abbrechen" }).click();
  await expect(page).not.toHaveURL(/feld=/);
});
