"use strict";

const InspectionState = (() => {
  function parseIgnored(raw) {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function findingKey(entity) {
    return JSON.stringify(["entity", entity.id, entity.status]);
  }

  function ignoredKeys(records, key, info) {
    const entry = Object.hasOwn(records, key) ? records[key] : null;
    if (!info.config_hash || entry?.config_hash !== info.config_hash) return new Set();
    return new Set(Array.isArray(entry.findings) ? entry.findings.filter((value) => typeof value === "string") : []);
  }

  function withIgnored(records, key, info) {
    const ignored = ignoredKeys(records, key, info);
    const entities = (info.entities || []).map((entity) => ({
      ...entity,
      ignored: !entity.ok && ignored.has(findingKey(entity)),
    }));
    const ignoredCount = entities.filter((entity) => entity.ignored).length;
    return {
      ...info,
      entities,
      ignored_count: ignoredCount,
      issue_count: Math.max(0, Number(info.issue_count || 0) - ignoredCount),
    };
  }

  function toggleIgnored(records, key, info, entity) {
    if (!info.config_hash || entity.ok) return records;
    const ignored = ignoredKeys(records, key, info);
    const finding = findingKey(entity);
    if (ignored.has(finding)) ignored.delete(finding);
    else ignored.add(finding);
    const updated = { ...records };
    if (ignored.size) {
      updated[key] = { config_hash: info.config_hash, findings: [...ignored].sort() };
    } else {
      delete updated[key];
    }
    return updated;
  }

  return { parseIgnored, findingKey, withIgnored, toggleIgnored };
})();

if (typeof module !== "undefined") module.exports = InspectionState;