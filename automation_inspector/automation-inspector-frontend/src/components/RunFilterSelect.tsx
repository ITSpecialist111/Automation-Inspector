"use client";

import * as Select from "@radix-ui/react-select";
import { FiChevronDown } from "react-icons/fi";
import { RunFilterSelectProps } from "../utils/types";

const filterOptions = [
  { value: "all", label: "All time" },
  { value: "1", label: "Last 1 day" },
  { value: "10", label: "Last 10 days" },
  { value: "20", label: "Last 20 days" },
  { value: "30", label: "Last 30 days" },
  { value: "-30", label: "Older than 30 days" },
  { value: "-90", label: "Older than 90 days" },
];

export function RunFilterSelect({ value, onChange }: RunFilterSelectProps) {
  const getLabel = (value: string) => {
    return (
      filterOptions.find((option) => option.value === value)?.label ||
      "All time"
    );
  };

  return (
    <div className="lg:w-64">
      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
        Last run filter
      </label>
      <Select.Root value={value} onValueChange={onChange}>
        <Select.Trigger
          className="w-full inline-flex items-center justify-between px-4 py-2.5 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
          title="Filter automations by last run time"
        >
          <Select.Value>{getLabel(value)}</Select.Value>
          <Select.Icon>
            <FiChevronDown className="w-4 h-4 text-slate-400" />
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content className="bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 z-50 overflow-hidden">
            <Select.Viewport className="p-1">
              {filterOptions.map((option) => (
                <Select.Item
                  key={option.value}
                  value={option.value}
                  className="flex items-center px-3 py-2 text-sm text-slate-900 dark:text-white hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md cursor-pointer outline-none"
                >
                  <Select.ItemText>{option.label}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </div>
  );
}
