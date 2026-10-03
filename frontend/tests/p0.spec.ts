import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const session = await request.post("/api/session", {
    data: { role: "Claims Executive" },
  });
  const { token } = await session.json();
  const reset = await request.post("/api/demo/reset", {
    headers: { Authorization: "Bearer " + token },
    data: {},
  });
  expect(reset.ok()).toBe(true);
});

test("CG021 resolution, passport persistence, audit and export", async ({
  page,
}) => {
  await page.goto("/claims/CG021");
  await expect(
    page.getByRole("heading", { name: "CG021", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  await page.getByRole("link", { name: "View evidence" }).click();
  await expect(page.locator("mark")).toContainText("signed operative report");
  await expect(
    page.getByText("SYNTHETIC POLICY — DEMONSTRATION ONLY", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "docs/evidence-viewer-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Back to CG021 passport" }).click();
  await page.getByRole("button", { name: "Resolve", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate request", exact: true })
    .click();
  await expect(page.locator(".request-text")).toContainText(
    "Do not create or alter clinical content",
  );
  await page
    .getByRole("button", { name: "Simulate request", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Simulate response", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Validate & update passport" }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Validate & update passport" })
    .click();
  await expect(page.locator(".passport-score>strong")).toHaveText("94%");
  await expect(page.locator(".claim-title .badge")).toContainText("Ready");
  await page.reload();
  await expect(page.locator(".passport-score>strong")).toHaveText("94%");
  await page.getByRole("tab", { name: "Audit", exact: true }).click();
  await expect(
    page.getByText("Resolution completed", { exact: true }).first(),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export passport" }).click();
  expect((await download).suggestedFilename()).toBe("CG021-passport.json");
  await page.getByRole("button", { name: "Reset demo" }).click();
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  await page.getByRole("tab", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "docs/claim-passport-desktop.png",
    fullPage: true,
  });
});

test("clean and investigation stories, queue filtering and role permissions", async ({
  page,
}) => {
  await page.goto("/claims/CG001");
  await expect(page.locator(".passport-score>strong")).toHaveText("98%");
  await expect(
    page.getByText("No open findings", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Evidence Passport", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Structured evidence passport" }),
  ).toBeVisible();
  await page.goto("/claims/CG048");
  await expect(
    page.getByRole("heading", { name: "Related synthetic claims" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "CG045", exact: true }),
  ).toBeVisible();
  await page.goto("/claims");
  await page.getByRole("textbox", { name: "Search claims" }).fill("CG021");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("link", { name: "CG021", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Demo role" })
    .selectOption("Auditor");
  await expect(
    page.getByRole("button", { name: "Resolve", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Generate request", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("combobox", { name: "Demo role" })
    .selectOption("Claims Executive");
  await expect(
    page.getByRole("button", { name: "Resolve", exact: true }),
  ).toBeEnabled();
  await page.goto("/dashboard");
  await expect(
    page.getByRole("heading", { name: "Claim readiness, at a glance" }),
  ).toBeVisible();
  await page.screenshot({ path: "docs/dashboard-desktop.png", fullPage: true });
});

test("mobile passport and responsive navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/claims/CG021");
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Claim readiness, at a glance" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "docs/dashboard-mobile.png", fullPage: true });
});
