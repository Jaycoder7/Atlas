import { expect, test } from "@playwright/test";
test("exposes all Atlas workspaces", async ({ page }) => {
  await page.goto("/dashboard");
  for (const name of ["Timeline", "Dependencies", "Hardware", "Requirements", "Validation", "Risks", "Changes", "Scenario"]) {
    await expect(page.getByRole("link", { name })).toBeVisible();
  }
});

test("runs the primary failure and scenario workflows", async ({ page }) => {
  await page.goto("/validation");
  await page.getByRole("button", { name: "Run Rev C thermal failure" }).click();
  await expect(page.getByText(/Thermal failure ingested/)).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.getByText("Validation", { exact: true })).toBeVisible();
  await expect(page.getByText("blocked", { exact: true }).first()).toBeVisible();

  await page.goto("/scenario");
  await page.getByRole("button", { name: "Evaluate scenario" }).click();
  await expect(page.getByText("+5 days", { exact: true }).first()).toBeVisible();
});
