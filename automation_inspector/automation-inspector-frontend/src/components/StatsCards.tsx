import { FiActivity, FiCheckCircle, FiAlertCircle } from "react-icons/fi";
import { ThemeAwareCard } from "./ThemeAwareCard";
import { StatsCardsProps } from "../utils/types";

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: "Total Automations",
      value: stats.total,
      icon: FiActivity,
      bgColor: "bg-blue-100 dark:bg-blue-900/30",
      iconColor: "text-blue-600 dark:text-blue-400",
    },
    {
      title: "Total Entities",
      value: stats.ent,
      icon: FiCheckCircle,
      bgColor: "bg-green-100 dark:bg-green-900/30",
      iconColor: "text-green-600 dark:text-green-400",
    },
    {
      title: "Automations with Issues",
      value: stats.err,
      icon: FiAlertCircle,
      bgColor: "bg-red-100 dark:bg-red-900/30",
      iconColor: "text-red-600 dark:text-red-400",
      valueColor: "text-red-600 dark:text-red-400",
    },
    {
      title: "Bad Entities",
      value: stats.badEnts,
      icon: FiAlertCircle,
      bgColor: "bg-orange-100 dark:bg-orange-900/30",
      iconColor: "text-orange-600 dark:text-orange-400",
      valueColor: "text-orange-600 dark:text-orange-400",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {cards.map((card) => (
        <ThemeAwareCard
          key={card.title}
          className="p-6 hover:scale-105 cursor-default"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600 dark:text-slate-400 transition-colors duration-300">
                {card.title}
              </p>
              <p
                className={`text-2xl font-bold transition-colors duration-300 ${card.valueColor || "text-slate-900 dark:text-white"}`}
              >
                {card.value}
              </p>
            </div>
            <div
              className={`w-10 h-10 ${card.bgColor} rounded-lg flex items-center justify-center transition-all duration-300`}
            >
              <card.icon
                className={`w-5 h-5 ${card.iconColor} transition-colors duration-300`}
              />
            </div>
          </div>
        </ThemeAwareCard>
      ))}
    </div>
  );
}
