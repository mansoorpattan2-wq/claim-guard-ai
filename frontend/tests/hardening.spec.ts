import { test, expect } from "@playwright/test";
import fs from "node:fs";
test.beforeEach(async ({ request }) => {
  const session = await request.post("/api/session", {
    data: { role: "Claims Executive" },
  });
  const { token } = await session.json();
  expect(
    (
      await request.post("/api/demo/reset-all", {
        headers: { Authorization: "Bearer " + token },
      })
    ).ok(),
  ).toBe(true);
});

test("reset confirmation cancellation, active history isolation and repeated reset", async ({
  page,
}) => {
  await page.goto("/claims/CG021");
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  page.once("dialog", (d) => d.dismiss());
  await page.getByRole("button", { name: "Reset complete demo" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Presentation restored" }),
  ).toHaveCount(0);
  for (let i = 0; i < 2; i++) {
    page.once("dialog", (d) => d.accept());
    await page.getByRole("button", { name: "Reset complete demo" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Presentation restored" }),
    ).toBeVisible();
    await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  }
  await page.getByRole("tab", { name: "Human Decisions", exact: true }).click();
  await expect(
    page.getByText("No decisions recorded.", { exact: false }),
  ).toBeVisible();
});

test("API unavailable and failed retrieval recover without stale grounded answer", async ({
  page,
}) => {
  await page.route("**/api/claims", (r) => r.abort());
  await page.goto("/dashboard");
  await expect(page.locator('.error-banner[role="alert"]')).toContainText(
    "unavailable",
  );
  await page.unroute("**/api/claims");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Claim readiness, at a glance" }),
  ).toBeVisible();
  await page.goto("/knowledge");
  await page.getByRole("button", { name: "Test retrieval" }).click();
  await expect(page.locator(".grounded-answer")).toContainText("GROUNDED");
  await page.route("**/api/knowledge/retrieve", (r) =>
    r.fulfill({ status: 503, body: "Service unavailable" }),
  );
  await page.getByRole("button", { name: "Test retrieval" }).click();
  await expect(page.locator(".grounded-answer")).toHaveCount(0);
  await expect(page.locator('.error-banner[role="alert"]')).toContainText(
    "Retry",
  );
  await page.unroute("**/api/knowledge/retrieve");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".grounded-answer")).toContainText("GROUNDED");
});

test("resolution request failure, refresh/back navigation and duplicate click remain safe", async ({
  page,
}) => {
  await page.goto("/claims/CG021");
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  await page.route("**/api/resolutions/RT-CG021/request", (r) =>
    r.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page
    .getByRole("button", { name: "Generate request", exact: true })
    .click();
  await expect(page.locator('.error-banner[role="alert"]')).toBeVisible();
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  await page.unroute("**/api/resolutions/RT-CG021/request");
  await page
    .getByRole("button", { name: "Generate request", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Simulate request", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Simulate response", exact: true }),
  ).toBeEnabled();
  await page.getByRole("link", { name: "View evidence", exact: true }).click();
  await expect(page.locator("mark")).toBeVisible();
  await page.goBack();
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
  await page
    .getByRole("button", { name: "Simulate response", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Validate & update passport" }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Validate & update passport" })
    .evaluate((b: HTMLButtonElement) => {
      b.click();
      b.click();
    });
  await expect(page.locator(".passport-score>strong")).toHaveText("94%");
  await expect(page.locator(".readiness-transition")).toContainText("63%");
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "docs/hardening/cg021-resolved.png",
    fullPage: true,
  });
  await page.route("**/api/claims", (r) => r.abort());
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Reset complete demo" }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace temporarily unavailable" }),
  ).toBeVisible();
  await expect(page.locator(".passport-score>strong")).toHaveCount(0);
  await page.unroute("**/api/claims");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".passport-score>strong")).toHaveText("63%");
});

