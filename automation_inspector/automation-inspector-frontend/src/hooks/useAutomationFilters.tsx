"use client";

import { useState, useMemo } from "react";
import type { DependencyMap } from "../utils/types";

export function useAutomationFilters(data: DependencyMap | null) {
  const [errOnly, setErrOnly] = useState(false);
  const [runFilter, setRunFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [enabledStatus, setEnabledStatus] = useState("all");
  const [entityState, setEntityState] = useState("all");

  const filteredAutomations = useMemo(() => {
    if (!data) return [];

    return Object.entries(data.automations)
      .filter(([, info]) => {
        const hasBad = info.entities.some((e) => !e.ok);
        if (errOnly && !hasBad) return false;

        if (enabledStatus !== "all") {
          const isEnabled = enabledStatus === "enabled";
          if (info.enabled !== isEnabled) return false;
        }

        if (entityState !== "all") {
          const hasMatchingState = info.entities.some(
            (e) => e.state.toLowerCase() === entityState.toLowerCase(),
          );
          if (!hasMatchingState) return false;
        }

        if (runFilter !== "all") {
          const lastTs = info.last_triggered
            ? new Date(info.last_triggered).getTime()
            : null;
          const daysOld = lastTs
            ? (Date.now() - lastTs) / (1000 * 60 * 60 * 24)
            : Number.POSITIVE_INFINITY;
          const n = Math.abs(Number(runFilter));
          if (runFilter.startsWith("-")) {
            if (daysOld <= n) return false;
          } else {
            if (daysOld > n) return false;
          }
        }

        if (search) {
          const nameMatch = info.friendly_name
            .toLowerCase()
            .includes(search.toLowerCase());
          const entMatch = info.entities.some((e) =>
            e.id.toLowerCase().includes(search.toLowerCase()),
          );
          if (!nameMatch && !entMatch) return false;
        }
        return true;
      })
      .map(([id, info]) => ({ id, ...info }));
  }, [data, errOnly, runFilter, search]);

  const stats = useMemo(() => {
    if (!data) return { total: 0, ent: 0, err: 0, badEnts: 0 };

    let ent = 0,
      err = 0,
      badEnts = 0;
    Object.values(data.automations).forEach((info) => {
      ent += info.entities.length;
      const hasBad = info.entities.some((e) => !e.ok);
      if (hasBad) err++;
      info.entities.forEach((e) => {
        if (!e.ok) badEnts++;
      });
    });

    return {
      total: Object.keys(data.automations).length,
      ent,
      err,
      badEnts,
    };
  }, [data]);

  return {
    filteredAutomations,
    stats,
    filters: {
      errOnly,
      runFilter,
      search,
      enabledStatus,
      entityState,
    },
    setFilters: {
      setErrOnly,
      setRunFilter,
      setSearch,
      setEnabledStatus,
      setEntityState,
    },
  };
}
