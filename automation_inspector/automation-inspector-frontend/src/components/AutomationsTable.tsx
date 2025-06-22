import { AutomationRow } from "./AutomationRow";
import { EmptyState } from "./EmptyState";
import { ThemeAwareCard } from "./ThemeAwareCard";
import { AutomationsTableProps } from "../utils/types";

export function AutomationsTable({
  automations,
  isLoading,
}: AutomationsTableProps) {
  return (
    <ThemeAwareCard className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700 transition-colors duration-300">
            <tr>
              <th className="px-3 py-2 sm:px-6 sm:py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider transition-colors duration-300">
                Automation
              </th>
              <th className="px-3 py-2 sm:px-6 sm:py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider transition-colors duration-300">
                Last Run
              </th>
              <th className="px-3 py-2 sm:px-6 sm:py-4 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider transition-colors duration-300">
                Entities
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
            {automations.map((automation) => (
              <AutomationRow key={automation.id} automation={automation} />
            ))}
            {!isLoading && automations.length === 0 && <EmptyState />}
          </tbody>
        </table>
      </div>
    </ThemeAwareCard>
  );
}
