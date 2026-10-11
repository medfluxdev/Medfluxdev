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
  await page.getByRole("button", { name: "Vertrag & Partner bearbeiten" }).click();
  const value = `INT-${Date.now() % 100000}`;
  await page.getByLabel("Vertragsgegenstand").fill(value);
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

test("13 – Direkt zur Stelle: Links in andere Reiter öffnen Abschnitt und Feld", async ({ page }) => {
  await openContract(page, "Softwarepflege PACS");
  const base = page.url().split("?")[0];
  await page.goto(`${base}?tab=finance&abschnitt=entries`);
  await expect(page.getByRole("form", { name: "Finanzeintrag anlegen" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Finanzeinträge" })).toBeInViewport();
  await page.goto(`${base}?tab=register&feld=term_start_date`);
  await expect(page.getByRole("button", { name: "Speichern", exact: true })).toBeVisible();
  await expect(page.locator(":focus")).toHaveAttribute("id", /^rg-term_(start_date|model)$/);
  await page.getByRole("button", { name: "Abbrechen" }).click();
});

test("14 – Direkt zur Stelle: Strg+K kennt, was dem offenen Vertrag fehlt", async ({ page }) => {
  // Ein bewusst unvollständiger Vertrag (nur Kurzbeschreibung) über die API derselben Anmeldung.
  await page.goto("/register");
  const created = await page.request.post(`${process.env.E2E_API_URL}/api/contracts?organization_slug=${process.env.E2E_ORG_SLUG}`, {
    headers: { Origin: process.env.E2E_BASE_URL ?? "" },
    data: { values: { short_description: `E2E Lücken ${Date.now() % 100000}` } },
  });
  expect(created.ok()).toBeTruthy();
  const { contract_id: contractId } = await created.json();
  await page.goto(`/contracts/${contractId}`);
  await page.getByRole("button", { name: /Was fehlt · / }).click();
  const gaps = page.getByRole("group", { name: "Was fehlt noch?" });
  await expect(gaps).toBeVisible();
  const first = (await gaps.getByRole("link").first().getAttribute("href"))!;
  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", { name: "Befehle und Suche" });
  await expect(palette.getByText("Dieser Vertrag")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect.poll(() => page.url()).toContain(first.split("?")[1]);
  await expect(page.locator(":focus")).toHaveAttribute("id", /^rg-/);
  // Aufräumen: archivieren, damit Liste und Bildreferenzen beim nächsten Lauf gleich bleiben.
  await page.getByRole("button", { name: "Abbrechen" }).click();
  const archived = await page.request.post(`${process.env.E2E_API_URL}/api/contracts/${contractId}/archive?organization_slug=${process.env.E2E_ORG_SLUG}`, {
    headers: { Origin: process.env.E2E_BASE_URL ?? "" }, data: {},
  });
  expect(archived.ok()).toBeTruthy();
});

test("15 – Erneut aus dem Dokument erfassen: fehlende Angaben suchen, vergleichen, übernehmen", async ({ page }, info) => {
  // Die lokale KI läuft in der Testumgebung nicht: die Schnittstelle der erneuten Erfassung wird im Browser
  // beantwortet (Ablauf, Vergleich und Barrierefreiheit der echten Seite werden geprüft; Backend: pytest).
  const origin = process.env.E2E_BASE_URL ?? "";
  const cors = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET,POST" };
  const missing = [{ key: "dates.start_date", label: "Vertragsbeginn" }];
  const run = { id: "run-e2e", mode: "missing_fields", fields: missing, page_hint: [], reread_document: false, model_id: null, applied_keys: [], requested_by_name: "E2E", message: null, queue_position: 0, created_at: null, started_at: null, finished_at: null, stale: false };
  const rows = [
    { key: "dates.start_date", label: "Vertragsbeginn", group: "new", current: null, proposed: "01.01.2025", evidence: [{ page: 1, quote: "Beginn 01.01.2025" }], register_keys: ["term_start_date"], preselected: true },
    { key: "identity.contract_title", label: "Vertragstitel", group: "missing_again", current: "Softwarepflege PACS", proposed: null, evidence: [], register_keys: [], preselected: false },
  ];
  let state: Record<string, unknown> = { can_start: true, blocked_reason: null, missing, field_search: { term_start_date: missing }, reread_suggested: false, run: null, rows: [] };
  let started: Record<string, unknown> | null = null;
  let applied: string[] | null = null;
  await page.route(/\/api\/contracts\/[^/]+\/reextraction/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const json = (body: unknown, status = 200) => route.fulfill({ status, headers: cors, contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname.endsWith("/models")) return json({ provider_id: "ollama", current_model: "qwen3-vl:8b", models: [{ model_id: "qwen3-vl:8b", label: "qwen3-vl:8b", parameter_size: "8B", vision: true, current: true }] });
    if (url.pathname.endsWith("/apply")) {
      applied = (request.postDataJSON() as { keys: string[] }).keys;
      state = { ...state, missing: [], run: { ...run, status: "applied", applied_keys: applied, summary: { new: 1 } }, rows: [] };
      return json({ applied: applied.length, keys: applied, message: `${applied.length} Angabe(n) übernommen.` });
    }
    if (request.method() === "POST") {
      started = request.postDataJSON() as Record<string, unknown>;
      // Nächste Abfrage: Ergebnis liegt vor.
      state = { ...state, run: { ...run, status: "ready", summary: { new: 1, missing_again: 1 } }, rows };
      return json({ ...run, status: "queued", summary: {} }, 202);
    }
    return json(state);
  });

  await openContract(page, "Softwarepflege PACS");
  // Einstieg „Was fehlt noch?“ → Dialog mit den fehlenden Angaben.
  const gapsButton = page.getByRole("button", { name: /Was fehlt · / });
  if (await gapsButton.isVisible().catch(() => false)) await gapsButton.click();
  const search = page.getByRole("link", { name: "Fehlende Angaben im Dokument suchen" });
  if (await search.isVisible().catch(() => false)) {
    await search.click();
  } else {
    await page.goto(`${page.url().split("?")[0]}?tab=documents&subtab=document&abschnitt=reextraction&suchen=fehlende`);
  }
  const dialog = page.getByRole("dialog", { name: "Erneut aus dem Dokument erfassen" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("checkbox", { name: "Vertragsbeginn" })).toBeChecked();
  await dialog.getByRole("textbox", { name: "Wo steht es? (optional)" }).fill("1");
  await checkA11y(page, info, "erneut-erfassen-dialog");
  await dialog.getByRole("button", { name: "Auswertung starten" }).click();
  await expect(dialog).toBeHidden();
  expect(started).toMatchObject({ mode: "missing_fields", fields: ["dates.start_date"], page_hint: [1] });

  // Ergebnis: Kopfhinweis und Vergleich; Neues mit Fundstelle ist vorausgewählt, Bisheriges bleibt.
  await expect(page.getByText("Erneute Erfassung abgeschlossen: 1 Angabe zum Prüfen.")).toBeVisible();
  const section = page.getByRole("region", { name: "Erneut aus dem Dokument erfassen" });
  await expect(section.getByRole("checkbox", { name: "Vertragsbeginn übernehmen" })).toBeChecked();
  await expect(section.getByText("Nicht erneut gefunden – der bisherige Wert bleibt (1)")).toBeVisible();
  await checkA11y(page, info, "erneut-erfassen-vergleich");
  await section.getByRole("button", { name: "Ausgewählte übernehmen (1)" }).click();
  await expect.poll(() => applied).toEqual(["dates.start_date"]);
  await expect(section.getByText(/Zuletzt übernommen: 1 Angabe/)).toBeVisible();
});

test("16 – Angabe aus dem Text übernehmen: Stelle markieren, Vorschau, speichern", async ({ page }, info) => {
  // Eigener Vertrag mit echtem PDF-Anhang über die API derselben Anmeldung.
  const api = process.env.E2E_API_URL;
  const org = process.env.E2E_ORG_SLUG;
  const origin = process.env.E2E_BASE_URL ?? "";
  await page.goto("/register");
  const created = await page.request.post(`${api}/api/contracts?organization_slug=${org}`, {
    headers: { Origin: origin }, data: { values: { short_description: `E2E Fundstelle ${Date.now() % 100000}` } },
  });
  expect(created.ok()).toBeTruthy();
  const { contract_id: contractId } = await created.json();
  const listing = await (await page.request.get(`${api}/api/contracts/${contractId}/documents?organization_slug=${org}`)).json();
  const uploaded = await page.request.post(`${api}/api/contracts/${contractId}/documents?organization_slug=${org}`, {
    headers: { Origin: origin },
    multipart: { files: { name: "vertrag.pdf", mimeType: "application/pdf", buffer: Buffer.from(MINI_PDF) }, attachment_type: listing.attachment_types[0], analyze: "false" },
  });
  expect(uploaded.ok()).toBeTruthy();

  // Ohne KI-Analyse gibt es in der Testumgebung keinen gelesenen Seitentext: Text und Prüfung werden im
  // Browser beantwortet (Prüfung, dass die Stelle auf der Seite steht, und das Lesen: pytest).
  const cors = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET,POST" };
  const text = "§ 3 Laufzeit\nDer Vertrag beginnt am 01.01.2025 und läuft drei Jahre.";
  const saved: Record<string, unknown>[] = [];
  await page.route(/\/api\/contracts\/[^/]+\/(documents\/[^/]+\/pages\/\d+\/text|register\/from-document)/, async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const json = (body: unknown) => route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(body) });
    if (request.url().includes("/pages/")) return json({ page: 1, pages: [1], text, fields: [{ key: "term_start_date", label: "Vertragsbeginn" }, { key: "initial_term", label: "Laufzeit" }] });
    const body = request.postDataJSON() as Record<string, unknown>;
    if (body.dry_run) return json({ preview: "01.01.2025", page: 1, quote: body.quote });
    saved.push(body);
    return json({});
  });

  await page.goto(`/contracts/${contractId}?tab=documents&subtab=document`);
  await page.getByRole("button", { name: "Angabe aus dem Text übernehmen" }).click();
  const region = page.getByRole("region", { name: "Text der Seite 1, so wie MedFlux ihn gelesen hat" });
  await expect(region).toContainText("beginnt am 01.01.2025");
  // Stelle mit der Maus markieren (Auswahl im Text, dann loslassen).
  await region.evaluate((element, wanted) => {
    const node = element.firstChild!;
    const start = (node.textContent ?? "").indexOf(wanted);
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, start + wanted.length);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  }, "beginnt am 01.01.2025");
  await expect(page.getByRole("textbox", { name: "Markierte Stelle (wörtlich)" })).toHaveValue("beginnt am 01.01.2025");
  await page.getByRole("combobox", { name: "Übernehmen als" }).selectOption("term_start_date");
  await expect(page.getByText("Wird gespeichert als: 01.01.2025")).toBeVisible();
  await checkA11y(page, info, "angabe-aus-text");
  await page.getByRole("button", { name: "Übernehmen", exact: true }).click();
  await expect.poll(() => saved.length).toBe(1);
  expect(saved[0]).toMatchObject({ field_key: "term_start_date", page: 1, quote: "beginnt am 01.01.2025" });

  const archived = await page.request.post(`${api}/api/contracts/${contractId}/archive?organization_slug=${org}`, { headers: { Origin: origin }, data: {} });
  expect(archived.ok()).toBeTruthy();
});

