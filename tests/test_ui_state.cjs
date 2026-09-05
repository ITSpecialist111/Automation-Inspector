const test = require("node:test");
const assert = require("node:assert/strict");
const { parseIgnored, withIgnored, toggleIgnored } = require("../automation_inspector/www/inspection-state.js");

const key = "automation.laundry";
const entity = { id: "sensor.washing_machine", status: "unavailable", ok: false };
const info = { config_hash: "config-one", issue_count: 2, entities: [entity] };

test("ignore is per finding and leaves unrelated issues visible", () => {
  const records = toggleIgnored({}, key, info, entity);
  const view = withIgnored(records, key, info);
  assert.equal(view.issue_count, 1);
  assert.equal(view.ignored_count, 1);
  assert.equal(view.entities[0].ignored, true);
  assert.equal(info.issue_count, 2);
  assert.equal(entity.ignored, undefined);
});

test("ignores persist in JSON and reset on a configuration change", () => {
  const records = parseIgnored(JSON.stringify(toggleIgnored({}, key, info, entity)));
  assert.equal(withIgnored(records, key, info).ignored_count, 1);
  assert.equal(withIgnored(records, key, { ...info, config_hash: "config-two" }).ignored_count, 0);
});

test("a new entity failure state is not hidden by an older ignore", () => {
  const records = toggleIgnored({}, key, info, entity);
  const changed = { ...info, entities: [{ ...entity, status: "missing" }] };
  assert.equal(withIgnored(records, key, changed).issue_count, 2);
  assert.equal(withIgnored(records, "script.laundry", info).ignored_count, 0);
});

test("restore removes the saved ignore", () => {
  const ignored = toggleIgnored({}, key, info, entity);
  const restored = toggleIgnored(ignored, key, info, entity);
  assert.deepEqual(restored, {});
  assert.equal(withIgnored(restored, key, info).issue_count, 2);
});

test("healthy entities and unavailable configurations cannot be ignored", () => {
  assert.deepEqual(toggleIgnored({}, key, info, { ...entity, ok: true }), {});
  assert.deepEqual(toggleIgnored({}, key, { ...info, config_hash: null }, entity), {});
});

test("malformed browser storage does not break the report", () => {
  for (const raw of [null, "broken", "[]", "null", "42"]) {
    assert.deepEqual(parseIgnored(raw), {});
  }
  for (const entry of [null, 42, {}, { config_hash: "config-one", findings: "bad" }]) {
    assert.equal(withIgnored({ [key]: entry }, key, info).ignored_count, 0);
  }
});