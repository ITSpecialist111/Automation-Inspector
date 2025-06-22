"use client";

import { useTheme } from "../contexts/ThemeContext";

export function useThemeAwareColors() {
  const { resolvedTheme } = useTheme();

  const colors = {
    primary: resolvedTheme === "dark" ? "#3b82f6" : "#2563eb",
    secondary: resolvedTheme === "dark" ? "#64748b" : "#475569",
    success: resolvedTheme === "dark" ? "#10b981" : "#059669",
    warning: resolvedTheme === "dark" ? "#f59e0b" : "#d97706",
    error: resolvedTheme === "dark" ? "#ef4444" : "#dc2626",
    background: resolvedTheme === "dark" ? "#0f172a" : "#f8fafc",
    surface: resolvedTheme === "dark" ? "#1e293b" : "#ffffff",
    text: resolvedTheme === "dark" ? "#f1f5f9" : "#0f172a",
    textSecondary: resolvedTheme === "dark" ? "#94a3b8" : "#64748b",
  };

  return { colors, isDark: resolvedTheme === "dark" };
}
