import { FiExternalLink } from "react-icons/fi";
import { EntityBadge } from "./EntityBadge";
import { AutomationRowProps } from "../utils/types";

export function AutomationRow({ automation }: AutomationRowProps) {
  const hasBad = automation.entities.some((e) => !e.ok);
  const trace = automation.config_id
    ? `${window.location.protocol}//${window.location.hostname}:8123/config/automation/edit/${automation.config_id}`
    : null;

  let lastRunDisplay = "Never";
  let lastRunColor = "text-slate-500 dark:text-slate-400";

  if (automation.last_triggered) {
    lastRunDisplay = new Date(automation.last_triggered).toLocaleString();
    const daysOld =
      (Date.now() - new Date(automation.last_triggered).getTime()) /
      (1000 * 60 * 60 * 24);

    if (daysOld < 1) {
      lastRunColor = "text-green-600 dark:text-green-400";
    } else if (daysOld < 7) {
      lastRunColor = "text-yellow-600 dark:text-yellow-400";
    } else if (daysOld < 30) {
      lastRunColor = "text-orange-600 dark:text-orange-400";
    } else {
      lastRunColor = "text-red-600 dark:text-red-400";
    }
  }

  return (
    <tr
      className={`hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors ${
        !automation.enabled ? "opacity-60" : ""
      } ${hasBad ? "bg-red-50 dark:bg-red-900/20" : ""}`}
    >
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          {trace && (
            <a
              href={trace}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
              title="Edit automation"
            >
              <FiExternalLink className="w-4 h-4" />
            </a>
          )}
          <div>
            <p className="font-semibold text-slate-900 dark:text-white">
              {automation.friendly_name}
            </p>
            {!automation.enabled && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300 mt-1">
                Disabled
              </span>
            )}
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <span className={`text-sm font-medium ${lastRunColor}`}>
          {lastRunDisplay}
        </span>
      </td>
      <td className="px-6 py-4">
        <div className="flex flex-wrap gap-2">
          {automation.entities.map((entity) => (
            <EntityBadge key={entity.id} entity={entity} />
          ))}
        </div>
      </td>
    </tr>
  );
}
