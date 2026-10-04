import { chromium, type FullConfig } from "@playwright/test";
import { mkdirSync } from "node:fs";

// Meldet das Testkonto einmal an und speichert die Sitzung fuer alle Tests.
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL ?? "http://localhost:3077";
  const login = process.env.E2E_ADMIN_LOGIN;
  const password = process.env.E2E_ADMIN_PASSWORD;
  if (!login || !password) throw new Error("E2E_ADMIN_LOGIN/E2E_ADMIN_PASSWORD fehlen (e2e/.env.example).");
  mkdirSync("e2e/.auth", { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ locale: "de-DE" });
  await page.goto(`${baseURL}/login`);
  await page.getByPlaceholder("E-Mail-Adresse eingeben").fill(login);
  await page.getByPlaceholder("Passwort eingeben").fill(password);
  await page.getByRole("button", { name: "Anmelden" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 60_000 });
  await page.context().storageState({ path: "e2e/.auth/admin.json" });
  await browser.close();
}
