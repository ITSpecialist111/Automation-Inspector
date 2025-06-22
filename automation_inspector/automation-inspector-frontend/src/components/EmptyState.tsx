import { FiActivity } from "react-icons/fi";

export function EmptyState() {
  return (
    <tr>
      <td colSpan={3} className="px-6 py-12 text-center">
        <div className="flex flex-col items-center">
          <FiActivity className="w-12 h-12 text-slate-300 dark:text-slate-600 mb-4" />
          <p className="text-lg font-medium text-slate-900 dark:text-white">
            No automations found
          </p>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Try adjusting your filters or search criteria
          </p>
        </div>
      </td>
    </tr>
  );
}
