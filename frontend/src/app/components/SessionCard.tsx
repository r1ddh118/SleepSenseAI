import { Link } from "react-router";
import { Calendar, Clock, Activity } from "lucide-react";
import { RiskBadge } from "./RiskBadge";
import type { Session } from "../data/mockData";

interface SessionCardProps {
  session: Session;
}

export function SessionCard({ session }: SessionCardProps) {
  const sleepEfficiency = session.features?.sleep_efficiency ?? 0;
  const averageHeartRate = session.features?.HR_mean ?? 0;
  const sleepStages = session.sleepStages ?? { wake: 0, n1: 0, n2: 0, n3: 0, rem: 0 };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <Link
      to={`/session/${session.id}`}
      className="block bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5 hover:shadow-lg transition-shadow"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-lg">Session {session.sid}</h3>
          <div className="flex items-center gap-4 mt-1 text-sm text-gray-600 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              {formatDate(session.date)}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {Math.floor(session.duration / 60)}h {session.duration % 60}m
            </span>
          </div>
        </div>
        <RiskBadge probability={session.riskProbability} size="sm" />
      </div>

      <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Sleep Efficiency</p>
          <p className="font-semibold text-gray-900 dark:text-gray-100">{sleepEfficiency.toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Avg Heart Rate</p>
          <p className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1">
            <Activity className="w-4 h-4 text-red-500" />
            {averageHeartRate.toFixed(0)} bpm
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Deep Sleep</p>
          <p className="font-semibold text-gray-900 dark:text-gray-100">{sleepStages.n3}%</p>
        </div>
      </div>

      <div className="flex gap-2 mt-4">
        {Object.entries(sleepStages).map(([stage, pct]) => {
          const colors: Record<string, string> = {
            wake: "bg-red-500",
            n1: "bg-amber-500",
            n2: "bg-blue-500",
            n3: "bg-purple-500",
            rem: "bg-green-500",
          };
          return (
            <div
              key={stage}
              className={`h-2 rounded ${colors[stage]}`}
              style={{ width: `${pct}%` }}
              title={`${stage.toUpperCase()}: ${pct}%`}
            />
          );
        })}
      </div>
    </Link>
  );
}
