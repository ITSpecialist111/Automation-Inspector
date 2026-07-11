"use strict";

const PAGE_SIZE = 50;
const THEME_KEY = "automation-inspector-theme";
const STATUS_LABELS = {
  enabled: "Enabled",
  disabled: "Disabled",
  not_loaded: "Not loaded",
  unavailable: "Unavailable",
  ok: "Healthy",
  missing: "Missing",
  unknown: "Unknown",
};

const state = {
  data: null,
  etag: null,
  lastLoadedAt: null,
  stale: false,
  loading: false,
  displayLimit: PAGE_SIZE,
  toastTimer: null,
};

const element = (id) => document.getElementById(id);

function create(tag, options = {}) {
  const item = document.createElement(tag);
  if (options.className) item.className = options.className;
  if (options.text !== undefined && options.text !== null) {
    item.textContent = String(options.text);
  }
  if (options.title) item.title = options.title;
  return item;
}

function addText(parent, text, className) {
  const item = create("span", { className, text });
  parent.append(item);
  return item;
}

function safeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value) {
  const date = safeDate(value);
  if (!date) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function relativeTime(value) {
  const date = safeDate(value);
  if (!date) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function statusClass(status) {
  return Object.hasOwn(STATUS_LABELS, status) ? status : "disabled";
}

function statusBadge(status) {
  return create("span", {
    className: `status-badge ${statusClass(status)}`,
    text: STATUS_LABELS[status] || String(status || "Unknown"),
  });
}

function safeHomeAssistantBase() {
  if (window.location.pathname.includes("/api/hassio_ingress/")) {
    return window.location.origin;
  }
  const configured = state.data?.home_assistant?.frontend_url;
  if (configured) {
    try {
      const url = new URL(configured);
      if (url.protocol === "http:" || url.protocol === "https:") return url.origin;
    } catch (_error) {
      // Fall through to the conventional local Home Assistant endpoint.
    }
  }
  return `${window.location.protocol}//${window.location.hostname}:8123`;
}

function homeAssistantUrl(path) {
  try {
    return new URL(path, safeHomeAssistantBase()).href;
  } catch (_error) {
    return null;
  }
}

function safeDocsUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && url.hostname === "www.home-assistant.io") {
      return url.href;
    }
  } catch (_error) {
    return null;
  }
  return null;
}

function link(text, href, className) {
  if (!href) return create("span", { className, text });
  const anchor = create("a", { className, text });
  anchor.href = href;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function showToast(message, isError = false) {
  const toast = element("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  if (state.toastTimer) window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 5000);
}

function updateThemeButton() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const button = element("theme-button");
  button.setAttribute(
    "aria-label",
    current === "dark" ? "Switch to light theme" : "Switch to dark theme",
  );
  button.title = current === "dark" ? "Use light theme" : "Use dark theme";
}

function initializeTheme() {
  const parameterTheme = new URLSearchParams(window.location.search).get("scoutTheme");
  if (!parameterTheme) {
    try {
      const saved = window.localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") {
        document.documentElement.setAttribute("data-theme", saved);
      }
    } catch (_error) {
      // Storage can be blocked in privacy-oriented iframe configurations.
    }
  }
  updateThemeButton();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    window.localStorage.setItem(THEME_KEY, next);
  } catch (_error) {
    // A theme change still works for the current page when storage is blocked.
  }
  updateThemeButton();
}

function metricCard(label, value, note, tone = "") {
  const card = create("article", { className: `metric-card ${tone}`.trim() });
  addText(card, label, "metric-label");
  addText(card, value ?? 0, "metric-value");
  addText(card, note, "metric-note");
  return card;
}