test("graph unavailable and malformed FHIR expose recovery and no false success", async ({
  page,
}) => {
  await page.route("**/api/investigations/graph", (r) =>
    r.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.goto("/investigations");
  await expect(page.locator('.error-banner[role="alert"]')).toBeVisible();
  await expect(page.locator(".graph-node")).toHaveCount(0);
  await page.unroute("**/api/investigations/graph");
  await page.getByRole("button", { name: "Retry graph" }).click();
  await expect(page.locator(".graph-node")).toHaveCount(11);
  await page.goto("/integrations");
  await page
    .getByRole("textbox", { name: "FHIR Bundle JSON" })
    .fill("{bad json");
  await page
    .getByRole("button", { name: "Import & analyse FHIR Bundle" })
    .click();
  await expect(page.locator('.error-banner[role="alert"]')).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open imported Claim Passport" }),
  ).toHaveCount(0);
});

test("malformed upload and intake refresh recover the persisted job", async ({
  page,
}) => {
  await page.goto("/claims/new");
  await page.locator("input[type=file]").setInputFiles({
    name: "invalid.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("not a PDF"),
  });
  await expect(page.locator('.error-banner[role="alert"]')).toContainText(
    "signature",
  );
  await page.locator("input[type=file]").setInputFiles({
    name: "operative-report.txt",
    mimeType: "text/plain",
    buffer: fs.readFileSync("backend/demo/operative-report.txt"),
  });
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
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Analysis complete" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open Claim Passport" }).click();
  await expect(page.locator(".passport-score>strong")).toHaveText("98%");
});

