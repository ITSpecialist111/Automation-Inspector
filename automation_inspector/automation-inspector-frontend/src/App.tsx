"use client";

import { useAutomationData } from "./hooks/useAutomationData";
import { useAutomationFilters } from "./hooks/useAutomationFilters";
import { ThemeProvider } from "./contexts/ThemeContext";
import { Header } from "./components/Header";
import { StatsCards } from "./components/StatsCards";
import { FilterPanel } from "./components/FilterPanel";
import { LoadingState } from "./components/LoadingState";
import { ErrorState } from "./components/ErrorState";
import { AutomationsTable } from "./components/AutomationsTable";

function AppContent() {
  const { data, loading, error, refresh } = useAutomationData();
  const { filteredAutomations, stats, filters, setFilters } =
    useAutomationFilters(data);

  const handleRefresh = () => {
    refresh(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 transition-all duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Header onRefresh={handleRefresh} isLoading={loading} />

        <StatsCards stats={stats} />

        <FilterPanel
          search={filters.search}
          onSearchChange={setFilters.setSearch}
          runFilter={filters.runFilter}
          onRunFilterChange={setFilters.setRunFilter}
          errorsOnly={filters.errOnly}
          onErrorsOnlyChange={setFilters.setErrOnly}
          enabledStatus={filters.enabledStatus}
          onEnabledStatusChange={setFilters.setEnabledStatus}
          entityState={filters.entityState}
          onEntityStateChange={setFilters.setEntityState}
        />

        {loading && <LoadingState />}

        {error && <ErrorState error={error} />}

        {!loading && !error && (
          <AutomationsTable
            automations={filteredAutomations}
            isLoading={loading}
          />
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <ThemeProvider
      defaultTheme="system"
      storageKey="automation-inspector-theme"
    >
      <AppContent />
    </ThemeProvider>
  );
}

export default App;
