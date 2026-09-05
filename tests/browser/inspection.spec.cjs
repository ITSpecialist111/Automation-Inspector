const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

async function replaceReport(page, change) {
  const response = await page.request.get("/api/v1/inspection");
  const report = await response.json();
  change(report);
  await page.route("**/api/v1/inspection*", (route) => route.fulfill({ json: report }));
}

async function ignoreLaundry(page) {
  const laundry = page.locator('[data-item-key="automation.laundry_reminder"]');
  await laundry.locator("summary").click();
  await laundry.getByRole("button", { name: "Ignore unavailable finding for sensor.washing_machine", exact: true }).click();
  await expect(page.locator("#ignored-count")).toHaveText("1");
}

test("loads the real app and synthetic inspection", async ({ page }) => {
  const response = await page.goto("/");
  expect(response.headers()["content-security-policy"]).toContain("'nonce-");
  await expect(page.getByRole("heading", { name: "Automation Inspector", exact: true })).toBeVisible();
  await expect(page.locator("#automation-list .automation-card")).toHaveCount(12);
  await expect(page.locator("#instance-name")).toContainText("Demo Home");
});

test("navigates automation, script, helper, and ignored views", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#all-count")).toHaveText("12");
  await page.locator('[data-view="script"]').click();
  await expect(page.locator("#automation-list .automation-card")).toHaveCount(3);
  await page.locator('[data-view="automation"]').click();
  await expect(page.locator("#automation-list .automation-card")).toHaveCount(9);
  await page.locator('[data-view="helpers"]').click();
  await expect(page.locator("#workspace")).toBeHidden();
  await expect(page.locator("#helper-panel")).toBeVisible();
  await expect(page.locator(".helper-row")).toHaveCount(2);
  await page.locator('[data-view="ignored"]').click();
  await expect(page.locator("#empty-state")).toBeVisible();
  await page.locator('[data-view="all"]').click();
  await expect(page.locator("#automation-list .automation-card")).toHaveCount(12);
});

test("filters and resets inspection results", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#all-count")).toHaveText("12");
  await page.locator("#status-filter").selectOption("disabled");
  await expect(page.locator(".automation-card")).toHaveCount(1);
  await expect(page.locator(".automation-title")).toHaveText("Heating schedule");
  await page.locator("#clear-filters").click();
  await page.locator("#search-input").fill("washing_machine");
  await expect(page.locator(".automation-card")).toHaveCount(1);
  await expect(page.locator(".automation-title")).toHaveText("Laundry reminder");
  await page.locator("#clear-filters").click();
  await page.locator("#run-filter").selectOption("older");
  await expect(page.locator(".automation-card")).toHaveCount(5);
  await page.locator("#clear-filters").click();
  await page.locator("#sort-filter").selectOption("name");
  await expect(page.locator(".automation-title").first()).toHaveText("Announce to household");
});

test("ignores persist and can be restored without hiding other issues", async ({ page }) => {
  await page.goto("/");
  const laundry = page.locator('[data-item-key="automation.laundry_reminder"]');
  await laundry.locator("summary").click();
  await laundry.getByRole("button", { name: "Ignore unavailable finding for sensor.washing_machine", exact: true }).click();
  await expect(laundry.locator(".finding-count")).toContainText("Clear");
  await expect(laundry.locator("details")).toHaveAttribute("open", "");
  await expect(page.locator("#ignored-count")).toHaveText("1");
  await page.reload();
  await expect(page.locator("#ignored-count")).toHaveText("1");
  await page.locator('[data-view="ignored"]').click();
  await expect(page.locator(".automation-card")).toHaveCount(1);
  await laundry.locator("summary").click();
  await laundry.getByRole("button", { name: "Restore unavailable finding for sensor.washing_machine", exact: true }).click();
  await expect(page.locator("#ignored-count")).toHaveText("0");
  await expect(page.locator("#empty-state")).toBeVisible();
});

