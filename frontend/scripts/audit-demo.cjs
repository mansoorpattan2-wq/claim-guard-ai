const { chromium } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const routes = [
    ["dashboard", "/dashboard"],
    ["claims", "/claims"],
    ["intake", "/claims/new"],
    ["passport", "/claims/CG021"],
    ["evidence", "/claims/CG021/evidence/CG021-F14"],
    ["resolution", "/resolutions"],
    ["review", "/review"],
    ["knowledge", "/knowledge"],
    ["investigations", "/investigations"],
    ["integrations", "/integrations"],
    ["audit", "/audit"],
    ["printable", "/claims/CG001/passport"],
  ];
  const folder = path.resolve("docs/hardening");
  fs.mkdirSync(folder, { recursive: true });
  const results = [];
  for (const [name, route] of routes) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("http://127.0.0.1:3000" + route);
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({
      path: path.join(folder, name + ".png"),
      fullPage: true,
    });
    for (const width of [390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      results.push({
        name,
        route,
        width,
        overflow: await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      });
    }
  }
  await page.goto("http://127.0.0.1:3000/claims/CG021");
  await page.waitForLoadState("networkidle");
  await page.getByRole("tab", { name: "Agent Trace", exact: true }).click();
  await page.screenshot({
    path: path.join(folder, "agent-trace.png"),
    fullPage: true,
  });
  fs.writeFileSync(
    path.join(folder, "route-audit.json"),
    JSON.stringify({ results, errors }, null, 2),
  );
  console.log(
    JSON.stringify(
      {
        routes: routes.length + 1,
        overflow: results.filter((r) => r.overflow),
        pageErrors: errors,
      },
      null,
      2,
    ),
  );
  await browser.close();
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
