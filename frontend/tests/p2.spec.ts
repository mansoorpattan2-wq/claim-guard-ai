import { test, expect } from "@playwright/test";
test.beforeEach(async ({ request }) => {
  const s = await request.post("/api/session", {
    data: { role: "Claims Executive" },
  });
  const { token } = await s.json();
  const reset = await request.post("/api/demo/reset-all", {
    headers: { Authorization: "Bearer " + token },
    data: {},
  });
  expect(reset.ok()).toBe(true);
});
test("investigation graph, signal evidence and linked passport", async ({
  page,
}) => {
  await page.goto("/investigations");
  await expect(
    page.getByRole("heading", { name: "Connected evidence network" }),
  ).toBeVisible();
  await expect(page.locator(".investigation-notice")).toContainText(
    "INVESTIGATION LEAD",
  );
  await expect(page.locator(".graph-node")).toHaveCount(11);
  await page
    .getByRole("button", {
      name: "Document Shared diagnostic source",
      exact: true,
    })
    .click();
  await expect(page.locator(".graph-detail")).toContainText("fingerprint");
  await page.getByRole("button", { name: "Zoom in graph" }).click();
  await page.getByRole("button", { name: "Reset graph view" }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/investigation-graph-desktop.png",
    fullPage: true,
  });
  await page
    .locator(".graph-detail")
    .getByRole("link", { name: "Open Claim Passport" })
    .click();
  await expect(
    page.getByRole("heading", { name: "CG048", exact: true }),
  ).toBeVisible();
});
test("FHIR sandbox import, adapter test and passport", async ({ page }) => {
  await page.goto("/integrations");
  await expect(
    page.getByRole("heading", { name: "NHCX", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".integration-card").filter({ hasText: "NHCX" }),
  ).toContainText("Not Connected");
  await page
    .locator(".integration-card")
    .filter({ hasText: "FHIR R4" })
    .getByRole("button", { name: "Test local adapter" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "No external connection tested",
  );
  await page
    .getByRole("button", { name: "Load synthetic FHIR Bundle" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "FHIR Bundle JSON" }),
  ).toHaveValue(/claimguard-synthetic-r4-demo/);
  await page
    .getByRole("button", { name: "Import & analyse FHIR Bundle" })
    .click();
  await expect(page.locator(".fhir-result")).toContainText("SYN-FHIR-101");
  await expect(
    page.getByRole("link", { name: "Open imported Claim Passport" }),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/fhir-integrations-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Open imported Claim Passport" })
    .click();
  await expect(page.locator(".passport-score>strong")).toHaveText("98%");
  await page.getByRole("button", { name: "Reset complete demo" }).click();
  await page.goto("/claims/CG021");
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
});
test("responsive P1/P2 workspaces and keyboard graph focus", async ({
  page,
}) => {
  await page.goto("/investigations");
  const node = page.getByRole("button", { name: "Claim CG048", exact: true });
  await node.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".graph-detail")).toContainText("CG048");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of [
    "/claims/new",
    "/review",
    "/knowledge",
    "/investigations",
    "/integrations",
  ]) {
    await page.goto(route);
    await expect(
      page.getByRole("combobox", { name: "Demo role" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.goto("/investigations");
  await expect(
    page.getByRole("heading", { name: "Linked claims" }),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/investigation-mobile.png",
    fullPage: true,
  });
});