function renderMetrics() {
  const metrics = element("metrics");
  metrics.replaceChildren();
  const summary = state.data?.summary || {};
  const unhealthyEntities =
    Number(summary.missing_entities || 0) +
    Number(summary.unavailable_entities || 0) +
    Number(summary.unknown_entities || 0) +
    Number(summary.disabled_entities || 0);
  metrics.append(
    metricCard(
      "Automations",
      summary.automations,
      `${summary.enabled || 0} enabled · ${summary.disabled || 0} disabled`,
    ),
    metricCard(
      "Need attention",
      summary.automations_with_issues,
      `${summary.unloaded || 0} not loaded`,
      summary.automations_with_issues ? "danger" : "",
    ),
    metricCard(
      "Dependency health",
      unhealthyEntities,
      `${summary.unique_entities || 0} unique entities checked`,
      unhealthyEntities ? "danger" : "",
    ),
    metricCard(
      "Compatibility",
      summary.compatibility_issues,
      "Errors and deprecations",
      summary.compatibility_issues ? "warning" : "",
    ),
    metricCard(
      "Unresolved targets",
      summary.unresolved_targets,
      "Devices, areas, floors, or labels",
      summary.unresolved_targets ? "warning" : "",
    ),
    metricCard(
      "Trace failures",
      summary.trace_failures,
      "Latest completed runs",
      summary.trace_failures ? "danger" : "",
    ),
  );
}

function alertRow(message, tone = "warning") {
  const row = create("div", { className: `alert ${tone}` });
  const symbol = create("span", {
    text: tone === "error" ? "!" : "i",
    className: "status-badge",
  });
  symbol.setAttribute("aria-hidden", "true");
  row.append(symbol, create("span", { text: message }));
  return row;
}

function renderAlerts(extraError = null) {
  const stack = element("alert-stack");
  stack.replaceChildren();
  if (extraError) stack.append(alertRow(extraError, "error"));
  if (state.stale) {
    stack.append(
      alertRow(
        "Home Assistant could not be refreshed. Showing the last successful inspection.",
        "warning",
      ),
    );
  }
  const warnings = Array.isArray(state.data?.warnings) ? state.data.warnings : [];
  warnings.slice(0, 5).forEach((warning) => stack.append(alertRow(String(warning))));
  if (warnings.length > 5) {
    stack.append(alertRow(`${warnings.length - 5} additional source warnings were suppressed.`));
  }
}

function updateConnection(error = null) {
  const dot = element("connection-dot");
  const label = element("connection-status");
  dot.classList.remove("connected", "error");
  if (error) {
    dot.classList.add("error");
    label.textContent = "Inspection unavailable";
  } else if (state.stale) {
    label.textContent = "Last-known-good inspection";
  } else if (state.data) {
    dot.classList.add("connected");
    label.textContent = "Inspection current";
  } else {
    label.textContent = "Preparing inspection…";
  }
  element("generated-time").textContent = state.data?.generated_at
    ? `Generated ${relativeTime(state.data.generated_at)}`
    : "Waiting for data";
}

function automationSearchText(key, info) {
  const parts = [key, info.friendly_name, info.status, info.config_id, info.mode];
  (info.entities || []).forEach((entity) => {
    parts.push(entity.id, entity.name, entity.state, entity.status);
  });
  (info.compatibility_issues || []).forEach((finding) => {
    parts.push(finding.code, finding.message, finding.current, finding.replacement);
  });
  (info.targets || []).forEach((target) => {
    parts.push(
      target.component,
      ...(target.entity_ids || []),
      ...(target.device_ids || []),
      ...(target.area_ids || []),
      ...(target.floor_ids || []),
      ...(target.label_ids || []),
    );
  });
  return parts.filter(Boolean).join(" ").toLocaleLowerCase();
}

function daysSince(value) {
  const date = safeDate(value);
  return date ? (Date.now() - date.getTime()) / 86400000 : Number.POSITIVE_INFINITY;
}

