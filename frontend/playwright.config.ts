import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: process.env.DEMO_FRONTEND_URL || "http://127.0.0.1:3000",
    ...(process.env.DEMO_RESET_KEY
      ? { extraHTTPHeaders: { "X-Demo-Reset-Key": process.env.DEMO_RESET_KEY } }
      : {}),
    viewport: { width: 1440, height: 1000 },
    headless: true,
    trace: "retain-on-failure",
  },
  reporter: "list",
});
