import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { SensorDataPoint } from "../data/mockData";

interface SensorChartProps {
  data: SensorDataPoint[];
  title: string;
  color: string;
  unit: string;
  yAxisDomain?: [number, number];
}

export function SensorChart({ data, title, color, unit, yAxisDomain }: SensorChartProps) {
  // Sample data to reduce points (take every 5th point for performance)
  const sampledData = data.filter((_, i) => i % 5 === 0);

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={sampledData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTime}
            stroke="#6b7280"
            tick={{ fontSize: 12 }}
          />
          <YAxis
            domain={yAxisDomain || ["auto", "auto"]}
            stroke="#6b7280"
            tick={{ fontSize: 12 }}
            label={{ value: unit, angle: -90, position: "insideLeft", style: { fontSize: 12 } }}
          />
          <Tooltip
            labelFormatter={formatTime}
            formatter={(value: number) => [`${value.toFixed(1)} ${unit}`, title]}
            contentStyle={{ backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: "6px" }}
            wrapperClassName="dark:[&_.recharts-tooltip-wrapper]:!bg-gray-800 dark:[&_.recharts-tooltip-wrapper]:!border-gray-700"
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}