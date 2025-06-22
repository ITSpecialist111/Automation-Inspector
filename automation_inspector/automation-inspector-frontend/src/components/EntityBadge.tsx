import type { EntityInfo } from "../utils/types";

export function EntityBadge({ entity }: { entity: EntityInfo }) {
  return (
    <a
      href={`${window.location.protocol}//${window.location.hostname}:8123/developer-tools/state?entity_id=${encodeURIComponent(entity.id)}`}
      target="_blank"
      rel="noopener noreferrer"
      className="group"
      title="View entity state in Home Assistant"
    >
      <span
        className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium transition-colors group-hover:scale-105 ${
          entity.ok
            ? "bg-green-100 text-green-800 border border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700"
            : "bg-red-100 text-red-800 border border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700"
        }`}
      >
        <span className="font-mono">{entity.id}</span>
        <span className="ml-1 opacity-75">: {entity.state}</span>
      </span>
    </a>
  );
}