function filteredAutomations() {
  const query = element("search-input").value.trim().toLocaleLowerCase();
  const status = element("status-filter").value;
  const run = element("run-filter").value;
  const issuesOnly = element("issues-only").checked;
  const sort = element("sort-filter").value;
  const entries = Object.entries(state.data?.automations || {}).filter(([key, info]) => {
    if (status !== "all" && info.status !== status) return false;
    if (issuesOnly && Number(info.issue_count || 0) === 0) return false;
    const age = daysSince(info.last_triggered);
    if (run === "never" && info.last_triggered) return false;
    if (run === "older" && age <= 30) return false;
    if (!Number.isNaN(Number(run)) && run !== "all" && age > Number(run)) return false;
    return !query || automationSearchText(key, info).includes(query);
  });

  const byName = (left, right) =>
    String(left[1].friendly_name || left[0]).localeCompare(
      String(right[1].friendly_name || right[0]),
      undefined,
      { sensitivity: "base" },
    );
  entries.sort((left, right) => {
    if (sort === "name") return byName(left, right);
    const leftTime = safeDate(left[1].last_triggered)?.getTime() || 0;
    const rightTime = safeDate(right[1].last_triggered)?.getTime() || 0;
    if (sort === "recent") return rightTime - leftTime || byName(left, right);
    if (sort === "oldest") return leftTime - rightTime || byName(left, right);
    return Number(right[1].issue_count || 0) - Number(left[1].issue_count || 0) || byName(left, right);
  });
  return entries;
}

function entityLink(entity, preview = false) {
  const url = homeAssistantUrl(
    `/developer-tools/state?entity_id=${encodeURIComponent(entity.id)}`,
  );
  const chip = link("", url, `entity-chip${entity.ok ? "" : " problem"}`);
  const id = create("span", { className: "entity-id", text: entity.id });
  chip.append(id);
  if (!preview) {
    chip.append(create("span", { className: "entity-state", text: `· ${entity.state}` }));
  }
  chip.title = `${entity.name || entity.id}: ${entity.state}`;
  return chip;
}

function automationHeader(key, info) {
  const main = create("div", { className: "automation-main" });
  const heading = create("div", { className: "automation-heading" });
  heading.append(statusBadge(info.status));
  const title = create("div", { className: "automation-title-wrap" });
  title.append(
    create("h3", { className: "automation-title", text: info.friendly_name || key }),
    create("span", { className: "automation-id", text: info.entity_id || `YAML · ${info.config_id || key}` }),
  );
  heading.append(title);

  const meta = create("div", { className: "automation-meta" });
  const run = create("span", {
    className: "meta-item",
    text: `Last run: ${relativeTime(info.last_triggered)}`,
    title: formatDate(info.last_triggered),
  });
  meta.append(run);
  if (info.mode) meta.append(create("span", { className: "meta-item", text: `Mode: ${info.mode}` }));
  meta.append(
    create("span", {
      className: "meta-item",
      text: `${(info.entities || []).length} dependencies`,
    }),
  );

  const preview = create("div", { className: "entity-preview" });
  const orderedEntities = [...(info.entities || [])].sort(
    (left, right) => Number(left.ok) - Number(right.ok) || left.id.localeCompare(right.id),
  );
  orderedEntities.slice(0, 4).forEach((entity) => preview.append(entityLink(entity, true)));
  if (orderedEntities.length > 4) {
    preview.append(
      create("span", {
        className: "entity-chip more-chip",
        text: `+${orderedEntities.length - 4} more`,
      }),
    );
  }
  if (orderedEntities.length === 0) {
    preview.append(create("span", { className: "section-note", text: "No entity references found" }));
  }

  const actions = create("div", { className: "automation-actions" });
  if (info.loaded && info.config_id) {
    actions.append(
      link(
        "Edit",
        homeAssistantUrl(`/config/automation/edit/${encodeURIComponent(info.config_id)}`),
        "button button-secondary small-button",
      ),
      link(
        "Traces",
        homeAssistantUrl(`/config/automation/trace/${encodeURIComponent(info.config_id)}`),
        "button button-ghost small-button",
      ),
    );
  }
  main.append(heading, meta, preview, actions);
  return main;
}

