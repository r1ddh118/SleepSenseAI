import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { HypnogramPoint } from "../data/mockData";

interface SleepHypnogramProps {
  data: HypnogramPoint[];
}

const stageLabels = ["Wake", "N1", "N2", "N3", "REM"];
const stageColors = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981"];

export function SleepHypnogram({ data }: SleepHypnogramProps) {
  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const stage = payload[0].value;
      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="font-medium text-gray-900 dark:text-gray-100">{stageLabels[stage]}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{formatTime(payload[0].payload.timestamp)}</p>
        </div>
      );
    }
    return null;
  };

  // Create gradient for each stage
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Sleep Hypnogram</h3>
        <div className="flex gap-4 text-xs">
          {stageLabels.map((label, idx) => (
            <div key={label} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded" style={{ backgroundColor: stageColors[idx] }} />
              <span className="text-gray-600 dark:text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data}>
          <defs>
            {stageColors.map((color, idx) => (
              <linearGradient key={`gradient-${idx}`} id={`stage${idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.8} />
                <stop offset="95%" stopColor={color} stopOpacity={0.3} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            stroke="#6b7280"
            tick={{ fontSize: 12 }}
          />
          <YAxis
            domain={[0, 4]}
            ticks={[0, 1, 2, 3, 4]}
            tickFormatter={(value) => stageLabels[value]}
            stroke="#6b7280"
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="stepAfter"
            dataKey="stage"
            stroke="#6b7280"
            strokeWidth={2}
            fill="url(#stage2)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}