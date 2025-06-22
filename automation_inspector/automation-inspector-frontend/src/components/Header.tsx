"use client";

import { FiRefreshCw, FiActivity } from "react-icons/fi";
import { ThemeToggle } from "./ThemeToggle";

interface HeaderProps {
  onRefresh: () => void;
  isLoading: boolean;
}

export function Header({ onRefresh, isLoading }: HeaderProps) {
  return (
    <div className="mb-10">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
        <div className="flex items-center gap-5">
          <div className="flex items-center justify-center w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-105">
            <FiActivity className="text-white w-7 h-7" />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight transition-colors duration-300">
              Automation Inspector
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-2 transition-colors duration-300 text-base">
              Monitor and analyze your Home Assistant automations
            </p>
          </div>
        </div>
        <div className="flex items-center justify-end gap-4 sm:gap-3">
          <ThemeToggle />
          <button
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium rounded-lg shadow-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-slate-900 hover:shadow-md disabled:cursor-not-allowed"
            onClick={onRefresh}
            disabled={isLoading}
            title="Rebuild dependency map now"
          >
            <FiRefreshCw
              className={`w-4 h-4 transition-transform duration-200 ${isLoading ? "animate-spin" : ""}`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>
    </div>
  );
}
