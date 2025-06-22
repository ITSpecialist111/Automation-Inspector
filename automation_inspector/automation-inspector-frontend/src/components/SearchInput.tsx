"use client";

import { FiSearch } from "react-icons/fi";
import { SearchInputProps } from "../utils/types";

export function SearchInput({ value, onChange }: SearchInputProps) {
  return (
    <div className="flex-1">
      <label
        htmlFor="search"
        className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2"
      >
        Search automations and entities
      </label>
      <div className="relative">
        <FiSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
        <input
          id="search"
          type="text"
          className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
          placeholder="Search by name or entity ID..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          title="Search automations and entities by name or entity ID"
        />
      </div>
    </div>
  );
}
