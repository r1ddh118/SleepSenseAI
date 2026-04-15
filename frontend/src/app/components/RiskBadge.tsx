import type { RiskLevel } from "../data/mockData";

interface RiskBadgeProps {
  probability: number;
  size?: "sm" | "md" | "lg";
}

export function RiskBadge({ probability, size = "md" }: RiskBadgeProps) {
  const level: RiskLevel =
    probability < 0.3 ? "low" : probability < 0.65 ? "moderate" : "high";

  const colorClasses = {
    low: "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700",
    moderate: "bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700",
    high: "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-300 dark:border-red-700",
  };

  const sizeClasses = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-3 py-1",
    lg: "text-base px-4 py-2",
  };

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border font-medium ${colorClasses[level]} ${sizeClasses[size]}`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          level === "low"
            ? "bg-green-500 dark:bg-green-400"
            : level === "moderate"
            ? "bg-amber-500 dark:bg-amber-400"
            : "bg-red-500 dark:bg-red-400"
        }`}
      />
      {level.toUpperCase()} RISK ({(probability * 100).toFixed(0)}%)
    </span>
  );
}