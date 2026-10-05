import type { RiskLevel } from "../data/mockData";

interface RiskBadgeProps {
  probability?: number;
  risk?: RiskLevel | string;
  size?: "sm" | "md" | "lg";
  showPercentage?: boolean;
}

export function RiskBadge({ probability, risk, size = "md", showPercentage = true }: RiskBadgeProps) {
  // Determine risk level safely from probability or risk string
  let level: RiskLevel = "low";
  let probVal = 0.15;

  if (typeof probability === "number" && !isNaN(probability)) {
    probVal = Math.max(0, Math.min(1, probability));
    level = probVal < 0.35 ? "low" : probVal < 0.7 ? "moderate" : "high";
  } else if (typeof risk === "string") {
    const lower = risk.toLowerCase();
    if (lower.includes("high")) {
      level = "high";
      probVal = 0.78;
    } else if (lower.includes("mod")) {
      level = "moderate";
      probVal = 0.52;
    } else {
      level = "low";
      probVal = 0.18;
    }
  }

  const colorClasses = {
    low: "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700",
    moderate: "bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700",
    high: "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-300 dark:border-red-700",
  };

  const sizeClasses = {
    sm: "text-xs px-2.5 py-0.5",
    md: "text-sm px-3 py-1",
    lg: "text-base px-4 py-2",
  };

  const percentageStr = (probVal * 100).toFixed(0);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide ${colorClasses[level]} ${sizeClasses[size]}`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          level === "low"
            ? "bg-green-500 dark:bg-green-400"
            : level === "moderate"
            ? "bg-amber-500 dark:bg-amber-400"
            : "bg-red-500 dark:bg-red-400 animate-pulse"
        }`}
      />
      <span>{level.toUpperCase()} RISK</span>
      {showPercentage && <span className="opacity-80 font-mono text-xs font-normal">({percentageStr}%)</span>}
    </span>
  );
}