function detailPanel(title, className = "") {
  const panel = create("section", { className: `detail-panel ${className}`.trim() });
  panel.append(create("h4", { text: title }));
  return panel;
}

function dependenciesPanel(info) {
  const panel = detailPanel("Dependencies");
  const list = create("ul", { className: "entity-list" });
  const entities = info.entities || [];
  if (!entities.length) {
    list.append(create("li", { className: "section-note", text: "No direct or resolved entity dependencies." }));
  }
  entities.forEach((entity) => {
    const row = create("li", { className: "entity-row" });
    const identity = create("div");
    identity.append(
      link(
        entity.id,
        homeAssistantUrl(`/developer-tools/state?entity_id=${encodeURIComponent(entity.id)}`),
        "entity-id",
      ),
      create("span", {
        className: "entity-name",
        text: `${entity.name || entity.id} · via ${(entity.sources || []).join(", ") || "configuration"}`,
      }),
    );
    row.append(identity, statusBadge(entity.status));
    list.append(row);
  });
  panel.append(list);
  return panel;
}

function findingsPanel(info) {
  const findings = info.compatibility_issues || [];
  if (!findings.length) return null;
  const panel = detailPanel("Validation & compatibility");
  const list = create("ul", { className: "finding-list" });
  findings.forEach((finding) => {
    const severity = ["error", "warning", "info"].includes(finding.severity)
      ? finding.severity
      : "info";
    const row = create("li", { className: `finding ${severity}` });
    const heading = create("div", { className: "finding-title" });
    heading.append(
      create("p", { className: "finding-message", text: finding.message || finding.code }),
      create("span", { className: `status-badge ${severity === "error" ? "missing" : "disabled"}`, text: severity }),
    );
    row.append(heading);
    if (finding.replacement) {
      row.append(
        create("span", {
          className: "finding-replacement",
          text: `Use: ${finding.replacement}`,
        }),
      );
    }
    const location = create("span", {
      className: "finding-path path",
      text: finding.path || "$",
    });
    row.append(location);
    const docs = safeDocsUrl(finding.docs_url);
    if (docs) row.append(link("Learn more", docs, "finding-path"));
    list.append(row);
  });
  panel.append(list);
  return panel;
}

function appendTargetChips(container, label, values, missing = false) {
  (values || []).forEach((value) => {
    container.append(
      create("span", {
        className: `target-chip${missing ? " missing" : ""}`,
        text: `${label}: ${value}`,
      }),
    );
  });
}

function targetsPanel(info) {
  const targets = info.targets || [];
  if (!targets.length) return null;
  const panel = detailPanel("Resolved targets");
  const list = create("ul", { className: "target-list" });
  targets.forEach((target) => {
    const row = create("li", { className: "target-row" });
    row.append(
      create("strong", {
        text: `${target.kind || "target"}${target.component ? ` · ${target.component}` : ""}`,
      }),
      create("span", { className: "target-path path", text: target.path || "$.target" }),
    );
    const chips = create("div", { className: "target-chips" });
    appendTargetChips(chips, "Entity", target.entity_ids);
    appendTargetChips(chips, "Device", target.device_ids);
    appendTargetChips(chips, "Area", target.area_ids);
    appendTargetChips(chips, "Floor", target.floor_ids);
    appendTargetChips(chips, "Label", target.label_ids);
    appendTargetChips(chips, "Missing device", target.missing_devices, true);
    appendTargetChips(chips, "Missing area", target.missing_areas, true);
    appendTargetChips(chips, "Missing floor", target.missing_floors, true);
    appendTargetChips(chips, "Missing label", target.missing_labels, true);
    if (!chips.childElementCount) {
      chips.append(create("span", { className: "section-note", text: "No matching entities." }));
    }
    row.append(chips);
    list.append(row);
  });
  panel.append(list);
  return panel;
}

