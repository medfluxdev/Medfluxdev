import { test } from "@playwright/test";
import { openContract } from "./helpers";
test("shot", async ({ page }) => {
  await openContract(page, "Wartung CT Somatom");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: "test-results/u4-contract.png" });
  await page.getByRole("tab", { name: "Fristen & Entscheidung" }).click();
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: "test-results/u4-contract-fristen.png", fullPage: true });
});
