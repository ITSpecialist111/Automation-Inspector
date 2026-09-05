const { defineConfig } = require("@playwright/test");
const { existsSync } = require("node:fs");
const { join } = require("node:path");

const localPython = join(__dirname, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.AI_TEST_PYTHON || (existsSync(localPython) ? localPython : "python");
const port = Number(process.env.AI_UI_PORT || 8765);
const baseURL = `http://127.0.0.1:${port}`;

module.exports = defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  workers: 2,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: { baseURL, colorScheme: "light", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `"${python}" -m uvicorn ui_server:app --app-dir tests --host 127.0.0.1 --port ${port}`,
    env: { PYTHONPATH: join(__dirname, "automation_inspector") },
    url: `${baseURL}/health`,
    reuseExistingServer: false,
    timeout: 30000,
  },
});