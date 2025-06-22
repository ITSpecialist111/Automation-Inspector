"use client";

import { useTheme } from "../contexts/ThemeContext";
import { ThemeAwareCardProps } from "../utils/types";

export function ThemeAwareCard({
  children,
  className = "",
  variant = "default",
}: ThemeAwareCardProps) {
  useTheme();

  const getVariantClasses = () => {
    const baseClasses = "rounded-xl transition-all duration-300";

    switch (variant) {
      case "elevated":
        return `${baseClasses} bg-white dark:bg-slate-800 shadow-lg hover:shadow-xl border border-slate-200 dark:border-slate-700`;
      case "outlined":
        return `${baseClasses} bg-transparent border-2 border-slate-300 dark:border-slate-600 hover:border-slate-400 dark:hover:border-slate-500`;
      default:
        return `${baseClasses} bg-white dark:bg-slate-800 shadow-sm border border-slate-200 dark:border-slate-700 hover:shadow-md`;
    }
  };

  return (
    <div className={`${getVariantClasses()} ${className}`}>{children}</div>
  );
}