test("theme parameters override saved and system preferences", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/?scoutTheme=light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.locator("#theme-button").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("configuration edits automatically restore ignored findings", async ({ page }) => {
  await page.goto("/");
  await ignoreLaundry(page);
  await replaceReport(page, (report) => { report.automations["automation.laundry_reminder"].config_hash = "changed-config"; });
  await page.locator("#refresh-button").click();
  await expect(page.locator("#ignored-count")).toHaveText("0");
  await expect(page.locator('[data-item-key="automation.laundry_reminder"] .finding-count')).toHaveText("1 issue");
});

test("a missing configuration cannot be ignored", async ({ page }) => {
  await replaceReport(page, (report) => { report.automations["automation.laundry_reminder"].config_hash = null; });
  await page.goto("/");
  const laundry = page.locator('[data-item-key="automation.laundry_reminder"]');
  await laundry.locator("summary").click();
  await expect(laundry.getByRole("button", { name: "Ignore unavailable finding for sensor.washing_machine", exact: true })).toBeDisabled();
});

test("blocked storage keeps ignores session-only and reports it", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new DOMException("Storage blocked", "SecurityError"); } });
  });
  await page.goto("/");
  await ignoreLaundry(page);
  await expect(page.locator("#toast")).toContainText("session only");
  await page.reload();
  await expect(page.locator("#all-count")).toHaveText("12");
  await expect(page.locator("#ignored-count")).toHaveText("0");
});

test("refresh failures retain results and recover without stale warnings", async ({ page }) => {
  await page.clock.install();
  await page.goto("/");
  await expect(page.locator(".automation-card")).toHaveCount(12);
  await page.route("**/api/v1/inspection*", (route) => route.fulfill({ status: 503, json: { detail: "Home Assistant is restarting" } }));
  await page.locator("#refresh-button").click();
  await expect(page.locator("#alert-stack")).toContainText("Home Assistant is restarting");
  await expect(page.locator(".automation-card")).toHaveCount(12);
  await page.clock.fastForward(31000);
  await expect(page.locator("#connection-status")).toHaveText("Inspection unavailable");
  await page.unroute("**/api/v1/inspection*");
  await page.locator("#refresh-button").click();
  await expect(page.locator("#connection-status")).toHaveText("Inspection current");
  await expect(page.locator("#alert-stack")).toBeEmpty();
});

test("initial error recovery restores normal empty-state text", async ({ page }) => {
  await page.route("**/api/v1/inspection*", (route) => route.fulfill({ status: 503, json: { detail: "Not ready" } }));
  await page.goto("/");
  await expect(page.locator("#empty-state h3")).toHaveText("Inspection unavailable");
  await page.unroute("**/api/v1/inspection*");
  await page.locator("#refresh-button").click();
  await expect(page.locator(".automation-card")).toHaveCount(12);
  await page.locator("#search-input").fill("no-such-automation");
  await expect(page.locator("#empty-state h3")).toHaveText("No matching items");
});

test("cached inspections use ETags and preserve open details", async ({ page }) => {
  await page.clock.install();
  await page.goto("/");
  const laundry = page.locator('[data-item-key="automation.laundry_reminder"]');
  await laundry.locator("summary").click();
  await page.route("**/api/v1/inspection*", (route) => {
    const etag = route.request().headers()["if-none-match"];
    expect(etag).toBeTruthy();
    return route.fulfill({ status: 304, headers: { ETag: etag } });
  });
  const cached = page.waitForResponse((response) => response.url().includes("/api/v1/inspection") && response.status() === 304);
  await page.clock.fastForward(60000);
  await cached;
  await expect(laundry.locator("details")).toHaveAttribute("open", "");
  await expect(page.locator("#connection-status")).toHaveText("Inspection current");
});

