import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

// Barrierefreiheit: Ergebnisse werden immer angehaengt; schwere Verstoesse
// (critical/serious) lassen den Test fehlschlagen, ausser im Baseline-Modus.
export async function checkA11y(page: Page, testInfo: TestInfo, name: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  await testInfo.attach(`axe-${name}.json`, { body: JSON.stringify(results.violations, null, 2), contentType: "application/json" });
  const severe = results.violations.filter((item) => item.impact === "critical" || item.impact === "serious");
  if (process.env.E2E_AXE_BASELINE === "1") return severe;
  expect(severe.map((item) => `${item.id}: ${item.help} (${item.nodes.length})`)).toEqual([]);
  return severe;
}

export async function openContract(page: Page, title: string) {
  await page.goto("/register");
  await page.getByRole("searchbox", { name: /Suche/ }).fill(title);
  const links = page.getByRole("link", { name: /^\d{6}$/ });
  await expect(links).toHaveCount(1);
  await links.click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
}
