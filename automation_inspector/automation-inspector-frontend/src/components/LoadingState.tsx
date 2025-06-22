import { FiRefreshCw } from "react-icons/fi";

export function LoadingState() {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-12 shadow-sm border border-slate-200 dark:border-slate-700">
      <div className="flex flex-col items-center justify-center">
        <FiRefreshCw className="w-8 h-8 text-blue-500 animate-spin mb-4" />
        <p className="text-lg font-medium text-slate-900 dark:text-white">
          Loading automations...
        </p>
        <p className="text-slate-600 dark:text-slate-400 mt-1">
          Please wait while we fetch your data
        </p>
      </div>
    </div>
  );
}