function diagnosticsPanel(info) {
  if (!info.trace && !(info.warnings || []).length) return null;
  const panel = detailPanel("Recent execution & notes", "full-width");
  const list = create("ul", { className: "trace-list" });
  if (info.trace) {
    const hasError = Boolean(
      info.trace.error ||
      (info.trace.template_errors || []).length ||
      ["error", "failed_max_runs"].includes(info.trace.script_execution),
    );
    const summary = create("li", { className: `trace-line${hasError ? " error" : ""}` });
    summary.append(
      create("strong", { text: hasError ? "Latest trace failed" : "Latest trace completed" }),
      create("span", {
        text: ` · ${info.trace.script_execution || info.trace.state || "unknown"}`,
      }),
    );
    if (info.trace.error) summary.append(create("span", { text: ` · ${info.trace.error}` }));
    list.append(summary);
    (info.trace.template_errors || []).forEach((error) => {
      list.append(create("li", { className: "trace-line error", text: `Template: ${error}` }));
    });
  }
  (info.warnings || []).forEach((warning) => {
    list.append(create("li", { className: "warning-row", text: warning }));
  });
  panel.append(list);
  return panel;
}

function renderDetailBody(body, info) {
  body.append(dependenciesPanel(info));
  [findingsPanel(info), targetsPanel(info), diagnosticsPanel(info)]
    .filter(Boolean)
    .forEach((panel) => body.append(panel));
}

function automationCard(key, info) {
  const card = create("article", {
    className: `automation-card${info.issue_count ? " has-issues" : ""}${info.loaded ? "" : " not-loaded"}`,
  });
  card.append(automationHeader(key, info));

  const details = create("details", { className: "inspection-details" });
  const summary = create("summary", {
    className: "details-summary",
    text:
      `Inspection details · ${(info.entities || []).length} dependencies · ` +
      `${(info.targets || []).length} targets · ${(info.compatibility_issues || []).length} checks`,
  });
  const body = create("div", { className: "details-body" });
  details.append(summary, body);
  details.addEventListener("toggle", () => {
    if (details.open && details.dataset.rendered !== "true") {
      renderDetailBody(body, info);
      details.dataset.rendered = "true";
    }
  });
  card.append(details);
  return card;
}

function renderAutomations() {
  if (!state.data) return;
  const list = element("automation-list");
  list.replaceChildren();
  const entries = filteredAutomations();
  const visible = entries.slice(0, state.displayLimit);
  visible.forEach(([key, info]) => list.append(automationCard(key, info)));

  element("loading-state").classList.add("hidden");
  element("empty-state").classList.toggle("hidden", entries.length !== 0);
  const loadMoreRow = element("load-more-row");
  loadMoreRow.classList.toggle("hidden", visible.length >= entries.length);
  element("load-more").textContent = `Show ${Math.min(PAGE_SIZE, entries.length - visible.length)} more`;
  element("result-count").textContent =
    entries.length === Object.keys(state.data.automations || {}).length
      ? `${entries.length} automations inspected`
      : `${entries.length} of ${Object.keys(state.data.automations || {}).length} automations match`;
}

function renderHelpers() {
  const helpers = state.data?.unreferenced_helpers || [];
  const panel = element("helper-panel");
  panel.classList.toggle("hidden", helpers.length === 0);
  element("helper-count").textContent = String(helpers.length);
  const list = element("helper-list");
  list.replaceChildren();
  helpers.forEach((helper) => {
    const row = create("article", { className: "helper-row" });
    const identity = create("div");
    identity.append(
      create("span", { className: "helper-name", text: helper.name || helper.id }),
      link(
        helper.id,
        homeAssistantUrl(`/developer-tools/state?entity_id=${encodeURIComponent(helper.id)}`),
        "helper-id",
      ),
    );
    row.append(
      identity,
      create("span", {
        className: `entity-chip${helper.status === "ok" ? "" : " problem"}`,
        text: helper.state,
      }),
    );
    list.append(row);
  });
}

