import { FiAlertCircle } from "react-icons/fi";
import { ErrorStateProps } from "../utils/types";

export function ErrorState({ error }: ErrorStateProps) {
  return (
    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6">
      <div className="flex items-center gap-3">
        <FiAlertCircle className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" />
        <div>
          <h3 className="text-lg font-semibold text-red-900 dark:text-red-200">
            Error loading data
          </h3>
          <p
            className="text-red-700 dark:text-red-300 mt-1"
            title="Check your network connection or Home Assistant configuration for possible issues."
          >
            {error}
          </p>
        </div>
      </div>
    </div>
  );
}
