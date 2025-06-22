"use client";

import { SearchInput } from "./SearchInput";
import { RunFilterSelect } from "./RunFilterSelect";
import { ErrorsOnlyToggle } from "./ErrorsOnlyToggle";
import { EnabledStatusFilter } from "./EnabledStatusFilter";
import { EntityStateFilter } from "./EntityStateFilter";
import { ThemeAwareCard } from "./ThemeAwareCard";
import { FilterPanelProps } from "../utils/types";

export function FilterPanel({
  search,
  onSearchChange,
  runFilter,
  onRunFilterChange,
  errorsOnly,
  onErrorsOnlyChange,
  enabledStatus,
  onEnabledStatusChange,
  entityState,
  onEntityStateChange,
}: FilterPanelProps) {
  return (
    <ThemeAwareCard className="p-6 mb-8">
      <div className="flex flex-col gap-4 w-full">
        <div className="flex flex-col gap-4 w-full sm:flex-row sm:items-center sm:gap-6">
          <div className="flex-1 min-w-[220px]">
            <SearchInput value={search} onChange={onSearchChange} />
          </div>
          <div className="flex items-center min-w-[160px] h-full">
            <ErrorsOnlyToggle
              checked={errorsOnly}
              onChange={onErrorsOnlyChange}
            />
          </div>
        </div>
        <div className="flex flex-col gap-4 w-full sm:flex-row sm:items-center sm:gap-6">
          <div className="sm:w-64 min-w-[180px]">
            <RunFilterSelect value={runFilter} onChange={onRunFilterChange} />
          </div>
          <div className="sm:w-64 min-w-[180px]">
            <EnabledStatusFilter
              value={enabledStatus}
              onChange={onEnabledStatusChange}
            />
          </div>
          <div className="sm:w-64 min-w-[180px]">
            <EntityStateFilter
              value={entityState}
              onChange={onEntityStateChange}
            />
          </div>
        </div>
      </div>
    </ThemeAwareCard>
  );
}
