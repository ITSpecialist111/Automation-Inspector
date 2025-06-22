import * as Checkbox from "@radix-ui/react-checkbox";
import { FiCheck } from "react-icons/fi";
import { ErrorsOnlyToggleProps } from "../utils/types";

export function ErrorsOnlyToggle({ checked, onChange }: ErrorsOnlyToggleProps) {
  return (
    <div className="flex items-end">
      <label className="flex items-center gap-3 cursor-pointer">
        <Checkbox.Root
          className="w-5 h-5 rounded border-2 border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 flex items-center justify-center data-[state=checked]:bg-red-500 data-[state=checked]:border-red-500 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:focus:ring-offset-slate-800"
          checked={checked}
          onCheckedChange={(checked) => onChange(!!checked)}
          id="errOnly"
          title="Toggle to show only automations with errors"
        >
          <Checkbox.Indicator>
            <FiCheck className="text-white w-3 h-3" />
          </Checkbox.Indicator>
        </Checkbox.Root>
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          Show errors only
        </span>
      </label>
    </div>
  );
}
