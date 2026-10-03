import { test, expect } from "@playwright/test";
const operative = `SYNTHETIC OPERATIVE REPORT — DEMONSTRATION ONLY
Beneficiary: Demo Alias 101
Hospital: Cedar Demo Hospital
Procedure: Laparoscopic appendectomy
Admission: 2026-10-01
Discharge: 2026-10-03
Service date: 2026-10-02
Amount: 78000
Signed by: Dr. Demo
`;
test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/session", {
    data: { role: "Claims Executive" },
  });
  const { token } = await response.json();
  const reset = await request.post("/api/demo/reset-all", {
    headers: { Authorization: "Bearer " + token },
    data: {},
  });
  expect(reset.ok()).toBe(true);
});
test("multi-file intake, classification, identity, execution and passport", async ({
  page,
}) => {
  await page.goto("/claims/new");
  await expect(
    page.getByRole("heading", { name: "Bring the evidence together" }),
  ).toBeVisible();
  await page.locator("input[type=file]").setInputFiles([
    {
      name: "operative-report.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(operative),
    },
    {
      name: "final-bill.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "SYNTHETIC FINAL BILL\nBeneficiary: Demo Alias 101\nAmount: 78000",
      ),
    },
  ]);
  await expect(
    page.getByRole("combobox", { name: "Classification operative-report.txt" }),
  ).toHaveValue("operative_report");
  await expect(
    page.getByRole("textbox", { name: "Intake patient" }),
  ).toHaveValue("Demo Alias 101");
  await page
    .getByRole("checkbox", {
      name: "I confirm these are synthetic claim details",
    })
    .check();
  await page
    .getByRole("button", { name: "Analyse Claim", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Analysis complete" }),
  ).toBeVisible();
  await expect(page.locator(".execution-progress .done")).toHaveCount(8);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/intake-analysis-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Open Claim Passport" }).click();
  await expect(page.locator(".passport-score>strong")).toHaveText("98%");
  await page.getByRole("tab", { name: "Agent Trace", exact: true }).click();
  await page.locator(".trace-step").first().locator("summary").first().click();
  await expect(
    page.locator(".trace-step").first().locator(".trace-metadata"),
  ).toContainText("Tools");
  await expect(
    page.getByText("SHA-256", { exact: false }).first(),
  ).toBeVisible();
});

test("review override, mandatory rationale and state update", async ({
  page,
}) => {
  await page.goto("/review");
  await page
    .getByRole("combobox", { name: "Demo role" })
    .selectOption("Medical Reviewer");
  await page.locator(".review-item").filter({ hasText: "CG030" }).click();
  await page.getByRole("button", { name: "Override", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Record disposition" }),
  ).toBeDisabled();
  await page
    .getByRole("textbox", { name: "Review reason" })
    .fill(
      "Synthetic source exception reviewed; preserve the original finding.",
    );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/review-workspace-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Record disposition" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Human disposition recorded" }),
  ).toContainText("CG030 is READY");
  await page.goto("/claims/CG030");
  await expect(page.locator(".claim-title .badge")).toContainText("Ready");
  await page.getByRole("tab", { name: "Human Decisions", exact: true }).click();
  await expect(
    page
      .getByText(
        "Synthetic source exception reviewed; preserve the original finding.",
        { exact: true },
      )
      .first(),
  ).toBeVisible();
});

test("knowledge query, ranked citations and unavailable-date state", async ({
  page,
}) => {
  await page.goto("/knowledge");
  await expect(
    page.getByRole("heading", { name: "Governed knowledge sources" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Test retrieval" }).click();
  await expect(page.locator(".grounded-answer")).toContainText(
    "includes anaesthesia",
  );
  await expect(page.locator(".citation-rank").first()).toContainText("PKG-6.1");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "docs/knowledge-desktop.png", fullPage: true });
  await page
    .getByRole("textbox", { name: "Applicable date" })
    .fill("2025-10-02");
  await page.getByRole("button", { name: "Test retrieval" }).click();
  await expect(page.locator(".grounded-answer")).toContainText(
    "INSUFFICIENT_EVIDENCE",
  );
});

test("printable evidence passport and standalone export", async ({ page }) => {
  await page.goto("/claims/CG021/passport");
  const frame = page.frameLocator("iframe");
  await expect(
    frame.getByRole("heading", {
      name: "Claim Readiness Passport",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    frame.getByRole("heading", { name: "Document provenance", exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download HTML" }).click();
  expect((await download).suggestedFilename()).toBe(
    "CG021-readiness-passport.html",
  );
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "docs/printable-passport-desktop.png",
    fullPage: true,
  });
});
