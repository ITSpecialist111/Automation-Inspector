"use client";

import { useTheme } from "../contexts/ThemeContext";
import { FiSun, FiMoon, FiMonitor } from "react-icons/fi";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme, systemTheme } = useTheme();

  const getIcon = () => {
    switch (theme) {
      case "light":
        return <FiSun className="w-4 h-4" />;
      case "dark":
        return <FiMoon className="w-4 h-4" />;
      case "system":
        return <FiMonitor className="w-4 h-4" />;
      default:
        return <FiMonitor className="w-4 h-4" />;
    }
  };

  const getLabel = () => {
    switch (theme) {
      case "light":
        return "Light";
      case "dark":
        return "Dark";
      case "system":
        return "System";
      default:
        return "System";
    }
  };

  const getStatusText = () => {
    if (theme === "system") {
      return `Following system (${systemTheme})`;
    }
    return `Manual override: ${theme}`;
  };

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className="inline-flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-slate-900 shadow-sm"
          title={`Current theme: ${getLabel()} (${resolvedTheme})`}
        >
          <span className="transition-transform duration-200 hover:scale-110">
            {getIcon()}
          </span>
          <span className="hidden sm:inline text-sm font-medium">
            {getLabel()}
          </span>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 p-1 z-50 min-w-[160px] animate-in fade-in-0 zoom-in-95"
          sideOffset={5}
          align="end"
        >
          <DropdownMenu.Item
            className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer outline-none transition-colors duration-150 ${
              theme === "light"
                ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            onClick={() => setTheme("light")}
          >
            <FiSun className="w-4 h-4" />
            <span>Light</span>
            {theme === "light" && (
              <div className="ml-auto w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            )}
          </DropdownMenu.Item>

          <DropdownMenu.Item
            className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer outline-none transition-colors duration-150 ${
              theme === "dark"
                ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            onClick={() => setTheme("dark")}
          >
            <FiMoon className="w-4 h-4" />
            <span>Dark</span>
            {theme === "dark" && (
              <div className="ml-auto w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            )}
          </DropdownMenu.Item>

          <DropdownMenu.Item
            className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer outline-none transition-colors duration-150 ${
              theme === "system"
                ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            onClick={() => setTheme("system")}
          >
            <FiMonitor className="w-4 h-4" />
            <span>System</span>
            {theme === "system" && (
              <div className="ml-auto w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            )}
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="h-px bg-slate-200 dark:bg-slate-700 my-1" />

          <div className="px-3 py-2">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {getStatusText()}
            </p>
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