test("large reports paginate without losing filters", async ({ page }) => {
  await replaceReport(page, (report) => {
    const item = report.automations["automation.evening_lights"];
    report.automations = Object.fromEntries(Array.from({ length: 61 }, (_, index) => {
      const entityId = `automation.scheduled_${index}`;
      return [entityId, { ...item, entity_id: entityId, friendly_name: `Scheduled ${String(index).padStart(2, "0")}` }];
    }));
    report.scripts = {};
    Object.assign(report.summary, { automations: 61, scripts: 0, inspected_items: 61 });
  });
  await page.goto("/");
  await expect(page.locator(".automation-card")).toHaveCount(50);
  await page.locator("#load-more").click();
  await expect(page.locator(".automation-card")).toHaveCount(61);
  await expect(page.locator("#load-more-row")).toBeHidden();
  await page.locator("#search-input").fill("Scheduled 60");
  await expect(page.locator(".automation-card")).toHaveCount(1);
});

test("API text stays text and links cannot use unsafe protocols", async ({ page }) => {
  const text = '<img src=x onerror="window.injectionRan=true">';
  await replaceReport(page, (report) => {
    const item = report.automations["automation.laundry_reminder"];
    item.friendly_name = text;
    item.entities[0].name = text;
    item.compatibility_issues = [{ code: "probe", severity: "warning", message: text, path: "$", docs_url: "javascript:alert(1)" }];
    report.home_assistant.frontend_url = "javascript:alert(1)";
  });
  await page.goto("/");
  const laundry = page.locator('[data-item-key="automation.laundry_reminder"]');
  await expect(laundry.locator(".automation-title")).toHaveText(text);
  await laundry.locator("summary").click();
  await expect(laundry.locator(".finding-message")).toHaveText(text);
  await expect(page.locator("img, a[href^='javascript:']")).toHaveCount(0);
  expect(await page.evaluate(() => window.injectionRan)).toBeUndefined();
});

test("keyboard controls and inspection requests stay read-only", async ({ page }) => {
  const methods = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) methods.push(request.method());
  });
  await page.goto("/");
  await page.locator('[data-view="script"]').focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".automation-card")).toHaveCount(3);
  const summary = page.locator(".details-summary").first();
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("details").first()).toHaveAttribute("open", "");
  await page.keyboard.press("Space");
  await expect(page.locator("details").first()).not.toHaveAttribute("open", "");
  await page.locator("#refresh-button").click();
  await expect(page.locator("#refresh-button")).toBeEnabled();
  expect(methods.length).toBeGreaterThan(1);
  expect(methods.every((method) => method === "GET")).toBe(true);
});

test("assets render and expanded views pass accessibility checks", async ({ page }, testInfo) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("/");
  await expect(page.locator(".automation-card")).toHaveCount(12);
  await page.evaluate(() => document.fonts.ready);
  const fonts = await page.evaluate(() => [...document.fonts].filter((font) => font.status === "loaded").map((font) => font.family));
  expect(fonts).toContain("DM Sans");
  expect(fonts).toContain("Source Code Pro");
  await page.screenshot({ path: `test-results/overview-${testInfo.project.name}.png` });
  await page.locator('[data-item-key="automation.laundry_reminder"] summary').click();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations.map(({ id, nodes }) => ({ id, targets: nodes.map((node) => node.target) }))).toEqual([]);
  await page.screenshot({ path: `test-results/details-${testInfo.project.name}.png` });
  await page.locator("#theme-button").click();
  const darkResults = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkResults.violations.map(({ id, nodes }) => ({ id, targets: nodes.map((node) => node.target) }))).toEqual([]);
  await page.screenshot({ path: `test-results/dark-${testInfo.project.name}.png` });
  expect(errors).toEqual([]);
});

test("content and controls fit narrow, tablet, and wide screens", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".automation-card")).toHaveCount(12);
  await page.locator('[data-item-key="automation.laundry_reminder"] summary').click();
  for (const width of [320, 375, 768, 1024, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    const layout = await page.evaluate(() => {
      const context = document.createElement("canvas").getContext("2d");
      return {
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        clippedSelects: [...document.querySelectorAll("select")].filter((select) => {
          const style = getComputedStyle(select);
          context.font = style.font;
          const textWidth = context.measureText(select.selectedOptions[0].textContent).width;
          return textWidth + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 20 > select.clientWidth;
        }).map((select) => select.id),
      };
    });
    expect(layout, `Layout at ${width}px`).toEqual({ overflow: false, clippedSelects: [] });
  }
});