test("failed analysis offers retry and manual review without READY", async ({
  page,
}) => {
  await page.goto("/claims/new");
  await page.locator("input[type=file]").setInputFiles({
    name: "operative-report.txt",
    mimeType: "text/plain",
    buffer: fs.readFileSync("backend/demo/operative-report.txt"),
  });
  await expect(page.getByLabel("Intake patient")).toHaveValue("Demo Alias 101");
  await page.getByLabel("Intake admission").fill("2027-01-01");
  await page.getByLabel("Intake discharge").fill("2027-01-03");
  await page
    .getByRole("checkbox", {
      name: "I confirm these are synthetic claim details",
    })
    .check();
  await page
    .getByRole("button", { name: "Analyse Claim", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "A check needs attention" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry analysis" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Retry analysis" }).click();
  await expect(
    page.getByRole("heading", { name: "A check needs attention" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open human review passport" }).click();
  await expect(page.locator(".claim-title .badge")).toContainText(
    "Human review",
  );
  expect(
    Number(
      (await page.locator(".passport-score>strong").textContent())?.replace(
        "%",
        "",
      ),
    ),
  ).toBeLessThanOrEqual(49);
});

for (let run = 1; run <= 3; run++)
  test(`complete judge sequence reset rehearsal ${run}`, async ({
    page,
    request,
  }) => {
    const timings: Record<string, number> = {};
    const started = performance.now();
    async function measure(name: string, fn: () => Promise<void>) {
      const start = performance.now();
      await fn();
      timings[name] = Math.round(performance.now() - start);
    }
    await measure("dashboard_initial_load_ms", async () => {
      await page.goto("/dashboard");
      await expect(
        page.getByRole("heading", { name: "Claim readiness, at a glance" }),
      ).toBeVisible();
      await expect(page.locator(".metric").first()).toContainText("50");
    });
    await measure("claim_load_ms", async () => {
      await page.goto("/claims/CG001");
      await expect(page.locator(".passport-score>strong")).toHaveText("98%");
    });
    await page.getByRole("link", { name: "Print / PDF" }).click();
    await expect(
      page.getByRole("button", { name: "Download HTML" }),
    ).toBeEnabled();
    await page.goto("/claims/CG021");
    await expect(page.locator(".passport-score>strong")).toHaveText("63%");
    await page
      .getByRole("link", { name: "View evidence", exact: true })
      .click();
    await expect(page.locator("mark")).toContainText("signed operative report");
    await page.getByRole("link", { name: "Back to CG021 passport" }).click();
    await page.getByRole("button", { name: "Resolve", exact: true }).click();
    await page
      .getByRole("button", { name: "Generate request", exact: true })
      .click();
    await measure("resolution_request_action_ms", async () => {
      await page
        .getByRole("button", { name: "Simulate request", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Simulate response", exact: true }),
      ).toBeEnabled();
    });
    await page
      .getByRole("button", { name: "Simulate response", exact: true })
      .click();
    await measure("validation_and_targeted_rerun_roundtrip_ms", async () => {
      await page
        .getByRole("button", { name: "Validate & update passport" })
        .click();
      await expect(page.locator(".passport-score>strong")).toHaveText("94%");
    });
    await page.getByRole("tab", { name: "Agent Trace", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Structured execution trace" }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Audit", exact: true }).click();
    await expect(
      page.getByText("Resolution completed", { exact: true }).first(),
    ).toBeVisible();
    await page.goto("/knowledge");
    await measure("knowledge_query_ms", async () => {
      await page.getByRole("button", { name: "Test retrieval" }).click();
      await expect(page.locator(".grounded-answer")).toContainText(
        "anaesthesia",
      );
    });
    await page.goto("/review");
    await page
      .getByRole("combobox", { name: "Demo role" })
      .selectOption("Medical Reviewer");
    await page
      .locator(".review-queue button")
      .filter({ hasText: "CG030" })
      .click();
    await page.getByRole("button", { name: "Override", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Record disposition" }),
    ).toBeDisabled();
    await page
      .getByRole("textbox", { name: "Review reason" })
      .fill(
        "Synthetic demonstration review: package exception confirmed by reviewer.",
      );
    await page.getByRole("button", { name: "Record disposition" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "CG030 is READY" }),
    ).toBeVisible();
    await measure("investigation_graph_load_ms", async () => {
      await page.goto("/investigations");
      await expect(page.locator(".graph-node")).toHaveCount(11);
    });
    await page
      .getByRole("button", {
        name: "Document Shared diagnostic source",
        exact: true,
      })
      .click();
    await expect(page.locator(".graph-detail")).toContainText("fingerprint");
    await page.goto("/integrations");
    await page
      .getByRole("combobox", { name: "Demo role" })
      .selectOption("Claims Executive");
    await page
      .getByRole("button", { name: "Load synthetic FHIR Bundle" })
      .click();
    await measure("fhir_import_ms", async () => {
      await page
        .getByRole("button", { name: "Import & analyse FHIR Bundle" })
        .click();
      await expect(
        page.getByRole("link", { name: "Open imported Claim Passport" }),
      ).toBeVisible();
    });
    await page
      .getByRole("link", { name: "Open imported Claim Passport" })
      .click();
    await expect(page.locator(".passport-score>strong")).toHaveText("98%");
    await page.getByRole("tab", { name: "Agent Trace", exact: true }).click();
    await expect(page.locator(".trace-step")).toHaveCount(8);
    await page.getByRole("tab", { name: "Audit", exact: true }).click();
    await expect(
      page.getByText("Fhir bundle imported", { exact: true }),
    ).toBeVisible();
    const token = await page.evaluate(() => sessionStorage.getItem("cg-token"));
    const headers = { Authorization: "Bearer " + token };
    const states: Record<string, unknown> = {};
    for (const id of ["CG001", "CG021", "CG030", "CG048"]) {
      const c = await (
        await request.get("/api/claims/" + id, { headers })
      ).json();
      states[id] = { status: c.status, readiness: c.readiness };
      if (id === "CG021")
        timings.targeted_rerun_backend_ms = c.tasks[0].data.rerun_duration_ms;
    }
    timings.sequence_total_ms = Math.round(performance.now() - started);
    expect(timings.sequence_total_ms).toBeLessThan(240000);
    fs.mkdirSync("docs/hardening", { recursive: true });
    fs.writeFileSync(
      `docs/hardening/rehearsal-${run}.json`,
      JSON.stringify(
        {
          run,
          states,
          timings,
          scope:
            "Local deterministic synthetic UI flows. No narration or artificial presentation waits.",
        },
        null,
        2,
      ),
    );
    expect(states).toEqual({
      CG001: { status: "READY", readiness: 98 },
      CG021: { status: "READY", readiness: 94 },
      CG030: { status: "READY", readiness: 98 },
      CG048: { status: "INVESTIGATION", readiness: 95 },
    });
  });
