import type { ReactNode } from "react";

export interface EntityInfo {
  id: string;
  state: string;
  ok: boolean;
}

export interface AutomationInfo {
  friendly_name: string;
  enabled: boolean;
  config_id?: string;
  last_triggered?: string | null;
  entities: EntityInfo[];
}

export interface DependencyMap {
  automations: Record<string, AutomationInfo>;
  orphans: string[];
}

export interface ErrorStateProps {
  error: string;
}

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
}

export interface RunFilterSelectProps {
  value: string;
  onChange: (value: string) => void;
}

export interface ErrorsOnlyToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export interface EnabledStatusFilterProps {
  value: string;
  onChange: (value: string) => void;
}

export interface EntityStateFilterProps {
  value: string;
  onChange: (value: string) => void;
}

export interface FilterPanelProps {
  search: string;
  onSearchChange: (value: string) => void;
  runFilter: string;
  onRunFilterChange: (value: string) => void;
  errorsOnly: boolean;
  onErrorsOnlyChange: (checked: boolean) => void;
  enabledStatus: string;
  onEnabledStatusChange: (value: string) => void;
  entityState: string;
  onEntityStateChange: (value: string) => void;
}

export interface AutomationsTableProps {
  automations: (AutomationInfo & { id: string })[];
  isLoading: boolean;
}

export interface AutomationRowProps {
  automation: AutomationInfo & { id: string };
}

export type Theme = "light" | "dark" | "system";

export interface ThemeContextType {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  systemTheme: "light" | "dark";
}

export interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}

export interface UseAutomationDataResult {
  data: DependencyMap | null;
  loading: boolean;
  error: string | null;
  refresh: (force?: boolean) => void;
}

export interface StatsCardsProps {
  stats: {
    total: number;
    ent: number;
    err: number;
    badEnts: number;
  };
}

export interface ThemeAwareCardProps {
  children: ReactNode;
  className?: string;
  variant?: "default" | "elevated" | "outlined";
}
