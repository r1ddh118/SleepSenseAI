import { Link } from "react-router";
import { Plus, TrendingDown, TrendingUp, Activity, Moon, Zap } from "lucide-react";
import { SessionCard } from "../components/SessionCard";
import { ThemeToggle } from "../components/ThemeToggle";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { mockSessions, patientInfo } from "../data/mockData";

export function Dashboard() {
  // Sort sessions by date (most recent first)
  const recentSessions = [...mockSessions].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  // Generate trend data
  const trendData = mockSessions
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .map((session) => ({
      date: session.date,
      risk: session.riskProbability * 100,
      efficiency: session.features.sleep_efficiency,
    }));

  const avgRisk = mockSessions.reduce((sum, s) => sum + s.riskProbability, 0) / mockSessions.length;
  const avgEfficiency =
    mockSessions.reduce((sum, s) => sum + s.features.sleep_efficiency, 0) / mockSessions.length;
  const avgDeepSleep = mockSessions.reduce((sum, s) => sum + s.sleepStages.n3, 0) / mockSessions.length;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Moon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">SleepSense AI</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">Clinical Sleep Analysis Platform</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Link
                to="/admin/models"
                className="px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors dark:text-gray-200"
              >
                Model Leaderboard
              </Link>
              <Link
                to="/session/new"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                New Session
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Patient Info Card */}
        <div className="bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl p-6 text-white mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold mb-1">{patientInfo.name}</h2>
              <p className="text-blue-100 mb-4">Patient ID: {patientInfo.patientId}</p>
              <div className="flex gap-6 text-sm">
                <div>
                  <p className="text-blue-100">Age</p>
                  <p className="font-semibold text-lg">{patientInfo.age} years</p>
                </div>
                <div>
                  <p className="text-blue-100">Device</p>
                  <p className="font-semibold text-lg">{patientInfo.deviceId}</p>
                </div>
                <div>
                  <p className="text-blue-100">Total Sessions</p>
                  <p className="font-semibold text-lg">{patientInfo.totalSessions}</p>
                </div>
              </div>
            </div>
            <div className="text-right">
              <p className="text-blue-100 mb-1">Last Session</p>
              <p className="text-lg font-semibold">
                {new Date(patientInfo.lastSessionDate).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm text-gray-600 dark:text-gray-400">Average Risk Score</h3>
              <Activity className="w-5 h-5 text-blue-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">{(avgRisk * 100).toFixed(0)}%</p>
            <div className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
              <TrendingDown className="w-4 h-4" />
              <span>12% from last week</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm text-gray-600 dark:text-gray-400">Sleep Efficiency</h3>
              <Zap className="w-5 h-5 text-amber-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">{avgEfficiency.toFixed(1)}%</p>
            <div className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
              <TrendingUp className="w-4 h-4" />
              <span>8% from last week</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm text-gray-600 dark:text-gray-400">Average Deep Sleep</h3>
              <Moon className="w-5 h-5 text-purple-600" />
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">{avgDeepSleep.toFixed(0)}%</p>
            <div className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400">
              <span>Target: 15-25%</span>
            </div>
          </div>
        </div>

        {/* Trend Chart */}
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-8">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Risk Score & Sleep Efficiency Trend</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                stroke="#6b7280"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) =>
                  new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                }
              />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: "6px" }}
              />
              <Line
                type="monotone"
                dataKey="risk"
                stroke="#ef4444"
                strokeWidth={2}
                name="Risk Score (%)"
                dot={{ fill: "#ef4444", r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="efficiency"
                stroke="#10b981"
                strokeWidth={2}
                name="Sleep Efficiency (%)"
                dot={{ fill: "#10b981", r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Sessions */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Recent Sessions</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">{mockSessions.length} total sessions</p>
          </div>
          <div className="grid grid-cols-1 gap-4">
            {recentSessions.map((session) => (
              <SessionCard key={session.id} session={session} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}