function renderPage() {
  if (!state.data) return;
  renderMetrics();
  renderAlerts();
  renderAutomations();
  renderHelpers();
  const home = state.data.home_assistant || {};
  element("instance-name").textContent = home.location_name
    ? `${home.location_name} · Home Assistant ${home.version || "unknown"}`
    : `Home Assistant ${home.version || "unknown"}`;
  element("version-note").textContent =
    `Schema ${state.data.schema_version || "?"} · analyzed in ${state.data.summary?.duration_ms || 0} ms`;
  element("footer-version").textContent = `Automation Inspector ${state.data.app_version || ""}`.trim();
  updateConnection();
}

function setLoading(loading) {
  state.loading = loading;
  const button = element("refresh-button");
  button.disabled = loading;
  button.setAttribute("aria-busy", String(loading));
  if (!state.data) element("loading-state").classList.toggle("hidden", !loading);
}

async function loadInspection(force = false) {
  if (state.loading) return;
  setLoading(true);
  try {
    const url = new URL("api/v1/inspection", window.location.href);
    if (force) url.searchParams.set("refresh", "true");
    const headers = new Headers();
    if (state.etag && !force) headers.set("If-None-Match", state.etag);
    const response = await fetch(url, { cache: "no-cache", headers });
    if (response.status === 304) {
      state.lastLoadedAt = new Date();
      state.stale = response.headers.get("X-Automation-Inspector-Stale") === "true";
      updateConnection();
      renderAlerts();
      return;
    }
    let body;
    try {
      body = await response.json();
    } catch (_error) {
      body = null;
    }
    if (!response.ok) {
      throw new Error(body?.detail || `Inspection request failed (${response.status})`);
    }
    if (!body || body.schema_version !== 2 || typeof body.automations !== "object") {
      throw new Error("The server returned an unsupported inspection format.");
    }
    state.data = body;
    state.etag = response.headers.get("ETag");
    state.lastLoadedAt = new Date();
    state.stale = response.headers.get("X-Automation-Inspector-Stale") === "true";
    state.displayLimit = PAGE_SIZE;
    renderPage();
    if (force) showToast("Inspection refreshed successfully.");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load the inspection.";
    renderAlerts(message);
    updateConnection(message);
    showToast(message, true);
    if (!state.data) {
      element("loading-state").classList.add("hidden");
      element("empty-state").classList.remove("hidden");
      element("empty-state").querySelector("h3").textContent = "Inspection unavailable";
      element("empty-state").querySelector("p").textContent = "Automation Inspector will retry automatically.";
      window.setTimeout(() => loadInspection(false), 15000);
    }
  } finally {
    setLoading(false);
  }
}

function resetFilters() {
  element("filter-form").reset();
  state.displayLimit = PAGE_SIZE;
  renderAutomations();
  element("search-input").focus();
}

function bindEvents() {
  element("theme-button").addEventListener("click", toggleTheme);
  element("refresh-button").addEventListener("click", () => loadInspection(true));
  element("clear-filters").addEventListener("click", resetFilters);
  element("filter-form").addEventListener("submit", (event) => event.preventDefault());
  ["search-input", "status-filter", "run-filter", "sort-filter", "issues-only"].forEach((id) => {
    const eventName = id === "search-input" ? "input" : "change";
    element(id).addEventListener(eventName, () => {
      state.displayLimit = PAGE_SIZE;
      renderAutomations();
    });
  });
  element("load-more").addEventListener("click", () => {
    state.displayLimit += PAGE_SIZE;
    renderAutomations();
  });
}

initializeTheme();
bindEvents();
loadInspection(false);
window.setInterval(() => loadInspection(false), 60000);
window.setInterval(() => updateConnection(), 30000);